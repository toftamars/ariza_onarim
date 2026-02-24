# -*- coding: utf-8 -*-
"""
Arıza Print Service - Yazdırma işlemleri
"""

from odoo import _
from odoo.exceptions import UserError

from ..ariza_constants import TransferMetodu


class ArizaPrintService:
    """Arıza yazdırma işlemleri"""

    @staticmethod
    def action_print(record):
        """Arıza kaydı veya kargo çıktısı yazdır"""
        if record.transfer_metodu in [TransferMetodu.UCRETSIZ_KARGO, TransferMetodu.UCRETLI_KARGO] and record.transfer_id:
            kargo_a4_report = record.env['ir.actions.report'].search([
                ('model', '=', 'stock.picking'),
                ('report_name', '=', 'stock_picking.x_kargo_ciktisi_listesi_A4')
            ], limit=1)
            if kargo_a4_report:
                return kargo_a4_report.report_action(record.transfer_id)
            return record.env.ref('stock.action_report_delivery').report_action(record.transfer_id)
        teknik_servis_adres = record.teknik_servis_adres
        ctx = dict(record.env.context)
        ctx['teknik_servis_adres'] = teknik_servis_adres
        return record.env.ref('ariza_onarim.action_report_ariza_kayit').with_context(ctx).report_action(record)

    @staticmethod
    def action_print_invoice(record):
        """Fatura kalemine ait faturayı form view olarak açar"""
        if not record.invoice_line_id:
            raise UserError(_('Fatura kalemi seçilmemiş!'))
        invoice = record.invoice_line_id.move_id
        if not invoice:
            raise UserError(_('Fatura kalemine ait fatura bulunamadı!'))
        return {
            'type': 'ir.actions.act_window',
            'name': f'Fatura - {invoice.name}',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @staticmethod
    def action_print_delivery(record):
        """Transfer irsaliyesi yazdır"""
        if record.transfer_id:
            return record.env.ref('stock.action_report_delivery').report_action(record.transfer_id)
