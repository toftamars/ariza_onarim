from odoo import models, fields, api, _

class ArizaKayitTamamlaWizard(models.TransientModel):
    _name = 'ariza.kayit.tamamla.wizard'
    _description = 'Arıza Kaydı Tamamlama Sihirbazı'

    ariza_id = fields.Many2one('ariza.kayit', string='Arıza Kaydı', required=True)
    musteri_adi = fields.Char(string='Müşteri Adı', readonly=True)
    urun = fields.Char(string='Ürün', readonly=True)
    ariza_tipi = fields.Selection([
        ('musteri', 'Müşteri Ürünü'),
        ('magaza', 'Mağaza Ürünü'),
        ('teknik', 'Teknik Servis Ürünü')
    ], string='Arıza Tipi', readonly=True)
    onarim_bilgisi = fields.Text(string='Onarım Bilgisi', required=True)
    garanti_kapsaminda_mi = fields.Selection([
        ('evet', 'Evet'),
        ('hayir', 'Hayır'),
    ], string='Garanti Kapsamında mı?', required=True)
    ucret_bilgisi = fields.Char(string='Ücret Bilgisi')
    teslim_magazasi_id = fields.Many2one('account.analytic.account', string='Teslim Mağazası', required=True)
    teslim_adresi = fields.Char(string='Teslim Adresi', readonly=True)
    teslim_tarihi = fields.Date(string='Teslim Tarihi', required=True, default=fields.Date.context_today)
    teslim_saati = fields.Float(string='Teslim Saati', required=True)
    teslim_eden = fields.Many2one('res.users', string='Teslim Eden', required=True, default=lambda self: self.env.user)
    teslim_alan = fields.Char(string='Teslim Alan', required=True)
    teslim_alan_tc = fields.Char(string='Teslim Alan TC', required=True)
    teslim_alan_telefon = fields.Char(string='Teslim Alan Telefon', required=True)
    teslim_alan_imza = fields.Binary(string='Teslim Alan İmza', required=True)
    teslim_eden_imza = fields.Binary(string='Teslim Eden İmza', required=True)
    teslim_notu = fields.Text(string='Teslim Notu')
    teslim_durumu = fields.Selection([
        ('tamamlandi', 'Tamamlandı'),
        ('iptal', 'İptal'),
        ('beklemede', 'Beklemede')
    ], string='Teslim Durumu', required=True, default='tamamlandi')
    sms_gonderildi_wizard = fields.Boolean(string='SMS Gönderildi', readonly=True, default=False)

    @api.onchange('teslim_magazasi_id')
    def _onchange_teslim_magazasi(self):
        if self.teslim_magazasi_id and self.teslim_magazasi_id.name in ['DTL OKMEYDANI', 'DTL BEYOĞLU']:
            self.teslim_adresi = 'MAHMUT ŞEVKET PAŞA MAH. ŞAHİNKAYA SOK NO 31 OKMEYDANI'
        else:
            self.teslim_adresi = False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self._context.get('active_id'):
            ariza = self.env['ariza.kayit'].browse(self._context['active_id'])
            res.update({
                'ariza_id': ariza.id,
                'musteri_adi': ariza.partner_id.name,
                'urun': ariza.urun,
                'ariza_tipi': ariza.ariza_tipi,
                'teslim_magazasi_id': ariza.teslim_magazasi_id.id,
                'teslim_adresi': ariza.teslim_adresi,
            })
        return res

    def action_tamamla(self):
        self.ariza_id.write({
            'state': 'tamamlandi',
            'onarim_bilgisi': self.onarim_bilgisi,
            'garanti_kapsaminda_mi': self.garanti_kapsaminda_mi,
            'ucret_bilgisi': self.ucret_bilgisi,
            'teslim_magazasi_id': self.teslim_magazasi_id.id,
        })
        # SMS gönderimi
        sms_gonderildi = False
        if self.ariza_id.ariza_tipi == 'musteri' and self.ariza_id.partner_id and self.ariza_id.partner_id.phone:
            sms_mesaji = f"Sayın {self.ariza_id.partner_id.name} {self.ariza_id.name}, {self.ariza_id.urun} ürününüz teslim edilmeye hazırdır. Ürününüzü {self.teslim_magazasi_id.name} mağazamızdan teslim alabilirsiniz."
            self.ariza_id._send_sms_to_customer(sms_mesaji)
            sms_gonderildi = True
        self.sms_gonderildi_wizard = sms_gonderildi
        return {'type': 'ir.actions.act_window_close'} 