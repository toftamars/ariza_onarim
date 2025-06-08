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
        ariza = self.ariza_id
        # SMS gönderimi
        if ariza.ariza_tipi == 'musteri' and ariza.partner_id and ariza.partner_id.phone:
            magaza_adi = ariza._clean_magaza_adi(ariza.teslim_magazasi_id.name) if ariza.teslim_magazasi_id else ''
            # SMS mesajı
            sms_mesaji = f"Sayın {ariza.partner_id.name}. {ariza.name}, {ariza.urun} ürününüz teslim edilmeye hazırdır. Ürününüzü - {magaza_adi} mağazamızdan teslim alabilirsiniz. B021"
            ariza._send_sms_to_customer(sms_mesaji)
        
        # Önceki transferin konumlarını ters çevirerek yeni transfer oluştur
        if ariza.transfer_id:
            mevcut_kaynak = ariza.transfer_id.location_id
            mevcut_hedef = ariza.transfer_id.location_dest_id
            
            # Konumları ters çevirerek yeni transfer oluştur
            yeni_transfer = ariza._create_stock_transfer(
                kaynak_konum=mevcut_hedef,  # Önceki hedef konum yeni kaynak konum olur
                hedef_konum=mevcut_kaynak   # Önceki kaynak konum yeni hedef konum olur
            )
            
            if yeni_transfer:
                ariza.transfer_id = yeni_transfer.id
                # Yeni transferin detaylarını logla
                self.env['ir.logging'].create({
                    'name': 'ariza_onarim',
                    'type': 'server',
                    'level': 'info',
                    'dbname': self._cr.dbname,
                    'message': f"Yeni transfer oluşturuldu! Arıza No: {ariza.name} - Transfer ID: {yeni_transfer.id} - Kaynak: {mevcut_hedef.name} - Hedef: {mevcut_kaynak.name}",
                    'path': __file__,
                    'func': 'action_tamamla',
                    'line': 0,
                })
            else:
                raise UserError(_("Transfer oluşturulamadı! Lütfen kaynak ve hedef konumları kontrol edin."))
        
        # Arıza kaydını güncelle
        ariza.write({
            'state': 'tamamlandi',
            'teslim_notu': self.teslim_notu if hasattr(self, 'teslim_notu') else False
        })
        
        return {'type': 'ir.actions.act_window_close'} 