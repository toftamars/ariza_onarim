# -*- coding: utf-8 -*-
"""
Onarım Bilgi Wizard - Onarım bilgileri girişi için wizard
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..models.ariza_constants import SMSTemplates, TeslimAlan

class ArizaOnarimBilgiWizard(models.TransientModel):
    _name = 'ariza.onarim.bilgi.wizard'
    _description = 'Onarım Bilgilerini Doldurma Sihirbazı'

    ariza_id = fields.Many2one('ariza.kayit', string='Arıza Kaydı', required=True)
    partner_id = fields.Many2one('res.partner', string='Müşteri', readonly=True)
    musteri_adi = fields.Char(string='Müşteri Adı', readonly=True)
    urun = fields.Char(string='Ürün', readonly=True)
    ariza_tipi = fields.Selection([
        ('musteri', 'Müşteri Ürünü'),
        ('magaza', 'Mağaza Ürünü')
    ], string='Arıza Tipi', readonly=True)
    teslim_magazasi_id = fields.Many2one('account.analytic.account', string='Teslim Mağazası')
    adresime_gonderilsin = fields.Boolean(string='Adresime Gönderilsin', default=False)
    musteri_adresi_id = fields.Many2one('res.partner', string='Teslimat Adresi', 
                                       domain="[('type', 'in', ['delivery', 'contact'])]",
                                       attrs="{'invisible': [('adresime_gonderilsin', '=', False)], 'required': [('adresime_gonderilsin', '=', True)]}",
                                       context="{'default_type': 'delivery'}")
    onarim_bilgisi = fields.Text(string='Onarım Bilgisi', required=True)
    garanti_kapsaminda_mi = fields.Selection([
        ('evet', 'Evet'),
        ('hayir', 'Hayır'),
        ('urun_degisimi', 'Ürün Değişimi'),
    ], string='Garanti Kapsamında mı?', required=True)
    ucret_bilgisi = fields.Char(string='Ücret Bilgisi')
    onarim_ucreti = fields.Monetary(string='Onarım Ücreti', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Para Birimi', default=lambda self: self.env.company.currency_id)
    


    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self._context.get('active_id'):
            ariza = self.env['ariza.kayit'].browse(self._context['active_id'])
            res.update({
                'ariza_id': ariza.id,
                'partner_id': ariza.partner_id.id if ariza.partner_id else False,
                'musteri_adi': ariza.partner_id.name if ariza.partner_id else '',
                'urun': ariza.urun if ariza.urun else '',
                'ariza_tipi': ariza.ariza_tipi,
                'teslim_magazasi_id': ariza.teslim_magazasi_id.id if ariza.teslim_magazasi_id else False,
            })
            

        return res

    def _temizle_magaza_adi(self, magaza_adi):
        """Mağaza adından 'Perakende' ifadesini kaldır"""
        if magaza_adi:
            # "Perakende" ifadesini kaldır
            temiz_adi = magaza_adi.replace('Perakende ', '').replace(' Perakende', '')
            return temiz_adi
        return magaza_adi

    def action_onarim_bilgilerini_kaydet(self):
        """Onarım bilgilerini kaydet ve durumu güncelle"""
        ariza = self.ariza_id
        
        # Onarım bilgilerini güncelle
        ariza.onarim_bilgisi = self.onarim_bilgisi
        ariza.garanti_kapsaminda_mi = self.garanti_kapsaminda_mi
        ariza.ucret_bilgisi = self.ucret_bilgisi
        
        # Garanti kapsamında olan durumlarda onarım ücreti sıfırla
        if self.garanti_kapsaminda_mi in ['evet', 'urun_degisimi']:
            ariza.onarim_ucreti = 0.0
        else:
            ariza.onarim_ucreti = self.onarim_ucreti
        
        # Teslim mağazasını güncelle (müşteri ürünü için)
        if self.ariza_tipi == 'musteri':
            if self.adresime_gonderilsin and self.musteri_adresi_id:
                # Adrese gönderim seçildi
                ariza.teslim_magazasi_id = False
                ariza.teslim_adresi = self.musteri_adresi_id.street or ''
            elif self.teslim_magazasi_id:
                # Mağazadan teslim seçildi
                ariza.teslim_magazasi_id = self.teslim_magazasi_id.id
        
        # Durumu güncelle - Mağaza ürünü için yönetici tamamlandı, müşteri ürünü için normal akış
        if self.ariza_tipi == 'magaza':
            ariza.state = 'yonetici_tamamlandi'
        elif self.ariza_tipi == 'musteri' and self.adresime_gonderilsin and self.musteri_adresi_id:
            ariza.state = 'teslim_edildi'
            # Adrese gönderim için teslim bilgilerini güncelle
            ariza.teslim_alan = TeslimAlan.ADRESE_GONDERIM
            ariza.teslim_adresi = self.musteri_adresi_id.street or ''
            
            # Adrese gönderim için SMS gönder (Üçüncü SMS)
            if ariza.partner_id and ariza.partner_id.phone and not ariza.ucuncu_sms_gonderildi:
                from datetime import datetime
                teslim_tarihi = datetime.now().strftime("%d.%m.%Y %H:%M")
                
                message = SMSTemplates.ADRESE_GONDERIM_SMS.format(
                    musteri_adi=ariza.partner_id.name or '',
                    urun=ariza.urun or '',
                    teslim_tarihi=teslim_tarihi,
                    kayit_no=ariza.name or ''
                )
                
                if ariza.garanti_kapsaminda_mi in ['evet', 'urun_degisimi']:
                    message += SMSTemplates.GARANTI_EKLENTISI
                
                ariza._send_sms_to_customer(message)
                ariza.ucuncu_sms_gonderildi = True
        else:
            ariza.state = 'tamamlandi'
        
        # SMS gönderimi - Müşteri ürünü için 2. SMS kaldırıldı (Yönetici Onarımı Tamamla ve SMS Gönder butonu için)
        # Diğer SMS akışları (ilk SMS, üçüncü SMS) korunuyor
        

        
        # Mağaza ürünü işlemleri için 2. transfer artık kullanıcı "Teslim AL" butonuna bastığında oluşacak
        
        # Mesaj gönder
        if ariza.ariza_tipi == 'musteri' and self.adresime_gonderilsin and self.musteri_adresi_id:
            ariza.message_post(
                body=f"Onarım süreci tamamlandı. Onarım bilgileri kaydedildi. Adrese gönderim seçildi. Durum otomatik olarak 'Teslim Edildi' olarak güncellendi.",
                subject="Onarım Tamamlandı - Adrese Gönderim"
            )
        elif ariza.ariza_tipi == 'magaza':
            ariza.message_post(
                body=f"Yönetici onarım sürecini tamamladı. Onarım bilgileri kaydedildi. Kullanıcı 'Teslim AL' butonuna basarak Tamir Alımlar transferini oluşturabilir.",
                subject="Yönetici Onarım Tamamlandı - Kullanıcı Teslim AL Bekleniyor"
            )
        else:
            ariza.message_post(
                body=f"Onarım süreci tamamlandı. Onarım bilgileri kaydedildi. Kullanıcı Teslim Et butonuna basarak geri gönderim transferini oluşturabilir.",
                subject="Onarım Tamamlandı"
            )
        
        return {'type': 'ir.actions.act_window_close'} 