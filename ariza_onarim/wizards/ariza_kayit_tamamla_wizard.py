from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ArizaKayitTamamlaWizard(models.TransientModel):
    _name = 'ariza.kayit.tamamla.wizard'
    _description = 'ARIZA KAYIT TAMAMLAMA SİHİRBAZI'

    ariza_id = fields.Many2one('ariza.kayit', string='ARIZA KAYDI', required=True)
    musteri_adi = fields.Char(string='MÜŞTERİ ADI', readonly=True)
    urun = fields.Char(string='ÜRÜN', readonly=True)
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
    teslim_magazasi_id = fields.Many2one('account.analytic.account', string='TESLİM MAĞAZASI')
    teslim_adresi = fields.Char(string='TESLİM ADRESİ', readonly=True)
    teslim_tarihi = fields.Date(string='TESLİM TARİHİ', required=True, default=fields.Date.context_today)
    teslim_saati = fields.Float(string='TESLİM SAATİ', required=False)
    teslim_eden = fields.Many2one('res.users', string='TESLİM EDEN', required=True, default=lambda self: self.env.user)
    teslim_alan = fields.Char(string='TESLİM ALAN')
    teslim_alan_tc = fields.Char(string='TESLİM ALAN TC')
    teslim_alan_telefon = fields.Char(string='TESLİM ALAN TELEFON')
    teslim_alan_imza = fields.Binary(string='TESLİM ALAN İMZA', required=True)
    teslim_eden_imza = fields.Binary(string='TESLİM EDEN İMZA', required=True)
    teslim_notu = fields.Text(string='TESLİM NOTU')
    teslim_durumu = fields.Selection([
        ('tamamlandi', 'TAMAMLANDI'),
        ('iptal', 'İPTAL'),
        ('beklemede', 'BEKLEMEDE')
    ], string='TESLİM DURUMU', required=True, default='tamamlandi')
    sms_gonderildi_wizard = fields.Boolean(string='SMS Gönderildi', readonly=True, default=False)
    contact_id = fields.Many2one('res.partner', string='Kontak (Teslimat Adresi)')
    kaynak_konum_id = fields.Many2one('stock.location', string='Kaynak Konum')
    hedef_konum_id = fields.Many2one('stock.location', string='Hedef Konum')

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
                'teslim_adresi': ariza.teslim_adresi.upper() if ariza.teslim_adresi else '',
            })
            if ariza.ariza_tipi == 'musteri':
                res['teslim_magazasi_id'] = ariza.teslim_magazasi_id.id
            # Mağaza ürünü işlemlerinde kontak ve hedef konum otomatik dolsun
            if ariza.ariza_tipi == 'magaza':
                res['contact_id'] = ariza.contact_id.id if ariza.contact_id else False
                res['hedef_konum_id'] = ariza.kaynak_konum_id.id if ariza.kaynak_konum_id else False
        return res

    def action_tamamla(self):
        ariza = self.ariza_id
        # Mağaza ürünü işlemlerinde kontak ve hedef konum wizarddan alınsın
        if ariza.ariza_tipi == 'magaza':
            contact = self.contact_id or ariza.contact_id
            hedef_konum = self.hedef_konum_id or ariza.hedef_konum_id
            if not ariza.transfer_id and ariza.kaynak_konum_id and hedef_konum:
                transfer = ariza._create_stock_transfer(kaynak_konum=ariza.kaynak_konum_id, hedef_konum=self.hedef_konum_id, transfer_tipi='ilk')
                if transfer:
                    ariza.transfer_id = transfer.id
        # SMS gönderimi
        if ariza.ariza_tipi == 'musteri' and ariza.partner_id and ariza.partner_id.phone:
            magaza_adi = ariza._clean_magaza_adi(ariza.teslim_magazasi_id.name) if ariza.teslim_magazasi_id else ''
            sms_mesaji = f"Sayın {ariza.partner_id.name}. {ariza.name}, {ariza.urun} ürününüz teslim edilmeye hazırdır. Ürününüzü - {magaza_adi} mağazamızdan teslim alabilirsiniz. B021"
            ariza._send_sms_to_customer(sms_mesaji)

        # Önceki transferin konumlarını ters çevirerek yeni transfer oluştur
        yeni_transfer = False
        if ariza.transfer_id:
            mevcut_kaynak = ariza.transfer_id.location_id
            mevcut_hedef = ariza.transfer_id.location_dest_id
            # Konumları ters çevirerek yeni transfer oluştur
            yeni_transfer = ariza._create_stock_transfer(
                kaynak_konum=mevcut_hedef,  # Önceki hedef konum yeni kaynak konum olur
                hedef_konum=ariza.kaynak_konum_id,   # Hedef konum arıza kaydındaki kaynak konum olur
                delivery_type='matbu',
                transfer_tipi='ikinci'  # Onarım sonrası transfer
            )
            if yeni_transfer:
                transfer_url = f"/web#id={yeni_transfer.id}&model=stock.picking&view_type=form"
                ariza.message_post(
                    body=f"<b>Onarım sonrası giriş transferi oluşturuldu!</b><br/>"
                         f"Transfer No: <a href='{transfer_url}'>{yeni_transfer.name}</a><br/>"
                         f"Kaynak: {mevcut_hedef.display_name}<br/>"
                         f"Hedef: {ariza.kaynak_konum_id.display_name}<br/>"
                )
                # 2. transfer oluşturulduktan sonra işlemi kilitle
                ariza.write({
                    'state': 'kilitli',
                    'teslim_notu': self.teslim_notu if hasattr(self, 'teslim_notu') else False
                })
                # Kullanıcıyı yeni transferin form ekranına yönlendir
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Transfer Belgesi',
                    'res_model': 'stock.picking',
                    'res_id': yeni_transfer.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
        # Arıza kaydını güncelle (eğer transfer oluşturulmadıysa)
        ariza.write({
            'state': 'tamamlandi',
            'teslim_notu': self.teslim_notu if hasattr(self, 'teslim_notu') else False
        })
        return {'type': 'ir.actions.act_window_close'} 