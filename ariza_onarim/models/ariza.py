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
        ('magaza', 'Mağaza Ürünü'),
    ], string='Arıza Tipi', required=True, tracking=True)
    teknik_servis = fields.Selection([
        ('tedarikci', 'Tedarikçi'),
        ('dtl_beyoglu', 'DTL Beyoğlu'),
        ('dtl_okmeydani', 'DTL Ok Meydanı'),
        ('zuhal', 'Zuhal'),
        ('magaza', 'Mağaza'),
    ], string='Teknik Servis', tracking=True)
    magaza_ariza_tipi = fields.Selection([
        ('tedarikci', 'Tedarikçiye Gönderim'),
        ('teknik_servis', 'Teknik Servis'),
    ], string='Mağaza Arıza Tipi', tracking=True)
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
        domain="[('move_id.move_type', 'in', ['out_invoice', 'out_refund']), ('move_id.state', '=', 'posted'), ('move_id.partner_id', '=', partner_id)]")
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('New'):
                # Benzersiz arıza numarası oluştur
                sequence = self.env['ir.sequence'].next_by_code('ariza.kayit')
                if not sequence:
                    # Eğer sequence yoksa oluştur
                    self.env['ir.sequence'].create({
                        'name': 'Arıza Kayıt',
                        'code': 'ariza.kayit',
                        'prefix': 'ARZ/%(year)s/',
                        'padding': 5,
                        'company_id': self.env.company.id,
                    })
                    sequence = self.env['ir.sequence'].next_by_code('ariza.kayit')
                vals['name'] = sequence
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
            self.magaza_ariza_tipi = False
            self.analitik_hesap_id = False
            self.kaynak_konum_id = False
            self.hedef_konum_id = False
            if not self.siparis_yok:
                self.urun = False
                self.model = False
        elif self.ariza_tipi == 'magaza':
            self.partner_id = False
            self.siparis_yok = False
            self.invoice_line_id = False
            self.urun = False
            self.model = False
        elif self.ariza_tipi == 'teknik':
            self.partner_id = False
            self.siparis_yok = False
            self.invoice_line_id = False
            self.urun = False
            self.model = False
            self.magaza_ariza_tipi = False

    @api.onchange('teknik_servis', 'analitik_hesap_id')
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
            if self.magaza_ariza_tipi == 'tedarikci' and self.tedarikci_id:
                if self.tedarikci_id.property_stock_supplier:
                    self.hedef_konum_id = self.tedarikci_id.property_stock_supplier
            # Teknik servis ise hedef konum DTL/Stok
            elif self.magaza_ariza_tipi == 'teknik_servis':
                dtl_konum = self.env['stock.location'].search([
                    ('name', '=', 'DTL/Stok'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if dtl_konum:
                    self.hedef_konum_id = dtl_konum

    @api.onchange('invoice_line_id', 'islem_tipi', 'siparis_yok')
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
                                self._onchange_tedarikci_id()
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
                                self._onchange_tedarikci_id()
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
                self._onchange_tedarikci_id()
        else:
            self.tedarikci_id = False
            self.tedarikci_adresi = False
            self.tedarikci_telefon = False
            self.tedarikci_email = False
            self.marka_urunleri_ids = False
            self.magaza_urun_id = False

    @api.onchange('tedarikci_id')
    def _onchange_tedarikci_id(self):
        if self.tedarikci_id:
            self.tedarikci_adresi = self.tedarikci_id.street
            self.tedarikci_telefon = self.tedarikci_id.phone
            self.tedarikci_email = self.tedarikci_id.email
            # Tedarikçiye gönderim ise hedef konum tedarikçi adresi
            if self.magaza_ariza_tipi == 'tedarikci' and self.tedarikci_id.property_stock_supplier:
                self.hedef_konum_id = self.tedarikci_id.property_stock_supplier

    @api.onchange('islem_tipi')
    def _onchange_islem_tipi(self):
        if self.islem_tipi != 'teslim':
            self.garanti_kapsaminda_mi = False

    @api.onchange('ariza_tipi', 'analitik_hesap_id')
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
                'garanti_suresi', 'garanti_bitis_tarihi', 'kalan_garanti', 'magaza_ariza_tipi', 'transfer_metodu',
                'magaza_urun_id', 'marka_urunleri_ids', 'teknik_servis', 'onarim_bilgisi', 'ucret_bilgisi', 'garanti_kapsaminda_mi', 'ariza_tipi',
                'invoice_line_id', 'siparis_yok'
            ]
            for field in fields_to_copy:
                setattr(self, field, getattr(self.ariza_kabul_id, field, False))

    def _create_stock_transfer(self):
        _logger = self.env['ir.logging']
        if not self.analitik_hesap_id:
            _logger.create({
                'name': 'ariza_onarim',
                'type': 'server',
                'level': 'debug',
                'dbname': self._cr.dbname,
                'message': f"Transfer oluşturulamadı: analitik_hesap_id yok. Arıza No: {self.name}",
                'path': __file__,
                'func': '_create_stock_transfer',
                'line': 0,
            })
            return
        # Müşteri ürünü işlemlerinde konumları otomatik ayarla
        if self.ariza_tipi == 'musteri':
            # Kaynak konum müşteri konumu
            if self.partner_id and self.partner_id.property_stock_customer:
                self.kaynak_konum_id = self.partner_id.property_stock_customer
            else:
                customer_location = self.env['stock.location'].search([
                    ('usage', '=', 'customer'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if customer_location:
                    self.kaynak_konum_id = customer_location
            ariza_konum = self.env['stock.location'].search([
                ('name', '=', 'arıza/stok'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            if ariza_konum:
                self.hedef_konum_id = ariza_konum
        if not self.kaynak_konum_id or not self.hedef_konum_id:
            _logger.create({
                'name': 'ariza_onarim',
                'type': 'server',
                'level': 'debug',
                'dbname': self._cr.dbname,
                'message': f"Transfer oluşturulamadı: kaynak veya hedef konum yok. Arıza No: {self.name} - Kaynak: {self.kaynak_konum_id} - Hedef: {self.hedef_konum_id}",
                'path': __file__,
                'func': '_create_stock_transfer',
                'line': 0,
            })
            return
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '=', self.kaynak_konum_id.warehouse_id.id)
        ], limit=1)
        if not picking_type:
            _logger.create({
                'name': 'ariza_onarim',
                'type': 'server',
                'level': 'debug',
                'dbname': self._cr.dbname,
                'message': f"Transfer oluşturulamadı: picking_type yok. Arıza No: {self.name}",
                'path': __file__,
                'func': '_create_stock_transfer',
                'line': 0,
            })
            raise UserError(_("Transfer tipi bulunamadı."))
        picking_vals = {
            'location_id': self.kaynak_konum_id.id,
            'location_dest_id': self.hedef_konum_id.id,
            'picking_type_id': picking_type.id,
            'move_type': 'direct',
            'immediate_transfer': True,
            'company_id': self.env.company.id,
            'origin': self.name,
            'note': f"Arıza Kaydı: {self.name}\nÜrün: {self.urun}\nModel: {self.model}",
        }
        picking = self.env['stock.picking'].create(picking_vals)
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
        # Mağaza ürünü için transfer oluştur
        if self.ariza_tipi == 'magaza' and not self.transfer_id:
            picking = self._create_stock_transfer()
            if picking:
                self.transfer_id = picking.id
        # Müşteri ürünü işlemlerinde SMS gönder
        if self.ariza_tipi == 'musteri' and not self.sms_gonderildi:
            message = f"Sayın {self.partner_id.name}, {self.urun} ürününüz teslim alındı. Ürününüz onarım sürecine alınmıştır."
            self._send_sms_to_customer(message)
            self.sms_gonderildi = True

        # Ürün teslim işlemlerinde analitik bilgisi arıza kabulden gelsin
        if self.islem_tipi == 'teslim' and self.ariza_kabul_id:
            self.analitik_hesap_id = self.ariza_kabul_id.analitik_hesap_id

        self.state = 'onaylandi'

    def action_tamamla(self):
        # Sadece kabul işlemlerinde tamamla butonu olsun
        if self.islem_tipi == 'kabul':
            # SMS gönderimi buraya taşındı
            if self.ariza_tipi == 'musteri' and self.partner_id and self.partner_id.phone:
                magaza_adi = self._clean_magaza_adi(self.teslim_magazasi_id.name) if self.teslim_magazasi_id else ''
                onarim = self.onarim_bilgisi or ''
                garanti = dict(self._fields['garanti_kapsaminda_mi'].selection).get(self.garanti_kapsaminda_mi, '')
                ucret = self.ucret_bilgisi or ''
                durum = dict(self._fields['state'].selection).get(self.state, '')
                sms_mesaji = f"Sayın {self.partner_id.name} {self.name}, {self.urun} ürününüz {magaza_adi} mağazamızdan teslim alabilirsiniz.\nDurum: {durum}\nGaranti Kapsamında mı?: {garanti}\nOnarım Bilgisi: {onarim}\nÜcret Bilgisi: {ucret}\nTeslim Mağazası: {self.teslim_magazasi_id.name if self.teslim_magazasi_id else ''}\nİyi günler dileriz."
                self._send_sms_to_customer(sms_mesaji)
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
        teknik_servis_adres = ''
        if self.teknik_servis == 'tedarikci' and self.tedarikci_id:
            teknik_servis_adres = self.tedarikci_adresi or self.tedarikci_id.street or ''
        elif self.teknik_servis == 'zuhal':
            teknik_servis_adres = 'Halkalı merkez mh. Dereboyu cd. No:8/B'
        elif self.teknik_servis == 'dtl_beyoglu':
            teknik_servis_adres = 'Şahkulu mh. Nakkas çıkmazı No: 1/1 No:10-46 / 47'
        elif self.teknik_servis == 'dtl_okmeydani':
            teknik_servis_adres = 'MAHMUT ŞEVKET PAŞA MAH. ŞAHİNKAYA SOK NO 31 OKMEYDANI'
        # Rapor contextine adresi ekle
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
                        self._onchange_tedarikci_id()
            else:
                self.marka_id = False
                self.tedarikci_id = False
                self.tedarikci_adresi = False
                self.tedarikci_telefon = False
                self.tedarikci_email = False

    def action_print_delivery(self):
        if self.transfer_id:
            return self.env.ref('stock.action_report_delivery').report_action(self.transfer_id) 