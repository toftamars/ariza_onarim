from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ArizaKayit(models.Model):
    _name = 'ariza.kayit'
    _description = 'Arıza Kayıt'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Arıza No', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    islem_tipi = fields.Selection([
        ('kabul', 'Arıza Kabulü'),
        ('teslim', 'Arıza Teslimi')
    ], string='İşlem Tipi', required=True, default='kabul', tracking=True)
    
    ariza_tipi = fields.Selection([
        ('musteri', 'Müşteri Ürünü'),
        ('magaza', 'Mağaza Ürünü'),
        ('teknik', 'Teknik Servis')
    ], string='Arıza Tipi', required=True, tracking=True)
    
    # Müşteri Ürünü Alanları
    partner_id = fields.Many2one('res.partner', string='Müşteri', tracking=True)
    marka = fields.Char(string='Marka', tracking=True)
    model = fields.Char(string='Model', tracking=True)
    sale_order_id = fields.Many2one('sale.order', string='Sipariş', tracking=True)
    pos_order_id = fields.Many2one('pos.order', string='POS Siparişi', tracking=True)
    siparis_yok = fields.Boolean(string='Sipariş Yok', default=False, tracking=True)
    urun = fields.Char(string='Ürün', tracking=True)
    fatura_tarihi = fields.Date(string='Fatura Tarihi', tracking=True)
    aciklama = fields.Text(string='Arıza ve Onarım Tanımı', required=True, tracking=True)
    garanti_durumu = fields.Selection([
        ('var', 'Garantisi Var'),
        ('yok', 'Garantisi Yok')
    ], string='Garanti Durumu', tracking=True)
    notlar = fields.Text(string='Notlar', tracking=True)
    
    # Mağaza Ürünü Alanları
    magaza_ariza_tipi = fields.Selection([
        ('depo', 'Depo Arıza'),
        ('tedarikci', 'Tedarikçiler'),
        ('nefesli', 'Nefesli Arıza')
    ], string='Mağaza Arıza Tipi', tracking=True)
    analitik_hesap_id = fields.Many2one('account.analytic.account', string='Analitik Hesap', tracking=True)
    tedarikci_id = fields.Many2one('res.partner', string='Tedarikçi', domain="[('supplier_rank', '>', 0)]", tracking=True)
    transfer_irsaliye = fields.Boolean(string='İrsaliye Oluştur', default=False, tracking=True)
    transfer_id = fields.Many2one('stock.picking', string='Transfer', tracking=True)
    
    # Ortak Alanlar
    tarih = fields.Date(string='İşlem Tarihi', required=True, default=fields.Date.context_today, tracking=True)
    sorumlu_id = fields.Many2one('res.users', string='Sorumlu', required=True, default=lambda self: self.env.user, tracking=True)
    state = fields.Selection([
        ('draft', 'Taslak'),
        ('onaylandi', 'Onaylandı'),
        ('tamamlandi', 'Tamamlandı'),
        ('iptal', 'İptal')
    ], string='Durum', default='draft', tracking=True)
    acik_ariza_sayisi = fields.Integer(string='Açık Arıza Sayısı', compute='_compute_ariza_istatistikleri')
    tamamlanan_ariza_sayisi = fields.Integer(string='Tamamlanan Arıza Sayısı', compute='_compute_ariza_istatistikleri')
    iptal_ariza_sayisi = fields.Integer(string='İptal Edilen Arıza Sayısı', compute='_compute_ariza_istatistikleri')
    toplam_ariza_sayisi = fields.Integer(string='Toplam Arıza Sayısı', compute='_compute_ariza_istatistikleri')

    @api.depends('state')
    def _compute_ariza_istatistikleri(self):
        for record in self:
            record.acik_ariza_sayisi = self.search_count([('state', 'in', ['draft', 'onaylandi'])])
            record.tamamlanan_ariza_sayisi = self.search_count([('state', '=', 'tamamlandi')])
            record.iptal_ariza_sayisi = self.search_count([('state', '=', 'iptal')])
            record.toplam_ariza_sayisi = self.search_count([])

    @api.onchange('ariza_tipi')
    def _onchange_ariza_tipi(self):
        if self.ariza_tipi != 'musteri':
            self.siparis_yok = False
            self.sale_order_id = False
            self.pos_order_id = False
            self.fatura_tarihi = False
        if self.ariza_tipi != 'magaza':
            self.magaza_ariza_tipi = False
            self.analitik_hesap_id = False
            self.tedarikci_id = False
            self.transfer_irsaliye = False

    @api.onchange('sale_order_id', 'pos_order_id')
    def _onchange_order(self):
        if self.sale_order_id:
            self.partner_id = self.sale_order_id.partner_id
            self.fatura_tarihi = self.sale_order_id.invoice_ids and self.sale_order_id.invoice_ids[0].invoice_date or False
        elif self.pos_order_id:
            self.partner_id = self.pos_order_id.partner_id
            self.fatura_tarihi = self.pos_order_id.invoice_id and self.pos_order_id.invoice_id.invoice_date or False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ariza.kayit') or _('New')
        return super().create(vals_list)
    
    def action_onayla(self):
        if self.ariza_tipi == 'magaza' and self.magaza_ariza_tipi:
            self._create_stock_transfer()
        self.state = 'onaylandi'
    
    def action_tamamla(self):
        self.state = 'tamamlandi'
    
    def action_iptal(self):
        self.state = 'iptal'
    
    def _create_stock_transfer(self):
        if not self.analitik_hesap_id:
            raise UserError(_('Analitik hesap seçilmesi zorunludur.'))
            
        if self.magaza_ariza_tipi == 'depo':
            self._create_depo_transfer()
        elif self.magaza_ariza_tipi == 'tedarikci':
            self._create_tedarikci_transfer()
        elif self.magaza_ariza_tipi == 'nefesli':
            self._create_nefesli_transfer()
    
    def _create_depo_transfer(self):
        source_location = self.env['stock.location'].search([
            ('name', '=', f"{self.analitik_hesap_id.code}/stok")
        ], limit=1)
        
        dest_location = self.env['stock.location'].search([
            ('name', '=', 'arıza/stok')
        ], limit=1)
        
        if not source_location or not dest_location:
            raise UserError(_('Gerekli stok konumları bulunamadı.'))
            
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '!=', False)
        ], limit=1)
        
        if not picking_type:
            raise UserError(_('İç transfer türü bulunamadı.'))
            
        picking = self.env['stock.picking'].create({
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
            'picking_type_id': picking_type.id,
            'origin': self.name,
            'move_type': 'direct',
            'immediate_transfer': True,
        })
        
        self.transfer_id = picking.id
        
    def _create_tedarikci_transfer(self):
        if not self.tedarikci_id:
            raise UserError(_('Tedarikçi seçilmesi zorunludur.'))
            
        source_location = self.env['stock.location'].search([
            ('name', '=', f"{self.analitik_hesap_id.code}/stok")
        ], limit=1)
        
        dest_location = self.env['stock.location'].search([
            ('name', '=', f"{self.tedarikci_id.name}/stok")
        ], limit=1)
        
        if not source_location or not dest_location:
            raise UserError(_('Gerekli stok konumları bulunamadı.'))
            
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('warehouse_id', '!=', False)
        ], limit=1)
        
        if not picking_type:
            raise UserError(_('Dış transfer türü bulunamadı.'))
            
        picking = self.env['stock.picking'].create({
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
            'picking_type_id': picking_type.id,
            'origin': self.name,
            'move_type': 'direct',
            'immediate_transfer': True,
            'partner_id': self.tedarikci_id.id,
        })
        
        if self.transfer_irsaliye:
            picking.is_irsaliye = True
            
        self.transfer_id = picking.id
        
    def _create_nefesli_transfer(self):
        source_location = self.env['stock.location'].search([
            ('name', '=', f"{self.analitik_hesap_id.code}/stok")
        ], limit=1)
        
        dest_location = self.env['stock.location'].search([
            ('name', '=', 'nfsl/stok')
        ], limit=1)
        
        if not source_location or not dest_location:
            raise UserError(_('Gerekli stok konumları bulunamadı.'))
            
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '!=', False)
        ], limit=1)
        
        if not picking_type:
            raise UserError(_('İç transfer türü bulunamadı.'))
            
        picking = self.env['stock.picking'].create({
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
            'picking_type_id': picking_type.id,
            'origin': self.name,
            'move_type': 'direct',
            'immediate_transfer': True,
        })
        
        self.transfer_id = picking.id 