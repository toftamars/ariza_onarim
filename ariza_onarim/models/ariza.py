from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

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
        ('teknik', 'Teknik Servis'),
    ], string='Arıza Tipi', required=True, tracking=True)
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
    analitik_hesap_id = fields.Many2one('account.analytic.account', string='Analitik Hesap', tracking=True)
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
    garanti_durumu = fields.Selection([
        ('garanti_kapsaminda', 'Garanti Kapsamında'),
        ('garanti_disinda', 'Garanti Dışında'),
    ], string='Garanti Durumu', required=True)
    aciklama = fields.Text(string='Açıklama', required=True)
    notlar = fields.Text(string='Notlar')
    transfer_id = fields.Many2one('stock.picking', string='Transfer', readonly=True)
    transfer_irsaliye = fields.Char(string='Transfer İrsaliye No')
    company_id = fields.Many2one('res.company', string='Şirket', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
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
                self.garanti_durumu = False
        elif self.ariza_tipi == 'magaza':
            self.partner_id = False
            self.siparis_yok = False
            self.invoice_line_id = False
            self.urun = False
            self.model = False
            self.garanti_durumu = False
        elif self.ariza_tipi == 'teknik':
            self.partner_id = False
            self.siparis_yok = False
            self.invoice_line_id = False
            self.urun = False
            self.model = False
            self.garanti_durumu = False
            self.magaza_ariza_tipi = False

    @api.onchange('magaza_ariza_tipi')
    def _onchange_magaza_ariza_tipi(self):
        if self.magaza_ariza_tipi == 'tedarikci':
            self.tedarikci_id = False
        elif self.magaza_ariza_tipi == 'teknik_servis':
            self.analitik_hesap_id = False
            self.kaynak_konum_id = False
            # DTL/Stok konumunu bul
            dtl_konum = self.env['stock.location'].search([
                ('name', '=', 'DTL/Stok'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            if dtl_konum:
                self.hedef_konum_id = dtl_konum
            else:
                self.hedef_konum_id = False

    @api.onchange('analitik_hesap_id')
    def _onchange_analitik_hesap_id(self):
        if self.analitik_hesap_id and self.ariza_tipi in ['magaza', 'teknik']:
            # Analitik hesaptan kaynak konumu al
            if hasattr(self.analitik_hesap_id, 'konum_id') and self.analitik_hesap_id.konum_id:
                self.kaynak_konum_id = self.analitik_hesap_id.konum_id
            
            # Eğer mağaza arıza tipi teknik servis ise hedef konumu da ayarla
            if self.magaza_ariza_tipi == 'teknik_servis':
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
                self.urun = product.name
                self.model = product.default_code or ''
                self.garanti_durumu = 'garanti_kapsaminda' if product.warranty else 'garanti_disinda'

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if not self.partner_id:
            self.invoice_line_id = False
            self.siparis_yok = False
            self.urun = False
            self.model = False
            self.garanti_durumu = False

    @api.onchange('marka_id')
    def _onchange_marka_id(self):
        if self.marka_id and self.marka_id.partner_id:
            self.tedarikci_id = self.marka_id.partner_id
            self._onchange_tedarikci_id()

    @api.onchange('tedarikci_id')
    def _onchange_tedarikci_id(self):
        if self.tedarikci_id:
            self.tedarikci_adresi = self.tedarikci_id.street
            self.tedarikci_telefon = self.tedarikci_id.phone
            self.tedarikci_email = self.tedarikci_id.email

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

    def action_onayla(self):
        self.state = 'onaylandi'
        if self.ariza_tipi in ['magaza', 'teknik'] and self.analitik_hesap_id and self.kaynak_konum_id and self.hedef_konum_id:
            self._create_stock_transfer()

    def action_tamamla(self):
        self.state = 'tamamlandi'

    def action_iptal(self):
        self.state = 'iptal'
        if self.transfer_id:
            self.transfer_id.action_cancel() 