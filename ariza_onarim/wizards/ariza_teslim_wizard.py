from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ArizaTeslimWizard(models.TransientModel):
    _name = 'ariza.teslim.wizard'
    _description = 'Teslim Alan Bilgisi Girme Sihirbazı'

    ariza_id = fields.Many2one('ariza.kayit', string='Arıza Kaydı', required=True)
    musteri_adi = fields.Char(string='Müşteri Adı', readonly=True)
    urun = fields.Char(string='Ürün', readonly=True)
    teslim_alan = fields.Char(string='Teslim Alan Kişi', required=True)
    teslim_alan_tc = fields.Char(string='Teslim Alan TC')
    teslim_alan_telefon = fields.Char(string='Teslim Alan Telefon')
    teslim_notu = fields.Text(string='Teslim Notu')

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
        
        # Teslim bilgilerini güncelle
        ariza.teslim_alan = self.teslim_alan
        ariza.teslim_alan_tc = self.teslim_alan_tc
        ariza.teslim_alan_telefon = self.teslim_alan_telefon
        ariza.teslim_notu = self.teslim_notu
        
        # Durumu teslim edildi yap
        ariza.state = 'teslim_edildi'
        
        # Teslim edildi SMS'i gönder (Üçüncü SMS)
        if ariza.ariza_tipi == 'musteri' and ariza.partner_id and ariza.partner_id.phone and not ariza.ucuncu_sms_gonderildi:
            # Mağaza adını temizle
            magaza_adi = ariza.teslim_magazasi_id.name if ariza.teslim_magazasi_id else ''
            temiz_magaza_adi = ariza._clean_magaza_adi(magaza_adi)
            
            # Tarih ve saat bilgisini al
            from datetime import datetime
            teslim_tarihi = datetime.now().strftime("%d.%m.%Y %H:%M")
            
            # Teslim edilen kişi bilgisini al
            teslim_edilen_kisi = self.teslim_alan if self.teslim_alan else "müşteriye"
            
            message = f"Sayın {ariza.partner_id.name}. {ariza.urun} ürününüz {temiz_magaza_adi} mağazamızdan {teslim_tarihi} tarihinde {teslim_edilen_kisi} teslim edilmiştir. B021"
            ariza._send_sms_to_customer(message)
            ariza.ucuncu_sms_gonderildi = True
        
        # Teslim edildi e-posta gönder
        mail_to = 'alper.tofta@zuhalmuzik.com'
        subject = f"Ürün Teslim Edildi: {ariza.name}"
        body = f"""
Ürün Teslim Edildi.<br/>
<b>Arıza No:</b> {ariza.name}<br/>
<b>Müşteri:</b> {ariza.partner_id.name if ariza.partner_id else '-'}<br/>
<b>Ürün:</b> {ariza.urun}<br/>
<b>Model:</b> {ariza.model}<br/>
<b>Arıza Tanımı:</b> {ariza.ariza_tanimi or '-'}<br/>
<b>Tarih:</b> {ariza.tarih or '-'}<br/>
<b>Teknik Servis:</b> {ariza.teknik_servis or '-'}<br/>
<b>Teknik Servis Adresi:</b> {ariza.teknik_servis_adres or '-'}<br/>
<b>Teslim Alan:</b> {self.teslim_alan}<br/>
<b>Teslim Alan TC:</b> {self.teslim_alan_tc or '-'}<br/>
<b>Teslim Alan Telefon:</b> {self.teslim_alan_telefon or '-'}<br/>
<b>Teslim Notu:</b> {self.teslim_notu or '-'}<br/>
"""
        ariza.env['mail.mail'].create({
            'subject': subject,
            'body_html': body,
            'email_to': mail_to,
        }).send()
        
        # Chatter'a mesaj ekle
        ariza.message_post(
            body=f"Ürün teslim edildi. Teslim alan: {self.teslim_alan}. SMS gönderildi.",
            subject="Ürün Teslim Edildi"
        )
        
        return {'type': 'ir.actions.act_window_close'} 