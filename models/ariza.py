from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import os

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'
    
    partner_id = fields.Many2one('res.partner', string='Partner')
    adres = fields.Text(string='Adres')
    telefon = fields.Char(string='Telefon')
    email = fields.Char(string='E-posta')

    @api.model
    def _setup_zuhal_addresses(self):
        """Zuhal Dış Ticaret A.Ş. carisine ait adresleri analitik hesaplarla eşleştir"""
        zuhal_partner = self.env['res.partner'].search([('name', '=', 'Zuhal Dış Ticaret A.Ş.')], limit=1)
        if not zuhal_partner:
            return
            
        # Zuhal'in adreslerini al
        zuhal_addresses = self.env['res.partner'].search([
            ('parent_id', '=', zuhal_partner.id),
            ('type', '=', 'delivery')
        ])
        
        for address in zuhal_addresses:
            # Bu adrese ait analitik hesap var mı kontrol et
            existing_analytic = self.search([
                ('partner_id', '=', address.id)
            ], limit=1)
            
            if not existing_analytic:
                # Yeni analitik hesap oluştur
                self.create({
                    'name': f"{address.name} - {address.street or ''}",
                    'partner_id': address.id,
                    'adres': self._format_address(address),
                    'telefon': address.phone or address.mobile,
                    'email': address.email,
                })
            else:
                # Mevcut analitik hesabı güncelle
                existing_analytic.write({
                    'adres': self._format_address(address),
                    'telefon': address.phone or address.mobile,
                    'email': address.email,
                })
    
    def _format_address(self, partner):
        """Partner adresini formatla"""
        address_parts = []
        if partner.street:
            address_parts.append(partner.street)
        if partner.street2:
            address_parts.append(partner.street2)
        if partner.city:
            address_parts.append(partner.city)
        if partner.state_id:
            address_parts.append(partner.state_id.name)
        if partner.zip:
            address_parts.append(partner.zip)
        if partner.country_id:
            address_parts.append(partner.country_id.name)
        
        return ', '.join(address_parts) if address_parts else ''

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
        ('personel_onay', 'Personel Onayı'),
        ('teknik_onarim', 'Teknik Onarım'),
        ('onaylandi', 'Onaylandı'),
        ('tamamlandi', 'Tamamlandı'),
        ('teslim_edildi', 'Teslim Edildi'),
        ('kilitli', 'Kilitli'),
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
    teslim_notu = fields.Text(string='Teslim Notu', tracking=True)
    contact_id = fields.Many2one('res.partner', string='Kontak (Teslimat Adresi)', tracking=True)
    vehicle_id = fields.Many2one('res.partner', string='Sürücü', domain="[('is_driver','=',True)]", tracking=True)

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
                try:
                    vals['name'] = self.env['ir.sequence'].next_by_code('ariza.kayit')
                except:
                    # Sequence bulunamazsa manuel numara oluştur
                    import datetime
                    current_year = datetime.datetime.now().year
                    last_record = self.search([('name', '!=', False)], order='id desc', limit=1)
                    if last_record and last_record.name != 'New':
                        try:
                            last_number = int(last_record.name.split('/')[-1])
                            new_number = last_number + 1
                        except:
                            new_number = 1
                    else:
                        new_number = 1
                    vals['name'] = f"ARZ/{current_year}/{new_number:05d}"
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
        # Mağaza ürünü ve teknik servis tedarikçi ise hedef konum tedarikçi konumu
        elif self.ariza_tipi == 'magaza' and self.teknik_servis == 'TEDARİKÇİ' and self.tedarikci_id:
            if self.tedarikci_id.property_stock_supplier:
                self.hedef_konum_id = self.tedarikci_id.property_stock_supplier

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
        
        # Analitik hesaptan adres bilgilerini al
        if self.analitik_hesap_id:
            if self.analitik_hesap_id.adres:
                self.teslim_adresi = self.analitik_hesap_id.adres
            if self.analitik_hesap_id.telefon:
                self.tedarikci_telefon = self.analitik_hesap_id.telefon
            if self.analitik_hesap_id.email:
                self.tedarikci_email = self.analitik_hesap_id.email

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
            # Kontak (Teslimat Adresi) otomatik gelsin
            delivery_contact = self.tedarikci_id.child_ids.filtered(lambda c: c.type == 'delivery')
            self.contact_id = delivery_contact[0].id if delivery_contact else self.tedarikci_id.id
            # Tedarikçiye gönderim ise hedef konum tedarikçi adresi
            if self.teknik_servis == 'TEDARİKÇİ':
                if not self.tedarikci_id.property_stock_supplier:
                    raise UserError(_('Seçilen tedarikçinin stok konumu tanımlı değil! Lütfen tedarikçi kartında "Satıcı Konumu" alanını doldurun.'))
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

    def _create_stock_transfer(self, kaynak_konum=None, hedef_konum=None, force_internal=False, delivery_type=None, transfer_tipi=None):
        _logger = self.env['ir.logging']
        kaynak = kaynak_konum or self.kaynak_konum_id
        hedef = hedef_konum or self.hedef_konum_id
        
        # Log the locations for debugging
        _logger.create({
            'name': 'ariza_onarim',
            'type': 'server',
            'level': 'debug',
            'dbname': self._cr.dbname,
            'message': f"Transfer oluşturma başladı - Kaynak: {kaynak.display_name if kaynak else 'Yok'}, Hedef: {hedef.display_name if hedef else 'Yok'}",
            'path': __file__,
            'func': '_create_stock_transfer',
            'line': 0,
        })

        # Eğer mağaza ürünü, işlem tipi kabul ve teknik servis TEDARİKÇİ ise hedef contact_id olsun
        if self.ariza_tipi == 'magaza' and self.islem_tipi == 'kabul' and self.teknik_servis == 'TEDARİKÇİ' and self.contact_id:
            hedef = self.contact_id.property_stock_customer or self.contact_id.property_stock_supplier

        if not self.analitik_hesap_id:
            raise UserError(_("Transfer oluşturulamadı: Analitik hesap seçili değil!"))
        if not kaynak or not hedef:
            raise UserError(_("Transfer oluşturulamadı: Kaynak veya hedef konum eksik!"))
        if not self.magaza_urun_id:
            raise UserError(_("Transfer oluşturulamadı: Ürün seçili değil!"))

        # Picking type belirleme
        picking_type = False
        
        # Eğer mevcut bir transfer varsa, onun picking type'ını kullan
        if self.transfer_id:
            picking_type = self.transfer_id.picking_type_id
            _logger.create({
                'name': 'ariza_onarim',
                'type': 'server',
                'level': 'debug',
                'dbname': self._cr.dbname,
                'message': f"Mevcut transferden picking type alındı - Picking Type: {picking_type.name if picking_type else 'Yok'}",
                'path': __file__,
                'func': '_create_stock_transfer',
                'line': 0,
            })
        
        # Analitik hesap adını al
        magaza_adi = self.analitik_hesap_id.name if self.analitik_hesap_id else ""
        
        # Önce kaynak konumun warehouse'undan mağaza adını almayı dene
        if kaynak and kaynak.warehouse_id and kaynak.warehouse_id.name:
            magaza_adi = kaynak.warehouse_id.name
            _logger.create({
                'name': 'ariza_onarim',
                'type': 'server',
                'level': 'debug',
                'dbname': self._cr.dbname,
                'message': f"Kaynak konumdan mağaza adı alındı: {magaza_adi}",
                'path': __file__,
                'func': '_create_stock_transfer',
                'line': 0,
            })
        elif self.analitik_hesap_id and self.analitik_hesap_id.name:
            magaza_adi = self.analitik_hesap_id.name
            _logger.create({
                'name': 'ariza_onarim',
                'type': 'server',
                'level': 'debug',
                'dbname': self._cr.dbname,
                'message': f"Analitik hesaptan mağaza adı alındı: {magaza_adi}",
                'path': __file__,
                'func': '_create_stock_transfer',
                'line': 0,
            })
        
        # 1. transfer için önce tam eşleşme, yoksa ilike ile 'Tamir Teslimatları' geçen ilk operasyon türü
        if not picking_type and transfer_tipi == 'ilk':
            # Önce "Mağaza Adı: Tamir Teslimatları" formatında ara
            if magaza_adi:
                picking_type = self.env['stock.picking.type'].search([
                    ('name', '=', f'{magaza_adi}: Tamir Teslimatları')
                ], limit=1)
                if not picking_type:
                    picking_type = self.env['stock.picking.type'].search([
                        ('name', 'ilike', f'{magaza_adi}: Tamir Teslimatları')
                    ], limit=1)
            
            # Bulunamazsa sadece "Tamir Teslimatları" ara
            if not picking_type:
                picking_type = self.env['stock.picking.type'].search([
                    ('name', '=', 'Tamir Teslimatları')
                ], limit=1)
                if not picking_type:
                    picking_type = self.env['stock.picking.type'].search([
                        ('name', 'ilike', 'Tamir Teslimatları')
                    ], limit=1)
            
            if not picking_type:
                raise UserError(_("'Tamir Teslimatları' operasyon türü bulunamadı. Lütfen depo ve konum ayarlarınızı kontrol edin."))
        
        # 2. transfer için önce tam eşleşme, yoksa ilike ile 'Tamir Alımlar' geçen ilk operasyon türü
        if not picking_type and transfer_tipi == 'ikinci':
            # Önce "Mağaza Adı: Tamir Alımlar" formatında ara
            if magaza_adi:
                picking_type = self.env['stock.picking.type'].search([
                    ('name', '=', f'{magaza_adi}: Tamir Alımlar')
                ], limit=1)
                if not picking_type:
                    picking_type = self.env['stock.picking.type'].search([
                        ('name', 'ilike', f'{magaza_adi}: Tamir Alımlar')
                    ], limit=1)
            
            # Bulunamazsa sadece "Tamir Alımlar" ara
            if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('name', '=', 'Tamir Alımlar')
            ], limit=1)
                if not picking_type:
                    picking_type = self.env['stock.picking.type'].search([
                        ('name', 'ilike', 'Tamir Alımlar')
                    ], limit=1)
            
            if not picking_type:
                raise UserError(_("'Tamir Alımlar' operasyon türü bulunamadı. Lütfen depo ve konum ayarlarınızı kontrol edin."))
        
        # transfer_tipi belirtilmemişse veya bulunamadıysa, genel arama yap
        if not picking_type:
            _logger.create({
                'name': 'ariza_onarim',
                'type': 'server',
                'level': 'debug',
                'dbname': self._cr.dbname,
                'message': f"transfer_tipi belirtilmemiş, genel arama başlıyor - Mağaza: {magaza_adi}",
                'path': __file__,
                'func': '_create_stock_transfer',
                'line': 0,
            })
        
            # Önce mağaza adı ile 'Tamir Teslimatları' ara
            if magaza_adi:
                picking_type = self.env['stock.picking.type'].search([
                    ('name', '=', f'{magaza_adi}: Tamir Teslimatları')
                ], limit=1)
                if picking_type:
                    _logger.create({
                        'name': 'ariza_onarim',
                        'type': 'server',
                        'level': 'debug',
                        'dbname': self._cr.dbname,
                        'message': f"Mağaza adı ile 'Tamir Teslimatları' bulundu: {picking_type.name}",
                        'path': __file__,
                        'func': '_create_stock_transfer',
                        'line': 0,
                    })
                else:
                    picking_type = self.env['stock.picking.type'].search([
                        ('name', 'ilike', f'{magaza_adi}: Tamir Teslimatları')
                    ], limit=1)
                    if picking_type:
                        _logger.create({
                            'name': 'ariza_onarim',
                            'type': 'server',
                            'level': 'debug',
                            'dbname': self._cr.dbname,
                            'message': f"Mağaza adı ile ilike 'Tamir Teslimatları' bulundu: {picking_type.name}",
                            'path': __file__,
                            'func': '_create_stock_transfer',
                            'line': 0,
                        })
            
            # Mağaza adı ile bulunamazsa genel 'Tamir Teslimatları' ara
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('name', '=', 'Tamir Teslimatları')
            ], limit=1)
                if picking_type:
            _logger.create({
                'name': 'ariza_onarim',
                'type': 'server',
                'level': 'debug',
                'dbname': self._cr.dbname,
                        'message': f"Genel 'Tamir Teslimatları' bulundu: {picking_type.name}",
                        'path': __file__,
                        'func': '_create_stock_transfer',
                        'line': 0,
                    })
                else:
                    picking_type = self.env['stock.picking.type'].search([
                        ('name', 'ilike', 'Tamir Teslimatları')
                    ], limit=1)
                    if picking_type:
                        _logger.create({
                            'name': 'ariza_onarim',
                            'type': 'server',
                            'level': 'debug',
                            'dbname': self._cr.dbname,
                            'message': f"Genel ilike 'Tamir Teslimatları' bulundu: {picking_type.name}",
                            'path': __file__,
                            'func': '_create_stock_transfer',
                            'line': 0,
                        })
            
            # 'Tamir Teslimatları' bulunamazsa mağaza adı ile 'Tamir Alımlar' ara
            if not picking_type and magaza_adi:
                picking_type = self.env['stock.picking.type'].search([
                    ('name', '=', f'{magaza_adi}: Tamir Alımlar')
                ], limit=1)
                if picking_type:
                    _logger.create({
                        'name': 'ariza_onarim',
                        'type': 'server',
                        'level': 'debug',
                        'dbname': self._cr.dbname,
                        'message': f"Mağaza adı ile 'Tamir Alımlar' bulundu: {picking_type.name}",
                        'path': __file__,
                        'func': '_create_stock_transfer',
                        'line': 0,
                    })
                else:
                    picking_type = self.env['stock.picking.type'].search([
                        ('name', 'ilike', f'{magaza_adi}: Tamir Alımlar')
                    ], limit=1)
                    if picking_type:
                        _logger.create({
                            'name': 'ariza_onarim',
                            'type': 'server',
                            'level': 'debug',
                            'dbname': self._cr.dbname,
                            'message': f"Mağaza adı ile ilike 'Tamir Alımlar' bulundu: {picking_type.name}",
                'path': __file__,
                'func': '_create_stock_transfer',
                'line': 0,
            })
        
        # Eğer "Tamir Teslimatları" bulunamazsa, kaynak warehouse'dan internal picking type dene
        if not picking_type and kaynak.warehouse_id:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('warehouse_id', '=', kaynak.warehouse_id.id)
            ], limit=1)
            _logger.create({
                'name': 'ariza_onarim',
                'type': 'server',
                'level': 'debug',
                'dbname': self._cr.dbname,
                'message': f"Kaynak warehouse için internal picking type arama - Warehouse: {kaynak.warehouse_id.name}, Bulunan: {picking_type.name if picking_type else 'Yok'}",
                'path': __file__,
                'func': '_create_stock_transfer',
                'line': 0,
            })

        # Eğer hala bulunamazsa, hedef warehouse'dan internal picking type dene
        if not picking_type and hedef.warehouse_id:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('warehouse_id', '=', hedef.warehouse_id.id)
            ], limit=1)
            _logger.create({
                'name': 'ariza_onarim',
                'type': 'server',
                'level': 'debug',
                'dbname': self._cr.dbname,
                'message': f"Hedef warehouse için internal picking type arama - Warehouse: {hedef.warehouse_id.name}, Bulunan: {picking_type.name if picking_type else 'Yok'}",
                'path': __file__,
                'func': '_create_stock_transfer',
                'line': 0,
            })

        if not picking_type:
            raise UserError(_("'Tamir Teslimatları', 'Tamir Alımlar' veya 'İç Transfer' transfer tipi bulunamadı. Lütfen depo ve konum ayarlarınızı kontrol edin."))

        # E-İrsaliye numarası oluştur
        e_irsaliye_no = self.env['ir.sequence'].next_by_code('stock.picking.e.irsaliye')
        if not e_irsaliye_no:
            e_irsaliye_no = self.env['ir.sequence'].create({
                'name': 'E-İrsaliye Numarası',
                'code': 'stock.picking.e.irsaliye',
                'prefix': 'EIRS/%(year)s/',
                'padding': 5,
                'company_id': self.env.company.id,
            }).next_by_code('stock.picking.e.irsaliye')

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
            'delivery_type': 'matbu',  # Teslimat Türü matbu olarak default
        }
        stock_picking_fields = self.env['stock.picking'].fields_get()
        if 'e_irsaliye_no' in stock_picking_fields:
            picking_vals['e_irsaliye_no'] = e_irsaliye_no
        if 'sender_unit' in stock_picking_fields:
            picking_vals['sender_unit'] = self.analitik_hesap_id.name if self.analitik_hesap_id else False

        # Sürücü bilgisi ekle
        if self.vehicle_id:
            picking_vals['vehicle_id'] = self.vehicle_id.id

        # Eğer mağaza ürünü, işlem tipi kabul ve teknik servis TEDARİKÇİ ise partner_id'yi contact_id olarak ayarla
        if self.islem_tipi == 'kabul' and self.ariza_tipi == 'magaza' and self.teknik_servis == 'TEDARİKÇİ' and self.contact_id:
            picking_vals['partner_id'] = self.contact_id.id
        # Diğer durumlarda partner_id set edilmesin

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
            'message': f"Transfer OLUŞTURULDU! Arıza No: {self.name} - Picking ID: {picking.id} - Picking Type: {picking_type.name}",
            'path': __file__,
            'func': '_create_stock_transfer',
            'line': 0,
        })

        # 1. transferde chatter'a arıza tanımı ve önemli bilgiler yaz
        if transfer_tipi == 'ilk':
            msg = f"<b>Arıza Transferi Oluşturuldu</b><br/>"
            msg += f"Arıza Tanımı: {self.ariza_tanimi or '-'}<br/>"
            msg += f"Ürün: {self.urun or '-'}<br/>"
            msg += f"Model: {self.model or '-'}<br/>"
            msg += f"Müşteri: {self.partner_id.display_name if self.partner_id else '-'}<br/>"
            msg += f"Tarih: {fields.Date.today()}<br/>"
            if self.ariza_tanimi:
                msg += f"<br/><b>Ek Arıza Tanımı:</b> {self.ariza_tanimi}"
            picking.message_post(body=msg)
        # 2. transferde chatter'a onarım bilgisi ve önemli bilgiler yaz + hedef konumu kesin olarak güncelle
        elif transfer_tipi == 'ikinci':
            msg = f"<b>Onarım Sonrası Transfer Oluşturuldu</b><br/>"
            msg += f"Onarım Bilgisi: {self.onarim_bilgisi or '-'}<br/>"
            msg += f"Ürün: {self.urun or '-'}<br/>"
            msg += f"Model: {self.model or '-'}<br/>"
            msg += f"Müşteri: {self.partner_id.display_name if self.partner_id else '-'}<br/>"
            msg += f"Tarih: {fields.Date.today()}<br/>"
            if self.onarim_bilgisi:
                msg += f"<br/><b>Ek Onarım Bilgisi:</b> {self.onarim_bilgisi}"
            picking.message_post(body=msg)
            # Hedef konumu tekrar ve kesin olarak güncelle (partner_id override'ını engelle)
            if self.kaynak_konum_id:
                picking.location_dest_id = self.kaynak_konum_id.id
                # Tüm hareketlerin hedef konumunu da güncelle
                for move in picking.move_lines:
                    move.location_dest_id = self.kaynak_konum_id.id

        # Chatter'a mesaj ekle
        transfer_url = f"/web#id={picking.id}&model=stock.picking&view_type=form"
        durum = dict(self._fields['state'].selection).get(self.state, self.state)
        sms_bilgi = 'Aktif' if self.sms_gonderildi else 'Deaktif'
        self.message_post(
            body=f"<b>Yeni transfer oluşturuldu!</b><br/>"
                 f"Transfer No: <a href='{transfer_url}'>{picking.name}</a><br/>"
                 f"Kaynak: {kaynak.display_name}<br/>"
                 f"Hedef: {hedef.display_name}<br/>"
                 f"Tarih: {fields.Date.today()}<br/>"
                 f"Durum: {durum}<br/>"
                 f"SMS Gönderildi: {sms_bilgi}"
        )
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
        if not self.partner_id or not self.partner_id.email:
            return
        template = self.env.ref('ariza_onarim.email_template_ariza_bilgilendirme', raise_if_not_found=False)
        if template:
            template.with_context(
                email_to=self.partner_id.email,
                email_subject=subject,
                email_body=body
            ).send_mail(self.id, force_send=True)
        else:
            # Template bulunamazsa manuel mail gönder
            self.env['mail.mail'].create({
                'subject': subject,
                'body_html': body,
                'email_to': self.partner_id.email,
                'auto_delete': True,
            }).send()

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

    def action_personel_onayla(self):
        """Personel onaylama işlemi"""
        for record in self:
            if record.state == 'draft':
                record.state = 'personel_onay'
                # Personel onayı sonrası SMS gönder
                if record.islem_tipi == 'kabul' and record.ariza_tipi == 'musteri' and not record.sms_gonderildi:
                    message = f"Sayın {record.partner_id.name}., {record.urun} ürününüz teslim alındı, Ürününüz onarım sürecine alınmıştır. B021"
                    record._send_sms_to_customer(message)
                    record.sms_gonderildi = True
                # Personel onayında e-posta gönder
                mail_to = 'alper.tofta@zuhalmuzik.com'
                subject = f"Arıza Kaydı Personel Onayı: {record.name}"
                body = f"""
Arıza Kaydı Personel Onaylandı.<br/>
<b>Arıza No:</b> {record.name}<br/>
<b>Müşteri:</b> {record.partner_id.name if record.partner_id else '-'}<br/>
<b>Ürün:</b> {record.urun}<br/>
<b>Model:</b> {record.model}<br/>
<b>Arıza Tanımı:</b> {record.ariza_tanimi or '-'}<br/>
<b>Tarih:</b> {record.tarih or '-'}<br/>
<b>Teknik Servis:</b> {record.teknik_servis or '-'}<br/>
<b>Teknik Servis Adresi:</b> {record.teknik_servis_adres or '-'}<br/>
"""
                record.env['mail.mail'].create({
                    'subject': subject,
                    'body_html': body,
                    'email_to': mail_to,
                }).send()

    def action_teknik_onarim_baslat(self):
        """Teknik ekip onarım başlatma işlemi"""
        for record in self:
            if record.state == 'personel_onay':
                record.state = 'teknik_onarim'
                # Teknik onarım başlatma bildirimi
                record.message_post(
                    body=f"Teknik onarım süreci başlatıldı. Sorumlu: {record.sorumlu_id.name}",
                    subject="Teknik Onarım Başlatıldı"
                )

    def action_onayla(self):
        """Final onaylama işlemi - Sadece teknik_onarim durumundan çalışır"""
        for record in self:
            if record.state != 'teknik_onarim':
                raise UserError('Sadece teknik onarım aşamasındaki kayıtlar onaylanabilir!')
            
            # Mağaza ürünü ve teknik servis tedarikçi ise transferi tedarikçiye oluştur
            if record.ariza_tipi == 'magaza' and record.teknik_servis == 'TEDARİKÇİ' and not record.transfer_id:
                if not record.tedarikci_id or not record.tedarikci_id.property_stock_supplier:
                    raise UserError('Tedarikçi veya tedarikçi stok konumu eksik!')
                picking = record._create_stock_transfer(hedef_konum=record.tedarikci_id.property_stock_supplier)
                if picking:
                    record.transfer_id = picking.id
                    record.state = 'onaylandi'
                    return {
                        'type': 'ir.actions.act_window',
                        'name': 'Transfer Belgesi',
                        'res_model': 'stock.picking',
                        'res_id': picking.id,
                        'view_mode': 'form',
                    }
            # Mağaza ürünü ve teknik servis mağaza seçildiğinde transfer oluşturma
            if record.ariza_tipi == 'magaza' and record.teknik_servis == 'MAĞAZA':
                record.state = 'onaylandi'
                return
            # Mağaza ürünü için transfer oluşturma kontrolü
            if record.ariza_tipi == 'magaza' and record.teknik_servis == 'TEKNİK SERVİS':
                record.state = 'onaylandi'
                return
            # Mağaza ürünü için transfer oluştur
            if record.ariza_tipi == 'magaza' and not record.transfer_id:
                picking = record._create_stock_transfer()
                if picking:
                    record.transfer_id = picking.id
                    record.state = 'onaylandi'
                    return {
                        'type': 'ir.actions.act_window',
                        'name': 'Transfer Belgesi',
                        'res_model': 'stock.picking',
                        'res_id': picking.id,
                        'view_mode': 'form',
                    }
            
            # Ürün teslim işlemlerinde analitik bilgisi arıza kabulden gelsin
            if record.islem_tipi == 'teslim' and record.ariza_kabul_id:
                record.analitik_hesap_id = record.ariza_kabul_id.analitik_hesap_id

            record.state = 'onaylandi'
            # Onaylama sonrası otomatik kilitle
            record.action_lock()

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

    def action_lock(self):
        for rec in self:
            rec.state = 'kilitli'

    def action_unlock(self):
        for rec in self:
            rec.state = 'draft'

    def action_tamamla(self):
        # İlk transfer doğrulandıktan sonra tamamla butonu olsun
        if self.transfer_id:
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
            
            # Konumları ters çevirerek yeni transfer oluştur (çıkış transferi)
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
                # Eğer işlem tipi 'Arıza Kabul', arıza tipi 'Mağaza Ürünü', teknik servis 'TEDARİKÇİ' ise planlanan giriş transferi oluştur
                if ariza.islem_tipi == 'kabul' and ariza.ariza_tipi == 'magaza' and ariza.teknik_servis == 'TEDARİKÇİ':
                    # Giriş transferi: kaynak ve hedefi tekrar ters çevir
                    giris_transfer = ariza._create_stock_transfer(
                        kaynak_konum=mevcut_kaynak,  # Mağaza/depo
                        hedef_konum=mevcut_hedef    # Tedarikçi
                    )
                    # Giriş transferi planlanan olarak kalsın (onaylama yok)
                    if giris_transfer:
                        self.env['ir.logging'].create({
                            'name': 'ariza_onarim',
                            'type': 'server',
                            'level': 'info',
                            'dbname': self._cr.dbname,
                            'message': f"Planlanan giriş transferi oluşturuldu! Arıza No: {ariza.name} - Transfer ID: {giris_transfer.id} - Kaynak: {mevcut_kaynak.name} - Hedef: {mevcut_hedef.name}",
                            'path': __file__,
                            'func': 'action_tamamla',
                            'line': 0,
                        })
            else:
                raise UserError(_("Transfer oluşturulamadı! Lütfen kaynak ve hedef konumları kontrol edin."))
        
        return {'type': 'ir.actions.act_window_close'} 