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
    islem_tipi = fields.Selection([
        ('kabul', 'Arıza Kabul'),
        ('teslim', 'Ürün Teslim'),
    ], string='İşlem Tipi', required=True, tracking=True)
    ariza_tipi = fields.Selection([
        ('musteri', 'Müşteri Ürünü'),
        ('magaza', 'Mağaza Ürünü'),
    ], string='Arıza Tipi', required=True, tracking=True)
    teknik_servis = fields.Selection([
        ('tedarikci', 'Tedarikçi'),
        ('dtl', 'DTL'),
        ('zuhal', 'Zuhal'),
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
    tedarikci_adresi = fields.Text(string='Teslim Adresi', tracking=True)
    tedarikci_telefon = fields.Char(string='Tedarikçi Telefon', tracking=True)
    tedarikci_email = fields.Char(string='Tedarikçi E-posta', tracking=True)
    sorumlu_id = fields.Many2one('res.users', string='Sorumlu', default=lambda self: self.env.user, tracking=True)
    tarih = fields.Date(string='Tarih', default=fields.Date.context_today, tracking=True)
    state = fields.Selection([
        ('draft', 'Taslak'),
        ('onaylandi', 'Onaylandı'),
        ('tamamlandi', 'Tamamlandı'),
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
    transfer_id = fields.Many2one('stock.picking', string='Transfer', readonly=True)
    transfer_irsaliye = fields.Char(string='Transfer İrsaliye No')
    company_id = fields.Many2one('res.company', string='Şirket', default=lambda self: self.env.company)
    onarim_ucreti = fields.Float(string='Onarım Ücreti', tracking=True)
    yapilan_islemler = fields.Text(string='Yapılan İşlemler', tracking=True)
    marka_urunleri_ids = fields.Many2many(
        'product.product',
        string='Marka Ürünleri',
        tracking=True
    )
    transferler_ids = fields.Many2many('stock.picking', string='Transferler', tracking=True)
    ariza_kabul_id = fields.Many2one('ariza.kayit', string='Arıza Kabul No', domain="[('islem_tipi', '=', 'kabul')]", tracking=True)
    onarim_bilgisi = fields.Text(string='Onarım Bilgisi', tracking=True)
    ucret_bilgisi = fields.Char(string='Ücret Bilgisi', tracking=True)
    magaza_urun_id = fields.Many2one(
        'product.product',
        string='Ürün',
        tracking=True
    )
    sms_gonderildi = fields.Boolean(string='SMS Gönderildi', default=False, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ariza.kayit') or _('New')
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
        if self.teknik_servis == 'tedarikci':
            # Marka alanını göster
            self.marka_id = False
            # Hedef konum tedarikçi/stok
            tedarikci_konum = self.env['stock.location'].search([
                ('name', '=', 'tedarikçi/stok'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            if tedarikci_konum:
                self.hedef_konum_id = tedarikci_konum
            # Kaynak konum analitik hesaba ait stok konumu
            if self.analitik_hesap_id:
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
        elif self.teknik_servis == 'dtl':
            # Hedef konum DTL/Stok
            dtl_konum = self.env['stock.location'].search([
                ('name', '=', 'DTL/Stok'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            if dtl_konum:
                self.hedef_konum_id = dtl_konum
            # Kaynak konum analitik hesaba ait stok konumu
            if self.analitik_hesap_id:
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
        elif self.teknik_servis == 'zuhal':
            # Hedef konum arıza/stok
            ariza_konum = self.env['stock.location'].search([
                ('name', '=', 'arıza/stok'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            if ariza_konum:
                self.hedef_konum_id = ariza_konum
            # Kaynak konum analitik hesaba ait stok konumu
            if self.analitik_hesap_id:
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
                    if hasattr(product.product_tmpl_id, 'brand_id') and product.product_tmpl_id.brand_id:
                        self.marka_id = product.product_tmpl_id.brand_id.id
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
                    if hasattr(product.product_tmpl_id, 'brand_id') and product.product_tmpl_id.brand_id:
                        self.marka_id = product.product_tmpl_id.brand_id.id
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
            # Mağaza ürünü için ürünleri filtrele
            if self.ariza_tipi == 'magaza':
                domain = [('product_tmpl_id.brand_id', '=', self.marka_id.id)]
                return {'domain': {'magaza_urun_id': domain}}
            # Marka ürünlerini filtrele
            if self.ariza_tipi in ['magaza', 'teknik', 'musteri']:
                domain = [('product_tmpl_id.brand_id', '=', self.marka_id.id)]
                return {'domain': {'marka_urunleri_ids': domain}}
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
        if not self.analitik_hesap_id or not self.kaynak_konum_id or not self.hedef_konum_id:
            return

        # Transfer oluştur
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '=', self.kaynak_konum_id.warehouse_id.id)
        ], limit=1)

        if not picking_type:
            raise UserError(_("Transfer tipi bulunamadı."))

        picking_vals = {
            'location_id': self.kaynak_konum_id.id,
            'location_dest_id': self.hedef_konum_id.id,
            'picking_type_id': picking_type.id,
            'move_type': 'direct',
            'immediate_transfer': True,
            'company_id': self.env.company.id,
            'origin': self.name,
            'note': self.aciklama or '',
        }

        picking = self.env['stock.picking'].create(picking_vals)
        self.transfer_id = picking.id

    def _send_sms_to_customer(self, message):
        if self.partner_id and self.partner_id.phone:
            sms_obj = self.env['sms.sms'].create({
                'partner_id': self.partner_id.id,
                'to': self.partner_id.phone,
                'body': message,
                'state': 'outgoing',
            })
            sms_obj.send()

    def action_onayla(self):
        self.state = 'onaylandi'
        # SMS gönderimi
        if self.ariza_tipi == 'musteri' and self.partner_id and self.partner_id.phone:
            self._send_sms_to_customer('Arıza kaydınız alınmıştır. Takip No: %s' % self.name)
        # Mağaza ürünü ve tedarikçi seçili ise transfer oluştur
        if self.ariza_tipi == 'magaza' and self.analitik_hesap_id and self.tedarikci_id:
            # Analitik hesabın stok konumunu bul
            kaynak_konum = None
            dosya_yolu = os.path.join(os.path.dirname(__file__), '..', 'Analitik Bilgileri.txt')
            hesap_adi = self.analitik_hesap_id.name.strip().lower()
            try:
                with open(dosya_yolu, 'r', encoding='utf-8') as f:
                    for satir in f:
                        if hesap_adi in satir.lower():
                            parcalar = satir.strip().split('\t')
                            if len(parcalar) == 2:
                                konum_kodu = parcalar[1]
                                kaynak_konum = self.env['stock.location'].search([
                                    ('name', '=', konum_kodu),
                                    ('company_id', '=', self.env.company.id)
                                ], limit=1)
                                break
            except Exception as e:
                pass
            hedef_konum = self.tedarikci_id.property_stock_supplier if self.tedarikci_id.property_stock_supplier else False
            if kaynak_konum and hedef_konum:
                picking_type = self.env['stock.picking.type'].search([
                    ('code', '=', 'internal'),
                    ('warehouse_id', '=', kaynak_konum.warehouse_id.id)
                ], limit=1)
                if not picking_type:
                    raise UserError("Transfer tipi bulunamadı.")
                picking_vals = {
                    'location_id': kaynak_konum.id,
                    'location_dest_id': hedef_konum.id,
                    'picking_type_id': picking_type.id,
                    'move_type': 'direct',
                    'immediate_transfer': True,
                    'company_id': self.env.company.id,
                    'origin': self.name,
                }
                picking = self.env['stock.picking'].create(picking_vals)
                self.transfer_id = picking.id
                self.transferler_ids = [(4, picking.id)]
                picking.button_validate()
        elif self.ariza_tipi == 'magaza' and self.analitik_hesap_id and self.kaynak_konum_id and self.hedef_konum_id:
            self._create_stock_transfer()
        elif self.magaza_ariza_tipi == 'tedarikci' and self.ariza_tipi == 'magaza' and self.analitik_hesap_id and self.kaynak_konum_id and self.tedarikci_id:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('warehouse_id', '=', self.kaynak_konum_id.warehouse_id.id)
            ], limit=1)
            if not picking_type:
                raise UserError("Transfer tipi bulunamadı.")
            picking_vals = {
                'location_id': self.kaynak_konum_id.id,
                'location_dest_id': self.tedarikci_id.property_stock_supplier.id if self.tedarikci_id.property_stock_supplier else False,
                'picking_type_id': picking_type.id,
                'move_type': 'direct',
                'immediate_transfer': True,
                'company_id': self.env.company.id,
                'origin': self.name,
                'note': self.aciklama or '',
            }
            picking = self.env['stock.picking'].create(picking_vals)
            self.transfer_id = picking.id
            self.transferler_ids = [(4, picking.id)]
            picking.button_validate()
        elif self.ariza_tipi == 'teknik' and self.analitik_hesap_id and self.kaynak_konum_id and self.hedef_konum_id:
            self._create_stock_transfer()

    def action_tamamla(self):
        self.state = 'tamamlandi'
        # SMS gönderimi
        if self.ariza_tipi == 'musteri' and self.partner_id and self.partner_id.phone:
            self._send_sms_to_customer('Ürününüz teslim edilmeye hazırdır. Takip No: %s' % self.name)

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
        return self.env.ref('ariza_onarim.action_report_ariza_kayit').report_action(self)

    def action_print_teslim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_teslim').report_action(self)

    def action_print_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_onarim').report_action(self)

    def action_print_tedarikci(self):
        return self.env.ref('ariza_onarim.action_report_ariza_tedarikci').report_action(self)

    def action_print_dtl(self):
        return self.env.ref('ariza_onarim.action_report_ariza_dtl').report_action(self)

    def action_print_zuhal(self):
        return self.env.ref('ariza_onarim.action_report_ariza_zuhal').report_action(self)

    def action_print_magaza(self):
        return self.env.ref('ariza_onarim.action_report_ariza_magaza').report_action(self)

    def action_print_musteri(self):
        return self.env.ref('ariza_onarim.action_report_ariza_musteri').report_action(self)

    def action_print_teknik(self):
        return self.env.ref('ariza_onarim.action_report_ariza_teknik').report_action(self)

    def action_print_tedarikci_teknik(self):
        return self.env.ref('ariza_onarim.action_report_ariza_tedarikci_teknik').report_action(self)

    def action_print_dtl_teknik(self):
        return self.env.ref('ariza_onarim.action_report_ariza_dtl_teknik').report_action(self)

    def action_print_zuhal_teknik(self):
        return self.env.ref('ariza_onarim.action_report_ariza_zuhal_teknik').report_action(self)

    def action_print_magaza_teknik(self):
        return self.env.ref('ariza_onarim.action_report_ariza_magaza_teknik').report_action(self)

    def action_print_musteri_teknik(self):
        return self.env.ref('ariza_onarim.action_report_ariza_musteri_teknik').report_action(self)

    def action_print_tedarikci_teslim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_tedarikci_teslim').report_action(self)

    def action_print_dtl_teslim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_dtl_teslim').report_action(self)

    def action_print_zuhal_teslim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_zuhal_teslim').report_action(self)

    def action_print_magaza_teslim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_magaza_teslim').report_action(self)

    def action_print_musteri_teslim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_musteri_teslim').report_action(self)

    def action_print_tedarikci_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_tedarikci_onarim').report_action(self)

    def action_print_dtl_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_dtl_onarim').report_action(self)

    def action_print_zuhal_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_zuhal_onarim').report_action(self)

    def action_print_magaza_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_magaza_onarim').report_action(self)

    def action_print_musteri_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_musteri_onarim').report_action(self)

    def action_print_tedarikci_teknik_teslim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_tedarikci_teknik_teslim').report_action(self)

    def action_print_dtl_teknik_teslim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_dtl_teknik_teslim').report_action(self)

    def action_print_zuhal_teknik_teslim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_zuhal_teknik_teslim').report_action(self)

    def action_print_magaza_teknik_teslim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_magaza_teknik_teslim').report_action(self)

    def action_print_musteri_teknik_teslim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_musteri_teknik_teslim').report_action(self)

    def action_print_tedarikci_teknik_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_tedarikci_teknik_onarim').report_action(self)

    def action_print_dtl_teknik_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_dtl_teknik_onarim').report_action(self)

    def action_print_zuhal_teknik_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_zuhal_teknik_onarim').report_action(self)

    def action_print_magaza_teknik_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_magaza_teknik_onarim').report_action(self)

    def action_print_musteri_teknik_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_musteri_teknik_onarim').report_action(self)

    def action_print_tedarikci_teslim_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_tedarikci_teslim_onarim').report_action(self)

    def action_print_dtl_teslim_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_dtl_teslim_onarim').report_action(self)

    def action_print_zuhal_teslim_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_zuhal_teslim_onarim').report_action(self)

    def action_print_magaza_teslim_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_magaza_teslim_onarim').report_action(self)

    def action_print_musteri_teslim_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_musteri_teslim_onarim').report_action(self)

    def action_print_tedarikci_teknik_teslim_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_tedarikci_teknik_teslim_onarim').report_action(self)

    def action_print_dtl_teknik_teslim_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_dtl_teknik_teslim_onarim').report_action(self)

    def action_print_zuhal_teknik_teslim_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_zuhal_teknik_teslim_onarim').report_action(self)

    def action_print_magaza_teknik_teslim_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_magaza_teknik_teslim_onarim').report_action(self)

    def action_print_musteri_teknik_teslim_onarim(self):
        return self.env.ref('ariza_onarim.action_report_ariza_musteri_teknik_teslim_onarim').report_action(self)

    @api.onchange('magaza_urun_id')
    def _onchange_magaza_urun_id(self):
        if self.magaza_urun_id:
            # Ürün seçilince marka otomatik gelsin
            if hasattr(self.magaza_urun_id.product_tmpl_id, 'brand_id') and self.magaza_urun_id.product_tmpl_id.brand_id:
                self.marka_id = self.magaza_urun_id.product_tmpl_id.brand_id.id
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