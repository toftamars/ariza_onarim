# -*- coding: utf-8 -*-
"""
Arıza Print Service - Yazdırma işlemleri
"""

from odoo import _
from odoo.exceptions import UserError

from ..ariza_constants import ArizaTipi


class ArizaPrintService:
    """Arıza yazdırma işlemleri"""

    @staticmethod
    def action_print(record):
        """
        Arıza kayıt raporunu yazdırır (TEK BELGE).

        Kargo barkod şeridi rapora gömülüdür (report_ariza_kayit.xml):
        Aras barkodu oluşmuşsa formun üstünde basılır, ayrıca Kargo Çıktısı
        almaya gerek kalmaz.
        """
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
        # Öncelik: iade kargosu (dönüş ayağı); yoksa teknik servise gidiş kargosu
        picking = record.iade_transfer_id or record.transfer_id
        if not picking or picking.state == 'cancel':
            raise UserError(_(
                'Kargo çıktısı basılamaz: Bu kayıt için henüz kargo transferi yok.\n\n'
                'Gidiş kargosu ONAYLA adımında (kargo metodu seçiliyse), iade kargosu '
                'teslim adımında "Adrese Gönderilsin" seçildiğinde otomatik oluşturulur.'
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
        """Kargo Çıktısı raporunu basar (A5 veya A4, modülün kendi şablonu)"""
        # Önce picking/barkod kontrolü: yoksa yönlendiren UserError fırlatır
        ArizaPrintService._get_iade_picking(record)
        xmlid = ('ariza_onarim.action_report_kargo_ciktisi_a4' if a4
                 else 'ariza_onarim.action_report_kargo_ciktisi')
        return record.env.ref(xmlid).report_action(record)
