# -*- coding: utf-8 -*-
"""
Arıza Transfer Service - Transfer oluşturma mantığı

_create_stock_transfer'den taşınan tüm transfer oluşturma mantığı.
"""

import logging
from odoo import _, fields
from odoo.exceptions import UserError

from ..ariza_constants import ArizaTipi, IslemTipi, TeknikServis
from . import partner_helper
from . import transfer_helper

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
        delivery_carrier = transfer_helper.TransferHelper.get_delivery_carrier(ariza.env)
        if delivery_carrier:
            vals['carrier_id'] = delivery_carrier.id
        if ariza.vehicle_id:
            vals['vehicle_id'] = ariza.vehicle_id.id
        return vals

    @staticmethod
    def assign_driver(picking, driver_id, ariza_name):
        """Picking'e sürücü atar."""
        env = picking.env
        driver_partner = env['res.partner'].browse(driver_id)
        if not driver_partner.exists():
            _logger.warning(f"Default sürücü (ID {driver_id}) bulunamadı: {ariza_name}")
            return
        vehicle_id_val = False
        if hasattr(picking, 'vehicle_id') and picking.vehicle_id:
            vehicle_id_val = picking.vehicle_id.id
        elif hasattr(driver_partner, 'vehicle_id') and driver_partner.vehicle_id:
            vehicle_id_val = driver_partner.vehicle_id.id
        else:
            vehicle_id_val = driver_partner.id
        if not hasattr(picking, 'driver_ids'):
            _logger.error(f"driver_ids field'ı bulunamadı: {ariza_name} - Transfer: {picking.name}")
            return
        try:
            picking.sudo().write({
                'driver_ids': [(0, 0, {'driver_id': driver_partner.id, 'vehicle_id': vehicle_id_val})]
            })
        except Exception as e:
            _logger.error(f"Sürücü ataması başarısız: {ariza_name} - {str(e)}")
            try:
                picking.message_post(body=f"⚠️ Sürücü ataması yapılamadı: {str(e)}", message_type='notification')
            except Exception:
                pass

    @staticmethod
    def create_move(ariza, picking, kaynak, hedef):
        """Picking'e stock.move ekler."""
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
        picking_vals = ArizaTransferService.build_picking_vals(
            ariza, kaynak, hedef, picking_type, transfer_tipi
        )
        driver_id = ariza._get_default_driver_id()
        try:
            picking = ariza.env['stock.picking'].with_context(from_ariza_onarim=True).sudo().create(picking_vals)
        except Exception:
            try:
                picking = ariza.env['stock.picking'].with_context(
                    from_ariza_onarim=True, force_company=ariza.env.company.id
                ).sudo().create(picking_vals)
            except Exception as e2:
                raise UserError(_(f"Transfer oluşturulamadı: Güvenlik kısıtlaması! Hata: {str(e2)}"))
        ArizaTransferService.assign_driver(picking, driver_id, ariza.name)
        ArizaTransferService.create_move(ariza, picking, kaynak, hedef)
        ArizaTransferService.post_transfer_message(ariza, picking, kaynak, hedef)
        return picking
