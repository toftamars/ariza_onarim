# -*- coding: utf-8 -*-
"""
Arıza Transfer Service - Transfer oluşturma mantığı

_create_stock_transfer'den taşınan tüm transfer oluşturma mantığı.
"""

import logging
from odoo import _, fields
from odoo.exceptions import UserError

from ..ariza_constants import ArizaTipi, IslemTipi, TeknikServis, TransferMetodu
from . import partner_helper
from . import transfer_helper
from . import transit_helper
from . import ariza_musteri_iade_service

_logger = logging.getLogger(__name__)


class ArizaTransferService:
    """Arıza kaydı için transfer oluşturma servisi"""

    @staticmethod
    def get_edespatch_sequence_id(env, analitik_hesap_name):
        """Analitik hesap adından E-İrsaliye sequence ID döner."""
        if not analitik_hesap_name:
            return False
        analitik_adi = analitik_hesap_name
        if analitik_adi.startswith("Perakende - "):
            analitik_adi = analitik_adi[12:]
        edespatch_sequence = env['ir.sequence'].search([
            ('active', '=', True),
            ('company_id', '=', env.company.id),
            ('code', 'in', ['stock.edespatch', 'stock.ereceipt']),
            ('name', '=', f"{analitik_adi} - E-İrsaliye")
        ], limit=1)
        if not edespatch_sequence:
            all_sequences = env['ir.sequence'].search([
                ('active', '=', True),
                ('company_id', '=', env.company.id),
                ('code', 'in', ['stock.edespatch', 'stock.ereceipt']),
                ('name', 'ilike', 'E-İrsaliye')
            ])
            for seq in all_sequences:
                if analitik_adi.upper() in seq.name.upper():
                    edespatch_sequence = seq
                    break
        return edespatch_sequence.id if edespatch_sequence else False

    @staticmethod
    def build_picking_vals(ariza, kaynak, hedef, picking_type, transfer_tipi):
        """Transfer için picking_vals dict oluşturur."""
        vals = {
            'picking_type_id': picking_type.id,
            'location_id': kaynak.id,
            'location_dest_id': hedef.id,
            'origin': ariza.name,
            'analytic_account_id': ariza.analitik_hesap_id.id if ariza.analitik_hesap_id else False,
        }
        edespatch_id = ArizaTransferService.get_edespatch_sequence_id(
            ariza.env, ariza.analitik_hesap_id.name if ariza.analitik_hesap_id else ''
        )
        if edespatch_id:
            vals['edespatch_number_sequence'] = edespatch_id
        if transfer_tipi != 'ikinci':
            vals['note'] = (
                f"Arıza Kaydı: {ariza.name}\nÜrün: {ariza.urun}\nModel: {ariza.model}\nTransfer Metodu: {ariza.transfer_metodu}"
            )
        magaza_partner = ariza.analitik_hesap_id.partner_id if ariza.analitik_hesap_id and ariza.analitik_hesap_id.partner_id else False
        teknik_servis_partner = ariza.tedarikci_id if ariza.teknik_servis == TeknikServis.TEDARIKCI and ariza.tedarikci_id else partner_helper.PartnerHelper.get_partner_by_teknik_servis(ariza.env, ariza.teknik_servis)
        if transfer_tipi != 'ikinci' and ariza.islem_tipi == IslemTipi.ARIZA_KABUL and ariza.ariza_tipi == ArizaTipi.MAGAZA and ariza.teknik_servis == TeknikServis.TEDARIKCI and ariza.contact_id:
            teknik_servis_partner = ariza.contact_id
        if transfer_tipi == 'ilk' and teknik_servis_partner:
            vals['partner_id'] = teknik_servis_partner.id
        elif transfer_tipi == 'ikinci' and magaza_partner:
            vals['partner_id'] = magaza_partner.id
        elif teknik_servis_partner:
            vals['partner_id'] = teknik_servis_partner.id
        # Kargo ile taşınan transferlerde Aras taşıyıcısı atanır: transfer
        # doğrulandığında (validate) Aras booking yapılır ve barkod
        # (carrier_tracking_ref) otomatik oluşur. Diğer metodlarda (araç vb.)
        # mevcut davranış korunur (sabit/ücretsiz taşıyıcı, booking yok).
        delivery_carrier = False
        if ariza.transfer_metodu in (TransferMetodu.UCRETSIZ_KARGO, TransferMetodu.UCRETLI_KARGO):
            try:
                delivery_carrier = ariza_musteri_iade_service.ArizaMusteriIadeService.get_aras_carrier(ariza.env)
            except UserError:
                _logger.warning("Aras taşıyıcısı bulunamadı; sabit taşıyıcıya dönülüyor (kayıt: %s)", ariza.name)
        if not delivery_carrier:
            delivery_carrier = transfer_helper.TransferHelper.get_delivery_carrier(ariza.env)
        if delivery_carrier:
            vals['carrier_id'] = delivery_carrier.id
        return vals

    @staticmethod
    def create_move(ariza, picking, kaynak, hedef, route=None, group=None):
        """Picking'e stock.move ekler. route verilirse (yolda akışı) harekete
        rota, kayıt grubu ve ARZ origin'i yazılır: itme kuralıyla doğan varış
        transferi bunları kopyalar (ayrı picking + Matbu + kayıt eşleşmesi)."""
        move_vals = {
            'name': ariza.urun or ariza.magaza_urun_id.name,
            'product_id': ariza.magaza_urun_id.id,
            'product_uom_qty': 1,
            'product_uom': ariza.magaza_urun_id.uom_id.id,
            'picking_id': picking.id,
            'location_id': kaynak.id,
            'location_dest_id': hedef.id,
            'company_id': ariza.env.company.id,
        }
        if ariza.analitik_hesap_id:
            move_vals['analytic_account_id'] = ariza.analitik_hesap_id.id
        if route:
            move_vals.update({
                'origin': ariza.name,
                'group_id': group.id if group else False,
                'route_ids': [(6, 0, route.ids)],
            })
        try:
            ariza.env['stock.move'].sudo().create(move_vals)
        except Exception as e:
            try:
                picking.sudo().unlink()
            except Exception:
                pass
            raise UserError(_(f"Transfer oluşturulamadı: {str(e)}"))

    @staticmethod
    def post_transfer_message(ariza, picking, kaynak, hedef):
        """Ariza chatter'a transfer mesajı ekler."""
        transfer_url = f"/web#id={picking.id}&model=stock.picking&view_type=form"
        transfer_no_html = f'<a href="{transfer_url}">{picking.name}</a>'
        durum = dict(ariza._fields['state'].selection).get(ariza.state, ariza.state)
        sms_bilgi = 'Aktif' if ariza.sms_gonderildi else 'Deaktif'
        ariza.message_post(
            body=f"<b>Yeni transfer oluşturuldu!</b><br/>"
                 f"Transfer No: {transfer_no_html}<br/>"
                 f"Kaynak: {kaynak.display_name}<br/>"
                 f"Hedef: {hedef.display_name}<br/>"
                 f"Tarih: {fields.Date.today()}<br/>"
                 f"Durum: {durum}<br/>"
                 f"SMS Gönderildi: {sms_bilgi}",
            message_type='notification'
        )

    @staticmethod
    def create_stock_transfer(ariza, kaynak_konum=None, hedef_konum=None, transfer_tipi=None):
        """
        Arıza kaydı için stok transferi oluşturur.
        Returns: stock.picking
        """
        kaynak = kaynak_konum or ariza.kaynak_konum_id
        hedef = hedef_konum or ariza.hedef_konum_id
        if not ariza.analitik_hesap_id:
            raise UserError(_("Transfer oluşturulamadı: Analitik hesap seçili değil!"))
        if not kaynak or not hedef:
            raise UserError(_("Transfer oluşturulamadı: Kaynak veya hedef konum eksik!"))
        if not ariza.magaza_urun_id:
            raise UserError(_("Transfer oluşturulamadı: Ürün seçili değil!"))
        warehouse = transfer_helper.TransferHelper.get_warehouse_for_magaza(
            ariza.env, ariza.analitik_hesap_id.name if ariza.analitik_hesap_id else ''
        )
        picking_type = transfer_helper.TransferHelper.get_tamir_picking_type(
            ariza.env, transfer_tipi, warehouse
        )
        if not picking_type:
            raise UserError(_("Transfer oluşturulamadı: Uygun operasyon tipi bulunamadı!"))
        yolda = None
        route = group = False
        if transfer_tipi == 'ilk':
            yolda = transit_helper.TransitHelper.hazirla(ariza, kaynak, hedef)
        if yolda:
            route, transit, _nihai_hedef = yolda
            hedef = transit
        picking_vals = ArizaTransferService.build_picking_vals(
            ariza, kaynak, hedef, picking_type, transfer_tipi
        )
        if yolda:
            # Kayda özel grup: varış hareketi başka açık transferlere karışmasın
            # (Faz 0: grupsuz hareket Ocak'tan beri açık bir IN'e eklenmişti).
            group = ariza.env['procurement.group'].sudo().create({'name': ariza.name})
            picking_vals['group_id'] = group.id
        try:
            picking = ariza.env['stock.picking'].with_context(from_ariza_onarim=True).sudo().create(picking_vals)
        except Exception:
            try:
                picking = ariza.env['stock.picking'].with_context(
                    from_ariza_onarim=True, force_company=ariza.env.company.id
                ).sudo().create(picking_vals)
            except Exception as e2:
                raise UserError(_(f"Transfer oluşturulamadı: Güvenlik kısıtlaması! Hata: {str(e2)}"))
        ArizaTransferService.create_move(ariza, picking, kaynak, hedef, route=route, group=group)
        ArizaTransferService.post_transfer_message(ariza, picking, kaynak, hedef)
        if yolda:
            ArizaTransferService._yolda_baglat(ariza, picking, group)
        return picking

    @staticmethod
    def _yolda_baglat(ariza, picking, group):
        """Çıkışı onaylar (itme kuralı varış transferini doğurur) ve varışı kayda bağlar."""
        picking.sudo().action_confirm()
        varis = picking.move_ids_without_package.move_dest_ids.picking_id[:1]
        if not varis:
            # Odoo bazı durumlarda hareket bağını kurmayabilir: grupla ara
            varis = ariza.env['stock.picking'].sudo().search([
                ('group_id', '=', group.id),
                ('location_id', '=', picking.location_dest_id.id),
                ('id', '!=', picking.id),
            ], limit=1)
        if not varis:
            raise UserError(_(
                "Yolda transferi kurulamadı: varış transferi oluşmadı. "
                "Rota kurallarını kontrol edin (%s)."
            ) % picking.name)
        if len(varis.move_lines) != 1 or varis.group_id != group:
            # Varış başka kayıtların hareketleriyle karışmışsa doğrulama/iptal
            # onları da etkiler: kurmayı reddet.
            raise UserError(_(
                "Yolda transferi kurulamadı: varış transferi (%s) başka "
                "hareketler içeriyor. Lütfen yöneticinize bildirin."
            ) % varis.name)
        ariza.sudo().write({'yolda_akisi': True, 'gidis_in_id': varis.id})
        hedef_notu = ''
        if ariza.hedef_konum_id and ariza.hedef_konum_id != varis.location_dest_id:
            hedef_notu = (
                f"<br/>Not: Varış hedefi ({varis.location_dest_id.display_name}) kayıttaki "
                f"hedef konumdan ({ariza.hedef_konum_id.display_name}) farklı."
            )
        ariza.message_post(
            body=(
                f"<b>Yolda (iki adımlı) transfer kuruldu.</b><br/>"
                f"Çıkış: {picking.name} — ürün yola çıkınca doğrulanır.<br/>"
                f"Varış: {varis.name} — teknik servis ürünü teslim alınca "
                f"\"Kabul Et\" ile doğrulanır.{hedef_notu}"
            ),
            message_type='notification',
        )
