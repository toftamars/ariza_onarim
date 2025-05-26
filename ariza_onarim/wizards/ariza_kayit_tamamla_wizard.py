from odoo import models, fields, api, _

class ArizaKayitTamamlaWizard(models.TransientModel):
    _name = 'ariza.kayit.tamamla.wizard'
    _description = 'Arıza Kaydı Tamamlama'

    ariza_id = fields.Many2one('ariza.kayit', string='Arıza Kaydı', required=True)
    musteri_adi = fields.Char(string='Müşteri Adı', readonly=True)
    urun = fields.Char(string='Ürün', readonly=True)
    onarim_bilgisi = fields.Text(string='Onarım Bilgisi', required=True)
    garanti_kapsaminda_mi = fields.Selection([
        ('evet', 'Evet'),
        ('hayir', 'Hayır'),
    ], string='Garanti Kapsamında mı?', required=True)
    ucret_bilgisi = fields.Char(string='Ücret Bilgisi')
    teslim_magazasi_id = fields.Many2one('account.analytic.account', string='Teslim Mağazası', required=True)
    teslim_magazasi_adi = fields.Char(string='Mağaza Adı', compute='_compute_teslim_magazasi_adi')

    @api.onchange('teslim_magazasi_id')
    def _onchange_teslim_magazasi_id(self):
        if self.teslim_magazasi_id:
            # Perakende ifadesini kaldır
            self.teslim_magazasi_id.name = self.teslim_magazasi_id.name.replace('Perakende ', '')

    @api.depends('teslim_magazasi_id')
    def _compute_teslim_magazasi_adi(self):
        for rec in self:
            name = rec.teslim_magazasi_id.name or ''
            if '-' in name:
                rec.teslim_magazasi_adi = name.split('-')[-1].strip().split()[0]
            else:
                rec.teslim_magazasi_adi = name.split()[-1] if name else ''

    def action_tamamla(self):
        self.ariza_id.write({
            'state': 'tamamlandi',
            'onarim_bilgisi': self.onarim_bilgisi,
            'garanti_kapsaminda_mi': self.garanti_kapsaminda_mi,
            'ucret_bilgisi': self.ucret_bilgisi,
            'teslim_magazasi_id': self.teslim_magazasi_id.id,
        })
        # SMS gönderimi
        if self.ariza_id.ariza_tipi == 'musteri' and self.ariza_id.partner_id and self.ariza_id.partner_id.phone:
            sms_mesaji = f"Sayın {self.ariza_id.partner_id.name} {self.ariza_id.name}, {self.ariza_id.urun} ürününüz teslim edilmeye hazırdır. Ürününüzü {self.teslim_magazasi_id.name} mağazamızdan teslim alabilirsiniz."
            self.ariza_id._send_sms_to_customer(sms_mesaji)
        return {'type': 'ir.actions.act_window_close'} 