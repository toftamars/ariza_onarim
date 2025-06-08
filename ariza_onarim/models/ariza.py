from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import os

class ArizaKayit(models.Model):
    _name = 'ariza.kayit'
    _description = 'Arıza Kayıtları'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Arıza No', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    transfer_id = fields.Many2one('stock.picking', string='Transfer', readonly=True)
    islem_tipi = fields.Selection([
        ('kabul', 'Arıza Kabul'),
    ], string='İşlem Tipi', required=True, tracking=True)
    ariza_tipi = fields.Selection([
        ('musteri', 'Müşteri Ürünü'),
        ('magaza', 'Mağaza Ürünü')
    ], string='Arıza Tipi', required=True, tracking=True)
    teknik_servis = fields.Selection([
        ('DTL BEYOĞLU', 'DTL BEYOĞLU'),
        ('DTL OKMEYDANI', 'DTL OKMEYDANI'),
        ('ZUHAL ARIZA DEPO', 'ZUHAL ARIZA DEPO'),
        ('MAĞAZA', 'MAĞAZA'),
        ('ZUHAL NEFESLİ', 'ZUHAL NEFESLİ'),
        ('TEDARİKÇİ', 'TEDARİKÇİ')
    ], string='Teknik Servis')
    transfer_metodu = fields.Selection([
        ('arac', 'Araç'),
        ('ucretsiz_kargo', 'Ücretsiz Kargo'),
        ('ucretli_kargo', 'Ücretli Kargo'),
        ('magaza', 'Mağaza'),
    ], string='Transfer Metodu', tracking=True, default='arac')
    partner_id = fields.Many2one('res.partner', string='Müşteri', tracking=True)
    analitik_hesap_id = fields.Many2one('account.analytic.account', string='Analitik Hesap', tracking=True, required=True)
    kaynak_konum_id = fields.Many2one('stock.location', string='Kaynak Konum', tracking=True, domain="[('company_id', '=', company_id)]")
    hedef_konum_id = fields.Many2one('stock.location', string='Hedef Konum', tracking=True, domain="[('company_id', '=', company_id)]")
    tedarikci_id = fields.Many2one('res.partner', string='Tedarikçi', tracking=True)
    marka_id = fields.Many2one('product.brand', string='Marka', tracking=True)
    marka_manu = fields.Char(string='Marka (Manuel)', tracking=True)
    tedarikci_adresi = fields.Text(string='Teslim Adresi', tracking=True)
    tedarikci_telefon = fields.Char(string='Tedarikçi Telefon', tracking=True)
    tedarikci_email = fields.Char(string='Tedarikçi E-posta', tracking=True)
    sorumlu_id = fields.Many2one('res.users', string='Sorumlu', default=lambda self: self.env.user, tracking=True)
    tarih = fields.Date(string='Tarih', default=fields.Date.context_today, tracking=True)
    state = fields.Selection([
        ('draft', 'Taslak'),
        ('onaylandi', 'Onaylandı'),
        ('tamamlandi', 'Tamamlandı'),
        ('teslim_edildi', 'Teslim Edildi'),
        ('iptal', 'İptal'),
    ], string='Durum', default='draft', tracking=True)
    siparis_yok = fields.Boolean(string='Sipariş Yok', default=False)
    invoice_line_id = fields.Many2one('account.move.line', string='Fatura Kalemi',
        domain="[('move_id.partner_id', '=', partner_id), ('product_id.type', '=', 'product')]",
        tracking=True)
    fatura_tarihi = fields.Date(string='Fatura Tarihi', compute='_compute_fatura_tarihi', store=True)
    urun = fields.Char(string='Ürün', required=True)
    model = fields.Char(string='Model', required=True)
    garanti_suresi = fields.Char(string='Garanti Süresi', compute='_compute_garanti_suresi', store=True, tracking=True)
    garanti_bitis_tarihi = fields.Date(string='Garanti Bitiş Tarihi', compute='_compute_garanti_suresi', store=True)
    kalan_garanti = fields.Char(string='Kalan Garanti', compute='_compute_garanti_suresi', store=True)
    garanti_kapsaminda_mi = fields.Selection([
        ('evet', 'Evet'),
        ('hayir', 'Hayır'),
    ], string='Garanti Kapsamında mı?', tracking=True)
    ariza_tanimi = fields.Text(string='Arıza Tanımı', tracking=True)
    notlar = fields.Text(string='Notlar')
    transfer_irsaliye = fields.Char(string='Transfer İrsaliye No')
    company_id = fields.Many2one('res.company', string='Şirket', default=lambda self: self.env.company)
    onarim_ucreti = fields.Float(string='Onarım Ücreti', tracking=True)
    yapilan_islemler = fields.Text(string='Yapılan İşlemler', tracking=True)
    marka_urunleri_ids = fields.Many2many(
        'product.product',
        string='Marka Ürünleri',
        tracking=True
    )
    ariza_kabul_id = fields.Many2one('ariza.kayit', string='Arıza Kabul No', domain="[('islem_tipi', '=', 'kabul')]", tracking=True)
    onarim_bilgisi = fields.Text(string='Onarım Bilgisi', tracking=True)
    ucret_bilgisi = fields.Char(string='Ücret Bilgisi', tracking=True)
    magaza_urun_id = fields.Many2one(
        'product.product',
        string='Ürün',
        tracking=True
    )
    sms_gonderildi = fields.Boolean(string='SMS Gönderildi', default=False, tracking=True)
    teslim_magazasi_id = fields.Many2one('account.analytic.account', string='Teslim Mağazası', tracking=True)
    teslim_adresi = fields.Char(string='Teslim Adresi', tracking=True)
    musteri_faturalari = fields.Many2many('account.move', string='Müşteri Faturaları')
    teknik_servis_adres = fields.Char(string='Teknik Servis Adresi', compute='_compute_teknik_servis_adres', store=False)
    teslim_alan = fields.Char(string='Teslim Alan')
    teslim_alan_tc = fields.Char(string='Teslim Alan TC')
    teslim_alan_telefon = fields.Char(string='Teslim Alan Telefon')
    teslim_alan_imza = fields.Binary(string='Teslim Alan İmza')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Sorumlu kişinin analitik bilgisini al
            if not vals.get('analitik_hesap_id') and vals.get('sorumlu_id'):
                sorumlu = self.env['res.users'].browse(vals['sorumlu_id'])
                if sorumlu and sorumlu.employee_id and sorumlu.employee_id.magaza_id:
                    vals['analitik_hesap_id'] = sorumlu.employee_id.magaza_id.id
            # Varsayılan değerleri ayarla
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ariza.kayit')
            if not vals.get('state'):
                vals['state'] = 'draft'
            if not vals.get('islem_tipi'):
                vals['islem_tipi'] = 'kabul'
            if not vals.get('ariza_tipi'):
                vals['ariza_tipi'] = 'musteri'
            if not vals.get('sorumlu_id'):
                vals['sorumlu_id'] = self.env.user.id
        return super().create(vals_list)

    @api.depends('invoice_line_id')
    def _compute_fatura_tarihi(self):
        for record in self:
            if record.invoice_line_id:
                record.fatura_tarihi = record.invoice_line_id.move_id.invoice_date
            else:
                record.fatura_tarihi = False

    @api.onchange('ariza_tipi')
    def _onchange_ariza_tipi(self):
        if self.ariza_tipi == 'musteri':
            self.partner_id = False
            self.urun = False
            self.model = False
            self.teslim_magazasi_id = False
            self.teslim_adresi = False
            self.transfer_id = False
        elif self.ariza_tipi == 'magaza':
            self.partner_id = False
            self.urun = False
            self.model = False
            self.teslim_magazasi_id = self.env.user.employee_id.magaza_id
            if self.teslim_magazasi_id and self.teslim_magazasi_id.name in ['DTL OKMEYDANI', 'DTL BEYOĞLU']:
                self.teslim_adresi = 'MAHMUT ŞEVKET PAŞA MAH. ŞAHİNKAYA SOK NO 31 OKMEYDANI'
        elif self.ariza_tipi == 'teknik':
            self.partner_id = False
            self.urun = False
            self.model = False
            self.teslim_magazasi_id = False
            self.teslim_adresi = False

    @api.onchange('teknik_servis')
    def _onchange_teknik_servis(self):
        if not self.analitik_hesap_id:
            return

        # Analitik hesaba ait stok konumunu bul
        dosya_yolu = os.path.join(os.path.dirname(__file__), '..', 'Analitik Bilgileri.txt')
        hesap_adi = self.analitik_hesap_id.name.strip().lower()
        konum_kodu = None
        try:
            with open(dosya_yolu, 'r', encoding='utf-8') as f:
                for satir in f:
                    if hesap_adi in satir.lower():
                        parcalar = satir.strip().split('\t')
                        if len(parcalar) == 2:
                            konum_kodu = parcalar[1]
                            break
        except Exception as e:
            pass

        if konum_kodu:
            konum = self.env['stock.location'].search([
                ('name', '=', konum_kodu),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            if konum:
                self.kaynak_konum_id = konum

        # DTL Beyoğlu adresini otomatik ekle
        if self.teknik_servis == 'dtl_beyoglu':
            self.tedarikci_adresi = 'Şahkulu, Nakkaş Çk. No:1 D:1, 34420 Beyoğlu/İstanbul'
        # Zuhal adresini otomatik ekle
        elif self.teknik_servis == 'zuhal':
            self.tedarikci_adresi = 'Halkalı Merkez, 34303 Küçükçekmece/İstanbul'

        # Müşteri ürünü işlemleri için hedef konum ayarları
        if self.ariza_tipi == 'musteri':
            if self.teknik_servis == 'magaza' and konum_kodu:
                # Mağaza seçildiğinde [KOD]/arızalı konumu
                arizali_konum = self.env['stock.location'].search([
                    ('name', '=', f"{konum_kodu.split('/')[0]}/arızalı"),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if arizali_konum:
                    self.hedef_konum_id = arizali_konum
            elif self.teknik_servis in ['dtl_beyoglu', 'dtl_okmeydani']:
                # DTL seçildiğinde dtl/stok konumu
                dtl_konum = self.env['stock.location'].search([
                    ('name', '=', 'dtl/stok'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if dtl_konum:
                    self.hedef_konum_id = dtl_konum
            elif self.teknik_servis == 'zuhal':
                # Zuhal seçildiğinde arıza/stok konumu
                ariza_konum = self.env['stock.location'].search([
                    ('name', '=', 'arıza/stok'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if ariza_konum:
                    self.hedef_konum_id = ariza_konum

        # Mağaza ürünü işlemleri için hedef konum ayarları
        elif self.ariza_tipi == 'magaza':
            if self.teknik_servis in ['dtl_beyoglu', 'dtl_okmeydani']:
                # DTL seçildiğinde dtl/stok konumu
                dtl_konum = self.env['stock.location'].search([
                    ('name', '=', 'dtl/stok'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if dtl_konum:
                    self.hedef_konum_id = dtl_konum
            elif self.teknik_servis == 'zuhal':
                # Zuhal seçildiğinde arıza/stok konumu
                ariza_konum = self.env['stock.location'].search([
                    ('name', '=', 'arıza/stok'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if ariza_konum:
                    self.hedef_konum_id = ariza_konum

        # Teknik servis seçimine göre hedef konumu otomatik ata
        if self.teknik_servis in ['DTL BEYOĞLU', 'DTL OKMEYDANI']:
            dtl_konum = self.env['stock.location'].search([
                ('name', '=', 'DTL/Stok'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            if dtl_konum:
                self.hedef_konum_id = dtl_konum
        elif self.teknik_servis == 'ZUHAL ARIZA DEPO':
            ariza_konum = self.env['stock.location'].search([
                ('name', '=', 'Arıza/Stok'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            if ariza_konum:
                self.hedef_konum_id = ariza_konum
        elif self.teknik_servis == 'ZUHAL NEFESLİ':
            nfsl_konum = self.env['stock.location'].search([
                ('name', '=', 'Nfsl/Arızalı'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            if nfsl_konum:
                self.hedef_konum_id = nfsl_konum

    @api.onchange('analitik_hesap_id')
    def _onchange_analitik_hesap_id(self):
        if self.analitik_hesap_id and self.ariza_tipi in ['magaza', 'teknik']:
            # Dosya yolu
            dosya_yolu = os.path.join(os.path.dirname(__file__), '..', 'Analitik Bilgileri.txt')
            hesap_adi = self.analitik_hesap_id.name.strip().lower()
            konum_kodu = None
            try:
                with open(dosya_yolu, 'r', encoding='utf-8') as f:
                    for satir in f:
                        if hesap_adi in satir.lower():
                            parcalar = satir.strip().split('\t')
                            if len(parcalar) == 2:
                                konum_kodu = parcalar[1]
                                break
            except Exception as e:
                pass  # Hata yönetimi eklenebilir

            if konum_kodu:
                konum = self.env['stock.location'].search([
                    ('name', '=', konum_kodu),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if konum:
                    self.kaynak_konum_id = konum

            # Tedarikçiye gönderim ise hedef konum tedarikçi adresi
            if self.teknik_servis == 'TEDARİKÇİ' and self.tedarikci_id:
                if self.tedarikci_id.property_stock_supplier:
                    self.hedef_konum_id = self.tedarikci_id.property_stock_supplier
            # Teknik servis ise hedef konum DTL/Stok
            elif self.teknik_servis in ['DTL BEYOĞLU', 'DTL OKMEYDANI']:
                dtl_konum = self.env['stock.location'].search([
                    ('name', '=', 'DTL/Stok'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if dtl_konum:
                    self.hedef_konum_id = dtl_konum

    @api.onchange('invoice_line_id')
    def _onchange_invoice_line_id(self):
        if self.invoice_line_id:
            product = self.invoice_line_id.product_id
            if product:
                if self.islem_tipi == 'kabul' and self.ariza_tipi == 'musteri' and not self.siparis_yok:
                    self.urun = product.name
                    self.model = product.default_code or ''
                    # Marka bilgisini ürün şablonundan al
                    if hasattr(product, 'brand_id') and product.brand_id:
                        self.marka_id = product.brand_id.id
                        # Marka seçilince tedarikçi otomatik gelsin
                        if self.marka_id:
                            marka = self.env['product.brand'].browse(self.marka_id)
                            if marka and marka.partner_id:
                                self.tedarikci_id = marka.partner_id.id
                                self._onchange_tedarikci()
                    else:
                        self.marka_id = False
                        self.tedarikci_id = False
                        self.tedarikci_adresi = False
                        self.tedarikci_telefon = False
                        self.tedarikci_email = False
                else:
                    self.urun = product.name
                    self.model = product.default_code or ''
                    if hasattr(product, 'brand_id') and product.brand_id:
                        self.marka_id = product.brand_id.id
                        if self.marka_id:
                            marka = self.env['product.brand'].browse(self.marka_id)
                            if marka and marka.partner_id:
                                self.tedarikci_id = marka.partner_id.id
                                self._onchange_tedarikci()
                    else:
                        self.marka_id = False
                        self.tedarikci_id = False
                        self.tedarikci_adresi = False
                        self.tedarikci_telefon = False
                        self.tedarikci_email = False

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if not self.partner_id:
            self.invoice_line_id = False
            self.siparis_yok = False
            self.urun = False
            self.model = False

    @api.onchange('marka_id')
    def _onchange_marka_id(self):
        if self.marka_id:
            # Marka seçilince tedarikçi otomatik gelsin
            if self.marka_id.partner_id:
                self.tedarikci_id = self.marka_id.partner_id.id
                self._onchange_tedarikci()
        else:
            self.tedarikci_id = False
            self.tedarikci_adresi = False
            self.tedarikci_telefon = False
            self.tedarikci_email = False
            self.marka_urunleri_ids = False
            self.magaza_urun_id = False

    @api.onchange('tedarikci_id')
    def _onchange_tedarikci(self):
        if self.tedarikci_id:
            self.tedarikci_adresi = self.tedarikci_id.street
            self.tedarikci_telefon = self.tedarikci_id.phone
            self.tedarikci_email = self.tedarikci_id.email
            # Tedarikçiye gönderim ise hedef konum tedarikçi adresi
            if self.teknik_servis == 'TEDARİKÇİ' and self.tedarikci_id.property_stock_supplier:
                self.hedef_konum_id = self.tedarikci_id.property_stock_supplier

    @api.onchange('islem_tipi')
    def _onchange_islem_tipi(self):
        if self.islem_tipi != 'teslim':
            self.garanti_kapsaminda_mi = False

    @api.onchange('ariza_tipi')
    def _onchange_ariza_tipi_teknik(self):
        if self.ariza_tipi == 'teknik' and self.analitik_hesap_id:
            # Analitik hesaptan kaynak konumu al
            if hasattr(self.analitik_hesap_id, 'konum_id') and self.analitik_hesap_id.konum_id:
                self.kaynak_konum_id = self.analitik_hesap_id.konum_id
            # Hedef konumu DTL/Stok olarak ayarla
            dtl_konum = self.env['stock.location'].search([
                ('name', '=', 'DTL/Stok'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            if dtl_konum:
                self.hedef_konum_id = dtl_konum

    @api.onchange('ariza_kabul_id')
    def _onchange_ariza_kabul_id(self):
        if self.ariza_kabul_id:
            fields_to_copy = [
                'partner_id', 'analitik_hesap_id', 'kaynak_konum_id', 'hedef_konum_id', 'tedarikci_id',
                'marka_id', 'tedarikci_adresi', 'tedarikci_telefon', 'tedarikci_email', 'urun', 'model',
                'fatura_tarihi', 'notlar', 'onarim_ucreti', 'yapilan_islemler', 'ariza_tanimi',
                'garanti_suresi', 'garanti_bitis_tarihi', 'kalan_garanti', 'transfer_metodu',
                'magaza_urun_id', 'marka_urunleri_ids', 'teknik_servis', 'onarim_bilgisi', 'ucret_bilgisi', 'garanti_kapsaminda_mi', 'ariza_tipi',
                'invoice_line_id', 'siparis_yok'
            ]
            for field in fields_to_copy:
                setattr(self, field, getattr(self.ariza_kabul_id, field, False))

    def _create_stock_transfer(self, kaynak_konum=None, hedef_konum=None):
        _logger = self.env['ir.logging']
        kaynak = kaynak_konum or self.kaynak_konum_id
        hedef = hedef_konum or self.hedef_konum_id
        
        # Tedarikçi için özel kontrol
        if self.ariza_tipi == 'magaza' and self.teknik_servis == 'TEDARİKÇİ' and self.tedarikci_id:
            if not self.tedarikci_id.property_stock_supplier:
                raise UserError(_("Tedarikçi için stok konumu tanımlanmamış!"))
            hedef = self.tedarikci_id.property_stock_supplier

        if not self.analitik_hesap_id:
            raise UserError(_("Transfer oluşturulamadı: Analitik hesap seçili değil!"))
        if not kaynak or not hedef:
            raise UserError(_("Transfer oluşturulamadı: Kaynak veya hedef konum eksik!"))
        if not self.magaza_urun_id:
            raise UserError(_("Transfer oluşturulamadı: Ürün seçili değil!"))
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '=', kaynak.warehouse_id.id)
        ], limit=1)
        if not picking_type:
            raise UserError(_("Transfer tipi bulunamadı. Lütfen depo ve konum ayarlarınızı kontrol edin."))
        picking_vals = {
            'location_id': kaynak.id,
            'location_dest_id': hedef.id,
            'picking_type_id': picking_type.id,
            'move_type': 'direct',
            'immediate_transfer': True,
            'company_id': self.env.company.id,
            'origin': self.name,
            'note': f"Arıza Kaydı: {self.name}\nÜrün: {self.urun}\nModel: {self.model}\nTransfer Metodu: {self.transfer_metodu}",
            'analytic_account_id': self.analitik_hesap_id.id if self.analitik_hesap_id else False,
        }
        picking = self.env['stock.picking'].create(picking_vals)
        # Ürün hareketi ekle
        self.env['stock.move'].create({
            'name': self.urun or self.magaza_urun_id.name,
            'product_id': self.magaza_urun_id.id,
            'product_uom_qty': 1,
            'product_uom': self.magaza_urun_id.uom_id.id,
            'picking_id': picking.id,
            'location_id': kaynak.id,
            'location_dest_id': hedef.id,
            'company_id': self.env.company.id,
            'analytic_account_id': self.analitik_hesap_id.id if self.analitik_hesap_id else False,
            'quantity_done': 1,
        })
        _logger.create({
            'name': 'ariza_onarim',
            'type': 'server',
            'level': 'debug',
            'dbname': self._cr.dbname,
            'message': f"Transfer OLUŞTURULDU! Arıza No: {self.name} - Picking ID: {picking.id}",
            'path': __file__,
            'func': '_create_stock_transfer',
            'line': 0,
        })
        return picking

    def _send_sms_to_customer(self, message):
        # Sadece müşteri ürünü işlemlerinde SMS gönder
        if self.ariza_tipi != 'musteri':
            return
        if self.partner_id and self.partner_id.phone:
            sms_obj = self.env['sms.sms'].create({
                'partner_id': self.partner_id.id,
                'number': self.partner_id.phone,
                'body': message,
                'state': 'outgoing',
            })
            sms_obj.send()
        # SMS ile birlikte mail de gönder
        if self.partner_id and self.partner_id.email:
            subject = "Arıza Kaydınız Hakkında Bilgilendirme"
            self._send_email_to_customer(subject, message)

    def _send_email_to_customer(self, subject, body):
        """Müşteriye mail gönder"""
        if self.partner_id and self.partner_id.email:
            try:
                template = self.env.ref('ariza_onarim.email_template_ariza_bilgilendirme')
                template.with_context(
                    email_to=self.partner_id.email,
                    email_subject=subject,
                    email_body=body
                ).send_mail(self.id, force_send=True)
                return True
            except Exception as e:
                self.env['ir.logging'].create({
                    'name': 'ariza_onarim',
                    'type': 'server',
                    'level': 'error',
                    'dbname': self._cr.dbname,
                    'message': f"Mail gönderimi başarısız! Arıza No: {self.name} - Hata: {str(e)}",
                    'path': __file__,
                    'func': '_send_email_to_customer',
                    'line': 0,
                })
        return False

    def _create_delivery_order(self):
        if not self.partner_id or not self.analitik_hesap_id:
            return False

        # Kargo şirketini bul
        delivery_carrier = self.env['delivery.carrier'].search([
            ('delivery_type', '=', 'fixed'),
            ('fixed_price', '=', 0.0)
        ], limit=1)

        if not delivery_carrier:
            raise UserError(_("Ücretsiz kargo seçeneği bulunamadı."))

        # Satış siparişi oluştur
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'analytic_account_id': self.analitik_hesap_id.id,
            'carrier_id': delivery_carrier.id,
            'order_line': [(0, 0, {
                'name': f"Arıza Kaydı: {self.name}",
                'product_id': self.env.ref('product.product_product_4').id,  # Kargo ürünü
                'product_uom_qty': 1,
                'price_unit': 0.0,
            })],
        })

        # Satış siparişini onayla
        sale_order.action_confirm()

        # Teslimat siparişi oluştur
        picking = sale_order.picking_ids.filtered(lambda p: p.picking_type_code == 'outgoing')
        if picking:
            picking.write({
                'origin': self.name,
                'note': f"Arıza Kaydı: {self.name}\nÜrün: {self.urun}\nModel: {self.model}"
            })
            return picking
        return False

    def action_onayla(self):
        # Mağaza ürünü ve teknik servis tedarikçi ise transferi tedarikçiye oluştur
        if self.ariza_tipi == 'magaza' and self.teknik_servis == 'TEDARİKÇİ' and not self.transfer_id:
            if not self.tedarikci_id:
                raise UserError('Tedarikçi seçilmedi!')
            picking = self._create_stock_transfer()
            if picking:
                self.transfer_id = picking.id
                self.state = 'onaylandi'
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Transfer Belgesi',
                    'res_model': 'stock.picking',
                    'res_id': picking.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
        # Mağaza ürünü ve teknik servis mağaza seçildiğinde transfer oluşturma
        if self.ariza_tipi == 'magaza' and self.teknik_servis == 'MAĞAZA':
            self.state = 'onaylandi'
            return
        # Mağaza ürünü için transfer oluşturma kontrolü
        if self.ariza_tipi == 'magaza' and self.teknik_servis == 'TEKNİK SERVİS':
            self.state = 'onaylandi'
            return
        # Mağaza ürünü için transfer oluştur
        if self.ariza_tipi == 'magaza' and not self.transfer_id:
            picking = self._create_stock_transfer()
            if picking:
                self.transfer_id = picking.id
                self.state = 'onaylandi'
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Transfer Belgesi',
                    'res_model': 'stock.picking',
                    'res_id': picking.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
        
        # Müşteri ürünü işlemlerinde SMS gönder
        if self.ariza_tipi == 'musteri' and not self.sms_gonderildi:
            message = f"Sayın {self.partner_id.name}., {self.urun} ürününüz teslim alındı, Ürününüz onarım sürecine alınmıştır. B021"
            self._send_sms_to_customer(message)
            self.sms_gonderildi = True

        # Ürün teslim işlemlerinde analitik bilgisi arıza kabulden gelsin
        if self.islem_tipi == 'teslim' and self.ariza_kabul_id:
            self.analitik_hesap_id = self.ariza_kabul_id.analitik_hesap_id

        self.state = 'onaylandi'

    def action_tamamla(self):
        # Sadece kabul işlemlerinde tamamla butonu olsun
        if self.islem_tipi == 'kabul':
            # Onay uyarısı göster
            return {
                'name': 'Onarım Tamamlandı',
                'type': 'ir.actions.act_window',
                'res_model': 'ariza.kayit.tamamla.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_ariza_id': self.id,
                    'default_musteri_adi': self.partner_id.name,
                    'default_urun': self.urun,
                    'default_onay_mesaji': 'Ürünün onarım süreci tamamlanmıştır. Müşteriye SMS gönderilecektir. Emin misiniz?'
                }
            }

    def _clean_magaza_adi(self, name):
        # [1101404] Perakende - Akasya -> Akasya
        if name:
            if '-' in name:
                return name.split('-')[-1].strip().split()[0]
            return name.split()[-1]
        return ''

    def action_teslim_et(self):
        self.state = 'teslim_edildi'
        # SMS gönderimi kaldırıldı, artık tamamla butonunda gönderilecek

    def action_iptal(self):
        self.state = 'iptal'
        if self.transfer_id:
            self.transfer_id.action_cancel()

    @api.depends('invoice_line_id', 'fatura_tarihi')
    def _compute_garanti_suresi(self):
        for rec in self:
            rec.garanti_suresi = ''
            rec.garanti_bitis_tarihi = False
            rec.kalan_garanti = ''
            if rec.invoice_line_id and rec.fatura_tarihi:
                product = rec.invoice_line_id.product_id
                warranty_months = getattr(product.product_tmpl_id, 'warranty_period', 24)  # Varsayılan 24 ay
                rec.garanti_suresi = f"{warranty_months} ay"
                bitis = rec.fatura_tarihi + relativedelta(months=warranty_months)
                rec.garanti_bitis_tarihi = bitis
                kalan = (bitis - fields.Date.context_today(rec)).days
                if kalan > 0:
                    rec.kalan_garanti = f"{kalan} gün kaldı"
                else:
                    rec.kalan_garanti = "Süre doldu"

    def action_print(self):
        if self.transfer_metodu in ['ucretsiz_kargo', 'ucretli_kargo'] and self.transfer_id:
            return self.env.ref('stock.action_report_delivery').report_action(self.transfer_id)
        # Teknik servis adres bilgisi
        teknik_servis_adres = self.teknik_servis_adres
        ctx = dict(self.env.context)
        ctx['teknik_servis_adres'] = teknik_servis_adres
        return self.env.ref('ariza_onarim.action_report_ariza_kayit').with_context(ctx).report_action(self)

    @api.onchange('magaza_urun_id')
    def _onchange_magaza_urun_id(self):
        if self.magaza_urun_id:
            self.urun = self.magaza_urun_id.name or ''
            self.model = self.magaza_urun_id.default_code or ''
            # Ürün seçilince marka otomatik gelsin
            if hasattr(self.magaza_urun_id, 'brand_id') and self.magaza_urun_id.brand_id:
                self.marka_id = self.magaza_urun_id.brand_id.id
                # Marka seçilince tedarikçi otomatik gelsin
                if self.marka_id:
                    marka = self.env['product.brand'].browse(self.marka_id)
                    if marka and marka.partner_id:
                        self.tedarikci_id = marka.partner_id.id
                        self._onchange_tedarikci()
            else:
                self.marka_id = False
                self.tedarikci_id = False
                self.tedarikci_adresi = False
                self.tedarikci_telefon = False
                self.tedarikci_email = False

    def action_print_delivery(self):
        if self.transfer_id:
            return self.env.ref('stock.action_report_delivery').report_action(self.transfer_id)

    @api.onchange('teslim_magazasi_id')
    def _onchange_teslim_magazasi(self):
        if self.teslim_magazasi_id and self.teslim_magazasi_id.name in ['DTL OKMEYDANI', 'DTL BEYOĞLU']:
            self.teslim_adresi = 'MAHMUT ŞEVKET PAŞA MAH. ŞAHİNKAYA SOK NO 31 OKMEYDANI'
        else:
            self.teslim_adresi = False

    @api.onchange('sorumlu_id')
    def _onchange_sorumlu_id(self):
        """Sorumlu değiştiğinde analitik hesabı güncelle"""
        if self.sorumlu_id and self.sorumlu_id.employee_id and self.sorumlu_id.employee_id.magaza_id:
            self.analitik_hesap_id = self.sorumlu_id.employee_id.magaza_id.id

    @api.depends('partner_id')
    def _get_musteri_faturalari(self):
        for record in self:
            if record.partner_id:
                # Müşteriye ait gelen faturaları bul
                faturalar = self.env['account.move'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('move_type', '=', 'in_invoice'),
                    ('state', '=', 'posted'),
                    ('invoice_line_ids.product_id.type', '=', 'product')  # Sadece stok ürünleri
                ])
                record.musteri_faturalari = faturalar
            else:
                record.musteri_faturalari = False

    @api.onchange('fatura_kalem_id')
    def _onchange_fatura_kalem_id(self):
        if self.fatura_kalem_id:
            self.urun = self.fatura_kalem_id.product_id.name
            self.model = self.fatura_kalem_id.product_id.default_code
            # Ürünün marka bilgisini al
            if self.fatura_kalem_id.product_id.brand_id:
                self.marka_id = self.fatura_kalem_id.product_id.brand_id.id
            else:
                self.marka_id = False

    @api.depends('teknik_servis', 'tedarikci_id', 'tedarikci_adresi')
    def _compute_teknik_servis_adres(self):
        for rec in self:
            if rec.teknik_servis == 'TEDARİKÇİ' and rec.tedarikci_id:
                rec.teknik_servis_adres = rec.tedarikci_adresi or rec.tedarikci_id.street or ''
            elif rec.teknik_servis == 'ZUHAL ARIZA DEPO':
                rec.teknik_servis_adres = 'Halkalı merkez mh. Dereboyu cd. No:8/B'
            elif rec.teknik_servis == 'DTL BEYOĞLU':
                rec.teknik_servis_adres = 'Şahkulu mh. Nakkas çıkmazı No: 1/1 No:10-46 / 47'
            elif rec.teknik_servis == 'DTL OKMEYDANI':
                rec.teknik_servis_adres = 'MAHMUT ŞEVKET PAŞA MAH. ŞAHİNKAYA SOK NO 31 OKMEYDANI'
            elif rec.teknik_servis == 'ZUHAL NEFESLİ':
                rec.teknik_servis_adres = 'Şahkulu, Galip Dede Cd. No:33, 34421 Beyoğlu/İstanbul'
            else:
                rec.teknik_servis_adres = ''

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        res = super().button_validate()
        # Origin alanı üzerinden arıza kaydını bul
        for picking in self:
            if picking.origin:
                ariza = self.env['ariza.kayit'].search([('name', '=', picking.origin)], limit=1)
                if ariza:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'ariza.kayit',
                        'res_id': ariza.id,
                        'view_mode': 'form',
                        'target': 'current',
                    }
        return res 

class ArizaKayitTamamlaWizard(models.TransientModel):
    _name = 'ariza.kayit.tamamla.wizard'
    _description = 'Arıza Kaydı Tamamlama Sihirbazı'

    ariza_id = fields.Many2one('ariza.kayit', string='Arıza Kaydı', required=True)
    musteri_adi = fields.Char(string='Müşteri Adı', readonly=True)
    urun = fields.Char(string='Ürün', readonly=True)
    onay_mesaji = fields.Text(string='Onay Mesajı', readonly=True)

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
        
        return {'type': 'ir.actions.act_window_close'} 