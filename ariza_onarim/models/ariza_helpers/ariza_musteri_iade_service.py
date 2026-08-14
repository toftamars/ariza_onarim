# -*- coding: utf-8 -*-
"""
Arıza Müşteri Kargo Service - Müşteri ürünü Aras kargo sevkiyatları

Müşteri ürünleri için iki yönde Aras kargo picking'i oluşturur:

1. GİDİŞ (create_gidis_picking): Personel ONAYLA'ya bastığında, transfer
   metodu kargo ise mağaza → teknik servis sevkiyatı (ariza.transfer_id).
2. İADE (create_iade_picking): Onarım sonrası "Adrese Gönderilsin"
   seçildiğinde teknik servis/mağaza → müşteri adresi sevkiyatı
   (ariza.iade_transfer_id).

Ortak notlar:
- Kalem stok-dışı üründür ("Müşteri Ürünü (Kargo)", consumable) — envanteri
  bozmaz (müşteri ürünü zaten stokta değildir).
- Picking otomatik VALIDATE EDİLMEZ; kullanıcı kargoya verirken doğrular,
  Aras booking ve carrier_tracking_ref (barkod) o anda oluşur.
- Bu picking'ler e-İrsaliye ÜRETMEZ (arıza transferleri Matbu/printed).
- Mağaza ürünü akışına (ArizaTransferService.create_stock_transfer) dokunmaz.
"""

import logging

from odoo import _
from odoo.exceptions import UserError

from ..ariza_constants import ArizaTipi, TeknikServis
from . import partner_helper
from . import transfer_helper

_logger = logging.getLogger(__name__)

# Modül data'sındaki stok-dışı kargo ürünü (data/iade_kargo_product.xml)
IADE_KARGO_URUN_XMLID = 'ariza_onarim.product_musteri_urunu_kargo'
IADE_KARGO_URUN_KODU = 'ARZ-IADE-KARGO'

# Aras taşıyıcısı delivery_type değeri
ARAS_DELIVERY_TYPE = 'aras'


class ArizaMusteriIadeService:
    """Müşteri ürünü Aras kargo picking'i oluşturma servisi (gidiş + iade)"""

    @staticmethod
    def get_aras_carrier(env):
        """Aras taşıyıcısını döner (delivery_type='aras').

        Taşıyıcı sistemde arşivli olabilir (satış ekranlarında görünmesin diye);
        arşivli olsa da picking'e atanıp booking yapılabildiği için
        arşivliler de aranır.
        """
        carrier = env['delivery.carrier'].sudo().search([
            ('delivery_type', '=', ARAS_DELIVERY_TYPE),
        ], limit=1)
        if not carrier:
            carrier = env['delivery.carrier'].sudo().with_context(active_test=False).search([
                ('delivery_type', '=', ARAS_DELIVERY_TYPE),
            ], limit=1)
        if not carrier:
            raise UserError(_(
                'Aras Kargo taşıyıcısı bulunamadı!\n'
                'Stok > Ayarlar > Kargo Şirketleri menüsünden '
                "delivery_type='aras' olan bir taşıyıcı tanımlı olmalı."
            ))
        return carrier

    @staticmethod
    def get_iade_urun(env):
        """Stok-dışı 'Müşteri Ürünü (Kargo)' ürününü döner."""
        urun = env.ref(IADE_KARGO_URUN_XMLID, raise_if_not_found=False)
        if not urun:
            urun = env['product.product'].sudo().search([
                ('default_code', '=', IADE_KARGO_URUN_KODU)
            ], limit=1)
        if not urun:
            raise UserError(_(
                "İade kargo ürünü bulunamadı ('Müşteri Ürünü (Kargo)').\n"
                'Modül güncellemesi (upgrade) yapıldığından emin olun.'
            ))
        return urun

    @staticmethod
    def get_musteri_konumu(env, partner):
        """Hedef konumu döner (partner özel konumu veya genel Müşteriler)."""
        if partner and partner.property_stock_customer:
            return partner.property_stock_customer
        return env.ref('stock.stock_location_customers')

    @staticmethod
    def get_teknik_servis_partner(ariza):
        """Gidiş sevkiyatının alıcısı: teknik servis partneri."""
        if ariza.teknik_servis == TeknikServis.TEDARIKCI and ariza.tedarikci_id:
            return ariza.tedarikci_id
        return partner_helper.PartnerHelper.get_partner_by_teknik_servis(
            ariza.env, ariza.teknik_servis
        )

    @staticmethod
    def _create_aras_picking(ariza, alici, note, is_iade):
        """
        Müşteri ürünü için Aras teslimat picking'i oluşturur (ortak mantık).

        Args:
            ariza: ariza.kayit kaydı
            alici: res.partner (kargonun alıcısı)
            note: picking notu
            is_iade: True ise iade sevkiyatı (is_ariza_musteri_iade bayrağı)

        Returns:
            stock.picking
        """
        env = ariza.env

        warehouse = transfer_helper.TransferHelper.get_warehouse_for_magaza(
            env, ariza.analitik_hesap_id.name if ariza.analitik_hesap_id else ''
        )
        if not warehouse:
            raise UserError(_(
                'Kargo transferi için depo bulunamadı!\n'
                'Analitik hesap: %s'
            ) % (ariza.analitik_hesap_id.name if ariza.analitik_hesap_id else '-'))

        picking_type = transfer_helper.TransferHelper.get_picking_type(
            env, warehouse, 'outgoing', raise_if_not_found=True
        )
        kaynak = picking_type.default_location_src_id or warehouse.lot_stock_id
        hedef = ArizaMusteriIadeService.get_musteri_konumu(env, alici)
        carrier = ArizaMusteriIadeService.get_aras_carrier(env)
        urun = ArizaMusteriIadeService.get_iade_urun(env)

        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': kaynak.id,
            'location_dest_id': hedef.id,
            'partner_id': alici.id,
            'origin': ariza.name,
            'carrier_id': carrier.id,
            'is_ariza_musteri_iade': is_iade,
            'analytic_account_id': ariza.analitik_hesap_id.id if ariza.analitik_hesap_id else False,
            'note': note,
        }

        ctx = {'from_ariza_onarim': True}
        if is_iade:
            ctx['from_ariza_musteri_iade'] = True

        try:
            picking = env['stock.picking'].with_context(**ctx).sudo().create(picking_vals)
        except Exception as e:
            raise UserError(_('Kargo transferi oluşturulamadı: %s') % str(e))

        # Kalem: stok-dışı ürün; gerçek ürün bilgisi açıklamada taşınır
        marka = ariza.marka_id.name if ariza.marka_id else (ariza.marka_manu or '')
        move_name = ' - '.join(p for p in [marka, ariza.urun or ''] if p) or urun.name
        move_vals = {
            'name': f"{move_name} (Arıza: {ariza.name})",
            'product_id': urun.id,
            'product_uom_qty': 1,
            'product_uom': urun.uom_id.id,
            'picking_id': picking.id,
            'location_id': kaynak.id,
            'location_dest_id': hedef.id,
            'company_id': env.company.id,
        }
        if ariza.analitik_hesap_id:
            move_vals['analytic_account_id'] = ariza.analitik_hesap_id.id
        try:
            env['stock.move'].sudo().create(move_vals)
            picking.sudo().action_confirm()
            picking.sudo().action_assign()
        except Exception as e:
            try:
                picking.sudo().unlink()
            except Exception:
                pass
            raise UserError(_('Kargo transferi oluşturulamadı: %s') % str(e))

        return picking

    @staticmethod
    def create_gidis_picking(ariza):
        """
        Müşteri ürünü için mağaza → teknik servis Aras GİDİŞ sevkiyatı oluşturur.

        Personel ONAYLA aşamasında, transfer metodu kargo ise çağrılır.
        Idempotent: geçerli bir transfer zaten varsa yenisini oluşturmaz.

        Returns:
            stock.picking
        """
        if ariza.ariza_tipi != ArizaTipi.MUSTERI:
            raise UserError(_('Gidiş kargo transferi sadece müşteri ürünleri için oluşturulabilir.'))

        if ariza.transfer_id and ariza.transfer_id.state != 'cancel':
            return ariza.transfer_id

        alici = ArizaMusteriIadeService.get_teknik_servis_partner(ariza)
        if not alici:
            raise UserError(_(
                'Gidiş kargosu için teknik servis partneri bulunamadı!\n'
                'Teknik servis: %s'
            ) % (ariza.teknik_servis or '-'))

        note = (
            f"Arıza Kaydı: {ariza.name}\n"
            f"Müşteri Ürünü - Teknik Servise Gidiş ({ariza.teknik_servis or ''})\n"
            f"Ürün: {ariza.urun or ''}\n"
            f"Seri No: {ariza.seri_no or ''}"
        )
        picking = ArizaMusteriIadeService._create_aras_picking(ariza, alici, note, is_iade=False)

        ariza.transfer_id = picking.id

        picking_url = f"/web#id={picking.id}&model=stock.picking&view_type=form"
        ariza.message_post(
            body=(
                f"<b>Teknik servise gidiş kargo transferi oluşturuldu!</b><br/>"
                f"Transfer No: <a href='{picking_url}'>{picking.name}</a><br/>"
                f"Alıcı: {alici.display_name}<br/>"
                f"Taşıyıcı: Aras Kargo<br/>"
                f"Aras barkodu, transfer <b>doğrulandığında (validate)</b> oluşacaktır."
            ),
            message_type='notification'
        )
        _logger.info(f"[MUSTERI GIDIS] Gidiş picking oluşturuldu: {picking.name} (Arıza: {ariza.name})")
        return picking

    @staticmethod
    def create_iade_picking(ariza):
        """
        Müşteri ürünü için müşteri adresine Aras İADE sevkiyatı oluşturur.

        Idempotent: geçerli (iptal edilmemiş) bir iade transferi zaten varsa
        yenisini oluşturmaz, mevcut picking'i döner.

        Returns:
            stock.picking
        """
        if ariza.ariza_tipi != ArizaTipi.MUSTERI:
            raise UserError(_('İade kargo transferi sadece müşteri ürünleri için oluşturulabilir.'))

        # Idempotency: geçerli iade transferi varsa tekrar oluşturma
        if ariza.iade_transfer_id and ariza.iade_transfer_id.state != 'cancel':
            return ariza.iade_transfer_id

        # Alıcı: teslimat adresi (contact_id) öncelikli, yoksa müşteri
        alici = ariza.contact_id or ariza.partner_id
        if not alici:
            raise UserError(_('İade kargo transferi için müşteri/teslimat adresi bulunamadı!'))

        note = (
            f"Arıza Kaydı: {ariza.name}\n"
            f"Müşteri Ürünü İadesi (Adrese Gönderim)\n"
            f"Ürün: {ariza.urun or ''}\n"
            f"Seri No: {ariza.seri_no or ''}"
        )
        picking = ArizaMusteriIadeService._create_aras_picking(ariza, alici, note, is_iade=True)

        ariza.iade_transfer_id = picking.id

        picking_url = f"/web#id={picking.id}&model=stock.picking&view_type=form"
        ariza.message_post(
            body=(
                f"<b>İade kargo transferi oluşturuldu!</b><br/>"
                f"Transfer No: <a href='{picking_url}'>{picking.name}</a><br/>"
                f"Alıcı: {alici.display_name}<br/>"
                f"Taşıyıcı: Aras Kargo<br/>"
                f"Aras barkodu, transfer <b>doğrulandığında (validate)</b> oluşacaktır."
            ),
            message_type='notification'
        )
        _logger.info(f"[MUSTERI IADE] İade picking oluşturuldu: {picking.name} (Arıza: {ariza.name})")
        return picking
