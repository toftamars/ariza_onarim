from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ArizaKayitTamamlaWizard(models.TransientModel):
    _name = 'ariza.kayit.tamamla.wizard'
    _description = 'ARIZA KAYIT TAMAMLAMA SİHİRBAZI'

    ariza_id = fields.Many2one('ariza.kayit', string='ARIZA KAYDI', required=True)
    musteri_adi = fields.Char(string='MÜŞTERİ ADI', readonly=True)
    urun = fields.Char(string='ÜRÜN', readonly=True)
    ariza_tipi = fields.Selection([
        ('musteri', 'MÜŞTERİ ÜRÜNÜ'),
        ('magaza', 'MAĞAZA ÜRÜNÜ'),
        ('teknik', 'TEKNİK SERVİS ÜRÜNÜ')
    ], string='ARIZA TİPİ', readonly=True)
    onarim_bilgisi = fields.Text(string='Onarım Bilgisi', required=True)
    garanti_kapsaminda_mi = fields.Selection([
        ('evet', 'Evet'),
        ('hayir', 'Hayır'),
    ], string='Garanti Kapsamında mı?', required=True)
    ucret_bilgisi = fields.Char(string='Ücret Bilgisi')
    teslim_magazasi_id = fields.Many2one('account.analytic.account', string='TESLİM MAĞAZASI', required=True)
    teslim_adresi = fields.Char(string='TESLİM ADRESİ', readonly=True)
    teslim_tarihi = fields.Date(string='TESLİM TARİHİ', required=True, default=fields.Date.context_today)
    teslim_saati = fields.Float(string='TESLİM SAATİ', required=True)
    teslim_eden = fields.Many2one('res.users', string='TESLİM EDEN', required=True, default=lambda self: self.env.user)
    teslim_alan = fields.Char(string='TESLİM ALAN', required=True)
    teslim_alan_tc = fields.Char(string='TESLİM ALAN TC', required=True)
    teslim_alan_telefon = fields.Char(string='TESLİM ALAN TELEFON', required=True)
    teslim_alan_imza = fields.Binary(string='TESLİM ALAN İMZA', required=True)
    teslim_eden_imza = fields.Binary(string='TESLİM EDEN İMZA', required=True)
    teslim_notu = fields.Text(string='TESLİM NOTU')
    teslim_durumu = fields.Selection([
        ('tamamlandi', 'TAMAMLANDI'),
        ('iptal', 'İPTAL'),
        ('beklemede', 'BEKLEMEDE')
    ], string='TESLİM DURUMU', required=True, default='tamamlandi')
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
                'musteri_adi': ariza.partner_id.name.upper() if ariza.partner_id.name else '',
                'urun': ariza.urun.upper() if ariza.urun else '',
                'ariza_tipi': ariza.ariza_tipi,
                'teslim_magazasi_id': ariza.teslim_magazasi_id.id,
                'teslim_adresi': ariza.teslim_adresi.upper() if ariza.teslim_adresi else '',
            })
        return res

    def action_tamamla(self):
        self.ensure_one()
        if self.teslim_durumu == 'tamamlandi':
            self.ariza_id.write({
                'state': 'tamamlandi',
                'teslim_tarihi': self.teslim_tarihi,
                'teslim_saati': self.teslim_saati,
                'teslim_eden': self.teslim_eden.id,
                'teslim_alan': self.teslim_alan.upper() if self.teslim_alan else '',
                'teslim_alan_tc': self.teslim_alan_tc,
                'teslim_alan_telefon': self.teslim_alan_telefon,
                'teslim_alan_imza': self.teslim_alan_imza,
                'teslim_eden_imza': self.teslim_eden_imza,
                'teslim_notu': self.teslim_notu.upper() if self.teslim_notu else '',
            })
            if self.ariza_id.ariza_tipi == 'magaza':
                if self.ariza_id.transfer_id:
                    mevcut_kaynak = self.ariza_id.transfer_id.location_id
                    mevcut_hedef = self.ariza_id.transfer_id.location_dest_id
                    yeni_transfer = self.ariza_id._create_stock_transfer(
                        kaynak_konum=mevcut_hedef,
                        hedef_konum=mevcut_kaynak
                    )
                    if yeni_transfer:
                        self.ariza_id.transfer_id = yeni_transfer.id
                        self.env['ir.logging'].create({
                            'name': 'ariza_onarim',
                            'type': 'server',
                            'level': 'info',
                            'dbname': self._cr.dbname,
                            'message': f"Yeni transfer oluşturuldu! Arıza No: {self.ariza_id.name} - Transfer ID: {yeni_transfer.id} - Kaynak: {mevcut_hedef.name} - Hedef: {mevcut_kaynak.name}",
                            'path': __file__,
                            'func': 'action_tamamla',
                            'line': 0,
                        })
                    else:
                        raise UserError(_("Transfer oluşturulamadı! Lütfen kaynak ve hedef konumları kontrol edin."))
        elif self.teslim_durumu == 'iptal':
            self.ariza_id.write({
                'state': 'iptal',
                'teslim_notu': self.teslim_notu.upper() if self.teslim_notu else '',
            })
        elif self.teslim_durumu == 'beklemede':
            self.ariza_id.write({
                'state': 'beklemede',
                'teslim_notu': self.teslim_notu.upper() if self.teslim_notu else '',
            })
        return {'type': 'ir.actions.act_window_close'} 