# -*- coding: utf-8 -*-
"""
Arıza Müşteri İade Service - Müşteri ürünü iade kargo sevkiyatı

Onarılan müşteri ürünü müşteriye kargoyla geri gönderilirken (Adrese Gönderim)
Aras kargo barkodu üretebilmek için gerçek bir teslimat picking'i oluşturur.

Notlar:
- Kalem stok-dışı üründür ("Müşteri Ürünü (Kargo)", consumable) — envanteri bozmaz.
- Picking otomatik VALIDATE EDİLMEZ; kullanıcı kargoya verirken doğrular,
  Aras booking ve carrier_tracking_ref (barkod) o anda oluşur.
- Bu picking e-İrsaliye ÜRETMEZ (is_ariza_musteri_iade=True → Matbu/printed).
- Mağaza ürünü akışına (ArizaTransferService.create_stock_transfer) dokunmaz.
"""

import logging

from odoo import _
from odoo.exceptions import UserError

from ..ariza_constants import ArizaTipi
from . import transfer_helper

_logger = logging.getLogger(__name__)

# Modül data'sındaki stok-dışı kargo ürünü (data/iade_kargo_product.xml)
IADE_KARGO_URUN_XMLID = 'ariza_onarim.product_musteri_urunu_kargo'
IADE_KARGO_URUN_KODU = 'ARZ-IADE-KARGO'

# Aras taşıyıcısı delivery_type değeri
ARAS_DELIVERY_TYPE = 'aras'


class ArizaMusteriIadeService:
    """Müşteri ürünü iade kargo picking'i oluşturma servisi"""

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
        """Müşteri hedef konumunu döner (partner özel konumu veya genel Müşteriler)."""
        if partner and partner.property_stock_customer:
            return partner.property_stock_customer
        return env.ref('stock.stock_location_customers')

    @staticmethod
    def create_iade_picking(ariza):
        """
        Müşteri ürünü için Aras iade teslimat picking'i oluşturur.

        Idempotent: geçerli (iptal edilmemiş) bir iade transferi zaten varsa
        yenisini oluşturmaz, mevcut picking'i döner.

        Returns:
            stock.picking
        """
        env = ariza.env
        if ariza.ariza_tipi != ArizaTipi.MUSTERI:
            raise UserError(_('İade kargo transferi sadece müşteri ürünleri için oluşturulabilir.'))

        # Idempotency: geçerli iade transferi varsa tekrar oluşturma
        if ariza.iade_transfer_id and ariza.iade_transfer_id.state != 'cancel':
            return ariza.iade_transfer_id

        # Alıcı: teslimat adresi (contact_id) öncelikli, yoksa müşteri
        alici = ariza.contact_id or ariza.partner_id
        if not alici:
            raise UserError(_('İade kargo transferi için müşteri/teslimat adresi bulunamadı!'))

        # Kaynak: kaydın mağazasının deposu (teslimat operasyon tipi)
        warehouse = transfer_helper.TransferHelper.get_warehouse_for_magaza(
            env, ariza.analitik_hesap_id.name if ariza.analitik_hesap_id else ''
        )
        if not warehouse:
            raise UserError(_(
                'İade kargo transferi için depo bulunamadı!\n'
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
            'is_ariza_musteri_iade': True,
            'analytic_account_id': ariza.analitik_hesap_id.id if ariza.analitik_hesap_id else False,
            'note': (
                f"Arıza Kaydı: {ariza.name}\n"
                f"Müşteri Ürünü İadesi (Adrese Gönderim)\n"
                f"Ürün: {ariza.urun or ''}\n"
                f"Seri No: {ariza.seri_no or ''}"
            ),
        }

        try:
            picking = env['stock.picking'].with_context(
                from_ariza_onarim=True, from_ariza_musteri_iade=True
            ).sudo().create(picking_vals)
        except Exception as e:
            raise UserError(_('İade kargo transferi oluşturulamadı: %s') % str(e))

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
            raise UserError(_('İade kargo transferi oluşturulamadı: %s') % str(e))

        ariza.iade_transfer_id = picking.id

        picking_url = f"/web#id={picking.id}&model=stock.picking&view_type=form"
        ariza.message_post(
            body=(
                f"<b>İade kargo transferi oluşturuldu!</b><br/>"
                f"Transfer No: <a href='{picking_url}'>{picking.name}</a><br/>"
                f"Alıcı: {alici.display_name}<br/>"
                f"Taşıyıcı: {carrier.name}<br/>"
                f"Aras barkodu, transfer <b>doğrulandığında (validate)</b> oluşacaktır."
            ),
            message_type='notification'
        )
        _logger.info(f"[MUSTERI IADE] İade picking oluşturuldu: {picking.name} (Arıza: {ariza.name})")
        return picking
