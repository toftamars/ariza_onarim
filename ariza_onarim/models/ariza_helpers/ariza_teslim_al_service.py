# -*- coding: utf-8 -*-
"""
Arıza Teslim Al Service - Mağaza ürünü teslim al (Tamir Alımlar transferi)

action_teslim_al mantığı - Tamir Alımlar transferi oluşturma.
"""

import logging
from odoo import _, fields
from odoo.exceptions import UserError

from ..ariza_constants import ArizaStates, ArizaTipi, MagicNumbers, PartnerNames, TeknikServis

_logger = logging.getLogger(__name__)


class ArizaTeslimAlService:
    """Mağaza ürünü teslim al - Tamir Alımlar transferi servisi"""

    @staticmethod
    def execute(ariza):
        """
        Teslim al işlemini yürütür. Tamir Alımlar transferi oluşturur.
        Returns: ir.actions.act_window dict veya None
        """
        if ariza.ariza_tipi != ArizaTipi.MAGAZA:
            raise UserError('Bu işlem sadece mağaza ürünü işlemleri için kullanılabilir!')
        if ariza.state != ArizaStates.YONETICI_TAMAMLANDI:
            raise UserError('Bu işlem sadece yönetici tamamlandı durumundaki kayıtlar için kullanılabilir!')

        ilk_transfer = ariza.env['stock.picking'].search([
            ('origin', '=', ariza.name),
            ('state', '=', 'done')
        ], order='create_date asc', limit=1)
        if not ilk_transfer:
            raise UserError('İlk transfer bulunamadı! Lütfen önce ilk transferin tamamlandığından emin olun.')

        kaynak_konum = ilk_transfer.location_dest_id
        hedef_konum = ilk_transfer.location_id
        if not kaynak_konum or not hedef_konum:
            raise UserError('İlk transferin konum bilgileri eksik! Lütfen ilk transferi kontrol edin.')

        picking_type = ArizaTeslimAlService._get_tamir_alim_picking_type(
            ariza, kaynak_konum, hedef_konum, ilk_transfer
        )
        if not picking_type:
            is_ariza_stok = ArizaTeslimAlService._is_ariza_stok(hedef_konum)
            err_msg = 'Arıza: Tamir Alımlar' if is_ariza_stok else 'Tamir Alımlar'
            raise UserError(_('%s picking type bulunamadı! Lütfen sistem ayarlarını kontrol edin.') % err_msg)

        picking_vals = ArizaTeslimAlService._build_picking_vals(ariza, kaynak_konum, hedef_konum, picking_type)
        tamir_alim_transfer = ariza.env['stock.picking'].sudo().create(picking_vals)

        driver_id = ariza._get_default_driver_id()
        from . import ariza_transfer_service
        ariza_transfer_service.ArizaTransferService.assign_driver(
            tamir_alim_transfer, driver_id, ariza.name
        )

        ArizaTeslimAlService._create_move_and_line(ariza, tamir_alim_transfer, kaynak_konum, hedef_konum)

        ariza.state = ArizaStates.TAMAMLANDI
        ariza.teslim_alan = ariza.env.user.name
        ariza.teslim_notu = f"Ürün {fields.Datetime.now().strftime('%d.%m.%Y %H:%M')} tarihinde teslim alındı. Tamir Alımlar transferi oluşturuldu."

        transfer_bilgisi = f"""
        <p><strong>Yeni transfer oluşturuldu!</strong></p>
        <p><strong>Transfer No:</strong> <a href="/web#id={tamir_alim_transfer.id}&model=stock.picking&view_type=form">{tamir_alim_transfer.name}</a></p>
        <p><strong>Kaynak:</strong> {kaynak_konum.name}</p>
        <p><strong>Hedef:</strong> {hedef_konum.name}</p>
        <p><strong>Tarih:</strong> {fields.Datetime.now().strftime('%Y-%m-%d')}</p>
        <p><strong>Durum:</strong> {tamir_alim_transfer.state}</p>
        <p><strong>SMS Gönderildi:</strong> Deaktif</p>
        """
        ariza.message_post(
            body=transfer_bilgisi,
            subject="Mağaza Ürünü Teslim Alındı - Tamir Alımlar Transferi Oluşturuldu",
            message_type='notification'
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': tamir_alim_transfer.id,
            'view_mode': 'form',
            'context': {'hide_note': True},
            'target': 'current',
        }

    @staticmethod
    def _is_ariza_stok(hedef_konum):
        hedef_complete = (hedef_konum.complete_name or '').strip()
        hedef_upper = hedef_complete.upper()
        return 'ARIZA/STOK' in hedef_upper or 'Arıza/Stok' in hedef_complete

    @staticmethod
    def _get_tamir_alim_picking_type(ariza, kaynak_konum, hedef_konum, ilk_transfer):
        is_ariza_stok = ArizaTeslimAlService._is_ariza_stok(hedef_konum)
        picking_type = False

        if is_ariza_stok:
            picking_type = ariza.env['stock.picking.type'].search([
                ('default_location_dest_id', '=', hedef_konum.id),
                ('name', 'ilike', 'Tamir Alımlar')
            ], limit=1)
            if not picking_type and ilk_transfer.picking_type_id and ilk_transfer.picking_type_id.warehouse_id:
                wh = ilk_transfer.picking_type_id.warehouse_id
                picking_type = ariza.env['stock.picking.type'].search([
                    ('name', 'ilike', 'Arıza'),
                    ('name', 'ilike', 'Tamir Alımlar'),
                    ('warehouse_id', '=', wh.id)
                ], limit=1)
            if not picking_type:
                picking_type = ariza.env['stock.picking.type'].search([
                    ('name', 'ilike', 'Arıza'),
                    ('name', 'ilike', 'Tamir Alımlar')
                ], limit=1)

        if not picking_type and not is_ariza_stok:
            magaza_adi = ""
            if ariza.analitik_hesap_id and ariza.analitik_hesap_id.name:
                magaza_adi = ariza.analitik_hesap_id.name
                if magaza_adi.startswith("Perakende - "):
                    magaza_adi = magaza_adi[MagicNumbers.PERAKENDE_PREFIX_LENGTH:]
            depo_arama_adi = magaza_adi
            if magaza_adi and magaza_adi.lower() in ['temaworld', 'tema world']:
                depo_arama_adi = 'Tema World'
            warehouse = ariza.env['stock.warehouse'].search([
                ('name', 'ilike', depo_arama_adi)
            ], limit=1) if depo_arama_adi else False

            if warehouse:
                picking_type = ariza.env['stock.picking.type'].search([
                    ('name', '=', 'Tamir Alımlar'),
                    ('name', 'not ilike', 'Arıza:'),
                    ('warehouse_id', '=', warehouse.id)
                ], limit=1)
            if not picking_type:
                picking_type = ariza.env['stock.picking.type'].search([
                    ('name', '=', 'Tamir Alımlar'),
                    ('name', 'not ilike', 'Arıza:')
                ], limit=1)

        return picking_type

    @staticmethod
    def _build_picking_vals(ariza, kaynak_konum, hedef_konum, picking_type):
        vals = {
            'picking_type_id': picking_type.id,
            'location_id': kaynak_konum.id,
            'location_dest_id': hedef_konum.id,
            'origin': ariza.name,
            'analytic_account_id': ariza.analitik_hesap_id.id if ariza.analitik_hesap_id else False,
            'scheduled_date': fields.Datetime.now(),
            'date': fields.Datetime.now(),
        }
        partner_id = ArizaTeslimAlService._get_partner_for_tamir_alim(ariza)
        if partner_id:
            vals['partner_id'] = partner_id
        return vals

    @staticmethod
    def _get_partner_for_tamir_alim(ariza):
        if ariza.teknik_servis == TeknikServis.TEDARIKCI and ariza.tedarikci_id:
            return ariza.tedarikci_id.id
        if ariza.teknik_servis == TeknikServis.DTL_BEYOGLU:
            dtl = ariza.env['res.partner'].search([('name', 'ilike', PartnerNames.DTL_ELEKTRONIK)], limit=1)
            return dtl.id if dtl else None
        if ariza.teknik_servis == TeknikServis.DTL_OKMEYDANI:
            dtl = ariza.env['res.partner'].search([('name', 'ilike', PartnerNames.DTL_ELEKTRONIK)], limit=1)
            if dtl:
                okm = ariza.env['res.partner'].search([
                    ('parent_id', '=', dtl.id),
                    ('name', 'ilike', TeknikServis.DTL_OKMEYDANI)
                ], limit=1)
                return (okm or dtl).id
            return None
        if ariza.teknik_servis == TeknikServis.ZUHAL_ARIZA_DEPO:
            zuhal = ariza.env['res.partner'].search([('name', 'ilike', PartnerNames.ZUHAL_DIS_TICARET)], limit=1)
            if zuhal:
                ariza_depo = ariza.env['res.partner'].search([
                    ('parent_id', '=', zuhal.id),
                    ('name', 'ilike', 'Arıza Depo')
                ], limit=1)
                return (ariza_depo or zuhal).id
            return None
        if ariza.teknik_servis == TeknikServis.ZUHAL_NEFESLI:
            zuhal = ariza.env['res.partner'].search([('name', 'ilike', PartnerNames.ZUHAL_DIS_TICARET)], limit=1)
            if zuhal:
                nefesli = ariza.env['res.partner'].search([
                    ('parent_id', '=', zuhal.id),
                    ('name', 'ilike', 'Nefesli Arıza')
                ], limit=1)
                return (nefesli or zuhal).id
            return None
        return None

    @staticmethod
    def _create_move_and_line(ariza, picking, kaynak_konum, hedef_konum):
        product = ariza.magaza_urun_id
        if not product or not product.uom_id:
            raise UserError(f"Transfer satırı oluşturulamadı: Ürün veya birim bilgisi eksik! Ürün: {product.name if product else 'Seçili değil'}")
        move_vals = {
            'name': f"{product.name or 'Bilinmeyen Ürün'} - {ariza.name}",
            'product_id': product.id,
            'product_uom_qty': 1.0,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'location_id': kaynak_konum.id,
            'location_dest_id': hedef_konum.id,
        }
        move = ariza.env['stock.move'].sudo().create(move_vals)
        move_line_vals = {
            'move_id': move.id,
            'product_id': product.id,
            'product_uom_id': product.uom_id.id,
            'qty_done': 1.0,
            'location_id': kaynak_konum.id,
            'location_dest_id': hedef_konum.id,
            'picking_id': picking.id,
        }
        ariza.env['stock.move.line'].sudo().create(move_line_vals)
