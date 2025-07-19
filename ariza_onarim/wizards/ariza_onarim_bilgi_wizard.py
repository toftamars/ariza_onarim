from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ArizaOnarimBilgiWizard(models.TransientModel):
    _name = 'ariza.onarim.bilgi.wizard'
    _description = 'Onarım Bilgilerini Doldurma Sihirbazı'

    ariza_id = fields.Many2one('ariza.kayit', string='Arıza Kaydı', required=True)
    musteri_adi = fields.Char(string='Müşteri Adı', readonly=True)
    urun = fields.Char(string='Ürün', readonly=True)
    teslim_magazasi_id = fields.Many2one('account.analytic.account', string='Teslim Mağazası')
    onarim_bilgisi = fields.Text(string='Onarım Bilgisi', required=True)
    garanti_kapsaminda_mi = fields.Selection([
        ('evet', 'Evet'),
        ('hayir', 'Hayır'),
    ], string='Garanti Kapsamında mı?', required=True)
    ucret_bilgisi = fields.Char(string='Ücret Bilgisi')
    onarim_ucreti = fields.Float(string='Onarım Ücreti')

    def action_onarim_bilgilerini_kaydet(self):
        """Onarım bilgilerini kaydet ve durumu güncelle"""
        ariza = self.ariza_id
        
        # Onarım bilgilerini güncelle
        ariza.onarim_bilgisi = self.onarim_bilgisi
        ariza.garanti_kapsaminda_mi = self.garanti_kapsaminda_mi
        ariza.ucret_bilgisi = self.ucret_bilgisi
        ariza.onarim_ucreti = self.onarim_ucreti
        
        # Teslim mağazasını güncelle (müşteri ürünü için)
        if self.ariza_tipi == 'musteri' and self.teslim_magazasi_id:
            ariza.teslim_magazasi_id = self.teslim_magazasi_id.id
        
        # Durumu onaylandı olarak güncelle
        ariza.state = 'onaylandi'
        
        # SMS gönderimi - Müşteriye onarım tamamlandı bilgisi
        if ariza.partner_id and ariza.partner_id.phone:
            if ariza.ariza_tipi == 'musteri':
                # Müşteri ürünü için onarım tamamlandı SMS'i
                magaza_adi = self.teslim_magazasi_id.name if self.teslim_magazasi_id else ''
                sms_mesaji = f"Sayın {ariza.partner_id.name}. {ariza.name}, {ariza.urun} ürününüzün onarımı tamamlanmıştır. Ürününüzü {magaza_adi} mağazamızdan teslim alabilirsiniz. B021"
            else:
                # Mağaza ürünü için onarım tamamlandı SMS'i
                sms_mesaji = f"Sayın {ariza.partner_id.name}. {ariza.name}, {ariza.urun} ürününüzün onarımı tamamlanmıştır. B021"
            
            ariza._send_sms_to_customer(sms_mesaji)
        
        # Mesaj gönder
        ariza.message_post(
            body=f"Onarım süreci tamamlandı. Onarım bilgileri kaydedildi. Müşteriye SMS gönderildi. Kullanıcı tamamla butonuna basarak geri gönderim transferini oluşturabilir.",
            subject="Onarım Tamamlandı"
        )
        
        return {'type': 'ir.actions.act_window_close'} 