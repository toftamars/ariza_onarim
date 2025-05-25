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
        ('teknik_servis', 'Teknik Servis'),
    ], string='İşlem Tipi', required=True, tracking=True)
    ariza_tipi = fields.Selection([
        ('musteri', 'Müşteri Ürünü'),
        ('magaza', 'Mağaza Ürünü'),
    ], string='Arıza Tipi', required=True, tracking=True)
    magaza_ariza_tipi = fields.Selection([
        ('tedarikci', 'Tedarikçiye Gönderim'),
        ('teknik_servis', 'Teknik Servis'),
    ], string='Mağaza Arıza Tipi', tracking=True)
    transfer_metodu = fields.Selection([
        ('matbuu', 'Matbuu'),
        ('e_irsaliye', 'E-İrsaliye'),
    ], string='Transfer Metodu', tracking=True, default='matbuu')
    partner_id = fields.Many2one('res.partner', string='Müşteri', tracking=True)
    analitik_hesap_id = fields.Many2one('account.analytic.account', string='Analitik Hesap', tracking=True)
    tedarikci_id = fields.Many2one('res.partner', string='Tedarikçi', tracking=True)
    sorumlu_id = fields.Many2one('res.users', string='Sorumlu', default=lambda self: self.env.user, tracking=True)
    tarih = fields.Date(string='Tarih', default=fields.Date.context_today, tracking=True)
    state = fields.Selection([
        ('draft', 'Taslak'),
        ('onaylandi', 'Onaylandı'),
        ('tamamlandi', 'Tamamlandı'),
        ('iptal', 'İptal'),
    ], string='Durum', default='draft', tracking=True)
    siparis_yok = fields.Boolean(string='Sipariş Yok', default=False)
    sale_order_id = fields.Many2one('sale.order', string='Satış Siparişi')
    pos_order_id = fields.Many2one('pos.order', string='POS Siparişi')
    fatura_tarihi = fields.Date(string='Fatura Tarihi', compute='_compute_fatura_tarihi', store=True)
    urun = fields.Char(string='Ürün')
    marka = fields.Char(string='Marka')
    model = fields.Char(string='Model')
    garanti_durumu = fields.Selection([
        ('garanti_kapsaminda', 'Garanti Kapsamında'),
        ('garanti_disinda', 'Garanti Dışında'),
    ], string='Garanti Durumu')
    aciklama = fields.Text(string='Açıklama')
    notlar = fields.Text(string='Notlar')
    transfer_id = fields.Many2one('stock.picking', string='Transfer', readonly=True)
    transfer_irsaliye = fields.Char(string='Transfer İrsaliye No')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ariza.kayit') or _('New')
        return super().create(vals_list)

    @api.depends('sale_order_id', 'pos_order_id')
    def _compute_fatura_tarihi(self):
        for record in self:
            if record.sale_order_id and record.sale_order_id.invoice_ids:
                record.fatura_tarihi = record.sale_order_id.invoice_ids[0].invoice_date
            elif record.pos_order_id and record.pos_order_id.account_move:
                record.fatura_tarihi = record.pos_order_id.account_move.invoice_date
            else:
                record.fatura_tarihi = False

    @api.onchange('ariza_tipi')
    def _onchange_ariza_tipi(self):
        if self.ariza_tipi == 'musteri':
            self.magaza_ariza_tipi = False
            self.analitik_hesap_id = False
            self.tedarikci_id = False
            self.transfer_metodu = False
        elif self.ariza_tipi == 'magaza':
            self.partner_id = False
            self.siparis_yok = False
            self.sale_order_id = False
            self.pos_order_id = False
            self.urun = False
            self.marka = False
            self.model = False
            self.garanti_durumu = False

    @api.onchange('magaza_ariza_tipi')
    def _onchange_magaza_ariza_tipi(self):
        if self.magaza_ariza_tipi == 'tedarikci':
            self.tedarikci_id = False
        elif self.magaza_ariza_tipi == 'teknik_servis':
            self.analitik_hesap_id = False

    @api.onchange('analitik_hesap_id')
    def _onchange_analitik_hesap_id(self):
        if self.analitik_hesap_id and self.ariza_tipi == 'magaza':
            self._create_stock_transfer()

    def _create_stock_transfer(self):
        if not self.analitik_hesap_id:
            return

        # Kaynak ve hedef konumları belirle
        source_location = self.env['stock.location'].search([
            ('name', '=', f"{self.analitik_hesap_id.name}/Stok")
        ], limit=1)
        
        if not source_location:
            raise UserError(_(f"{self.analitik_hesap_id.name} için stok konumu bulunamadı."))

        if self.magaza_ariza_tipi == 'tedarikci':
            dest_location = self.env['stock.location'].search([
                ('name', '=', 'Tedarikçi/Stok')
            ], limit=1)
        else:
            dest_location = self.env['stock.location'].search([
                ('name', '=', 'Arıza/Stok')
            ], limit=1)

        if not dest_location:
            raise UserError(_("Hedef stok konumu bulunamadı."))

        # Transfer oluştur
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '=', source_location.warehouse_id.id)
        ], limit=1)

        if not picking_type:
            raise UserError(_("Transfer tipi bulunamadı."))

        picking_vals = {
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
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
        if self.ariza_tipi == 'magaza' and self.analitik_hesap_id:
            self._create_stock_transfer()

    def action_tamamla(self):
        self.state = 'tamamlandi'

    def action_iptal(self):
        self.state = 'iptal'
        if self.transfer_id:
            self.transfer_id.action_cancel() 