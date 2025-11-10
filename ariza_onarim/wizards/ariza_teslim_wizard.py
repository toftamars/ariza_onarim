# -*- coding: utf-8 -*-
"""
Teslim Wizard - Ürün teslim işlemi için wizard
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..models.ariza_constants import SMSTemplates, TeslimAlan

class ArizaTeslimWizard(models.TransientModel):
    _name = 'ariza.teslim.wizard'
    _description = 'Teslim Alan Bilgisi Girme Sihirbazı'

    ariza_id = fields.Many2one('ariza.kayit', string='Arıza Kaydı', required=True)
    musteri_adi = fields.Char(string='Müşteri Adı', readonly=True)
    urun = fields.Char(string='Ürün', readonly=True)
    teslim_alan = fields.Char(string='Teslim Alan Kişi', required=True)
    onarim_ucreti = fields.Monetary(string='Onarım Ücreti', currency_field='currency_id', readonly=True, compute='_compute_onarim_ucreti')
    currency_id = fields.Many2one('res.currency', string='Para Birimi', compute='_compute_onarim_ucreti')
    odeme_tamamlandi = fields.Selection([
        ('evet', 'Evet'),
        ('hayir', 'Hayır'),
    ], string='Ödeme Tamamlandı', required=False)
    
    @api.depends('ariza_id')
    def _compute_onarim_ucreti(self):
        for record in self:
            if record.ariza_id:
                record.onarim_ucreti = record.ariza_id.onarim_ucreti or 0.0
                record.currency_id = record.ariza_id.currency_id or self.env.company.currency_id
            else:
                record.onarim_ucreti = 0.0
                record.currency_id = self.env.company.currency_id

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self._context.get('active_id'):
            ariza = self.env['ariza.kayit'].browse(self._context['active_id'])
            res.update({
                'ariza_id': ariza.id,
                'musteri_adi': ariza.partner_id.name if ariza.partner_id else '',
                'urun': ariza.urun if ariza.urun else '',
            })
        return res

    def action_teslim_et(self):
        """Teslim işlemini gerçekleştir"""
        ariza = self.ariza_id
        
        # Onarım ücreti varsa ödeme kontrolü yap
        if ariza.onarim_ucreti and ariza.onarim_ucreti > 0:
            if not self.odeme_tamamlandi:
                raise UserError(_('Onarım ücreti bulunan kayıtlar için "Ödeme Tamamlandı" alanı zorunludur!'))
            if self.odeme_tamamlandi == 'hayir':
                raise UserError(_('Ödeme tamamlanmadan teslim işlemi yapılamaz! Lütfen önce ödemeyi tamamlayın.'))
        
        # Teslim bilgilerini güncelle
        ariza.teslim_alan = self.teslim_alan
        
        # Durumu teslim edildi yap
        ariza.state = 'teslim_edildi'
        
        # Teslim edildi SMS'i gönder (Üçüncü SMS)
        if ariza.ariza_tipi == 'musteri' and ariza.partner_id and ariza.partner_id.phone and not ariza.ucuncu_sms_gonderildi:
            # Tarih ve saat bilgisini al
            from datetime import datetime
            teslim_tarihi = datetime.now().strftime("%d.%m.%Y %H:%M")
            
            # Adrese Gönderim seçildiyse özel SMS template kullan
            if self.teslim_alan == TeslimAlan.ADRESE_GONDERIM:
                message = SMSTemplates.ADRESE_GONDERIM_SMS.format(
                    musteri_adi=ariza.partner_id.name or '',
                    urun=ariza.urun or '',
                    teslim_tarihi=teslim_tarihi,
                    kayit_no=ariza.name or ''
                )
            else:
                # Mağazadan teslim - normal SMS template
                magaza_adi = ariza.teslim_magazasi_id.name if ariza.teslim_magazasi_id else ''
                temiz_magaza_adi = ariza._clean_magaza_adi(magaza_adi)
                
                # Teslim edilen kişi bilgisini al
                teslim_edilen_kisi = self.teslim_alan if self.teslim_alan else "müşteriye"
                
                message = SMSTemplates.UCUNCU_SMS.format(
                    musteri_adi=ariza.partner_id.name or '',
                    urun=ariza.urun or '',
                    magaza_adi=temiz_magaza_adi or '',
                    teslim_tarihi=teslim_tarihi,
                    teslim_alan_kisi=teslim_edilen_kisi,
                    kayit_no=ariza.name or ''
                )
            
            if ariza.garanti_kapsaminda_mi in ['evet', 'urun_degisimi']:
                message += SMSTemplates.GARANTI_EKLENTISI
            ariza._send_sms_to_customer(message)
            ariza.ucuncu_sms_gonderildi = True
        
        # Chatter'a mesaj ekle (mail gönderilmesin)
        ariza.message_post(
            body=f"Ürün teslim edildi. Teslim alan: {self.teslim_alan}. SMS gönderildi.",
            subject="Ürün Teslim Edildi",
            message_type='notification'
        )
        
        return {'type': 'ir.actions.act_window_close'} 