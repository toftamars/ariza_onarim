# -*- coding: utf-8 -*-
"""
Arıza Print Service - Yazdırma işlemleri
"""

from odoo import _
from odoo.exceptions import UserError

from ..ariza_constants import ArizaTipi, TransferMetodu

# Kargo Çıktısı raporları (Studio kaydı, DB'de tanımlı — repoda değil)
KARGO_CIKTISI_REPORT = 'stock_picking.x_kargo_ciktisi_listesi'
KARGO_CIKTISI_A4_REPORT = 'stock_picking.x_kargo_ciktisi_listesi_A4'


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

    @staticmethod
    def _get_iade_picking(record):
        """
        Müşteri ürününün iade kargo picking'ini döner.

        Picking yoksa veya barkod henüz oluşmadıysa kullanıcıyı yönlendiren
        UserError fırlatır (yazdırma işlemi yan etkiyle sevkiyat OLUŞTURMAZ).
        """
        if record.ariza_tipi != ArizaTipi.MUSTERI:
            raise UserError(_('Kargo Çıktısı yalnızca müşteri ürünleri için basılabilir.'))
        picking = record.iade_transfer_id
        if not picking or picking.state == 'cancel':
            raise UserError(_(
                'Kargo çıktısı basılamaz: Bu kayıt için henüz iade kargo transferi yok.\n\n'
                'İade kargosu, teslim adımında "Adrese Gönderilsin" seçildiğinde '
                'otomatik oluşturulur. Önce teslim/gönderim adımını tamamlayın.'
            ))
        if not picking.carrier_tracking_ref:
            raise UserError(_(
                'Kargo çıktısı basılamaz: Aras barkodu henüz oluşmadı.\n\n'
                'Barkod, iade transferi (%s) doğrulandığında (validate) otomatik oluşur. '
                'Lütfen önce transferi doğrulayın.'
            ) % picking.name)
        return picking

    @staticmethod
    def action_print_kargo_ciktisi(record, a4=False):
        """Müşteri ürünü iade kargosunun Kargo Çıktısı raporunu basar (A5 veya A4)"""
        picking = ArizaPrintService._get_iade_picking(record)
        report_name = KARGO_CIKTISI_A4_REPORT if a4 else KARGO_CIKTISI_REPORT
        report = record.env['ir.actions.report'].sudo().search([
            ('model', '=', 'stock.picking'),
            ('report_name', '=', report_name),
        ], limit=1)
        if not report:
            raise UserError(_(
                'Kargo Çıktısı raporu bu sunucuda tanımlı değil: %s\n'
                'Bu rapor Studio kaydıdır; staging/canlı veritabanında bulunmalıdır.'
            ) % report_name)
        return report.report_action(picking)
