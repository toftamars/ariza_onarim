from odoo import models, fields, api, _
from odoo.exceptions import UserError

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
                                       domain="[('parent_id', '=', partner_id), ('type', '=', 'delivery')]",
                                       attrs="{'invisible': [('adresime_gonderilsin', '=', False)], 'required': [('adresime_gonderilsin', '=', True)]}")
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
        
        # Durumu tamamlandı olarak güncelle
        ariza.state = 'tamamlandi'
        
        # SMS gönderimi - Müşteriye onarım tamamlandı bilgisi (İkinci SMS)
        if ariza.partner_id and ariza.partner_id.phone and not ariza.ikinci_sms_gonderildi:
            if ariza.ariza_tipi == 'musteri':
                # Müşteri ürünü için onarım tamamlandı SMS'i
                if self.adresime_gonderilsin and self.musteri_adresi_id:
                    # Adrese gönderim
                    sms_mesaji = f"Sayın {ariza.partner_id.name}. {ariza.name}, {ariza.urun} ürününüzün onarımı tamamlanmıştır. Ürününüz adresinize gönderilecektir. B021"
                else:
                    # Mağazadan teslim
                    magaza_adi = self.teslim_magazasi_id.name if self.teslim_magazasi_id else ''
                    temiz_magaza_adi = self._temizle_magaza_adi(magaza_adi)
                    sms_mesaji = f"Sayın {ariza.partner_id.name}. {ariza.name}, {ariza.urun} ürününüzün onarımı tamamlanmıştır. Ürününüzü {temiz_magaza_adi} mağazamızdan teslim alabilirsiniz. B021"
            else:
                # Mağaza ürünü için onarım tamamlandı SMS'i
                sms_mesaji = f"Sayın {ariza.partner_id.name}. {ariza.name}, {ariza.urun} ürününüzün onarımı tamamlanmıştır. B021"
            
            ariza._send_sms_to_customer(sms_mesaji)
            # Müşteriye e-posta gönder
            if ariza.partner_id and ariza.partner_id.email:
                ariza._send_email_to_customer("Ürününüz Teslim Edilmeye Hazır", sms_mesaji)
            ariza.ikinci_sms_gonderildi = True
        
        # Mesaj gönder
        ariza.message_post(
            body=f"Onarım süreci tamamlandı. Onarım bilgileri kaydedildi. Müşteriye SMS gönderildi. Kullanıcı Teslim Et butonuna basarak geri gönderim transferini oluşturabilir.",
            subject="Onarım Tamamlandı"
        )
        
        return {'type': 'ir.actions.act_window_close'} 