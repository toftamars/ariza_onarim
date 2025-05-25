from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ArizaKayit(models.Model):
    _name = 'ariza.kayit'
    _description = 'Arıza Kayıt'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Arıza No', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    partner_id = fields.Many2one('res.partner', string='Müşteri', required=True, tracking=True)
    tarih = fields.Date(string='İşlem Tarihi', required=True, default=fields.Date.context_today, tracking=True)
    ariza_tipi = fields.Selection([
        ('teknik', 'Teknik Arıza'),
        ('magaza', 'Mağaza Arıza'),
        ('diger', 'Diğer')
    ], string='Arıza Tipi', required=True, tracking=True)
    magaza_ariza_tipi = fields.Selection([
        ('ekran', 'Ekran Arızası'),
        ('klavye', 'Klavye Arızası'),
        ('batarya', 'Batarya Arızası'),
        ('diger', 'Diğer')
    ], string='Mağaza Arıza Tipi', tracking=True)
    garanti_durumu = fields.Selection([
        ('var', 'Garantisi Var'),
        ('yok', 'Garantisi Yok')
    ], string='Garanti Durumu', tracking=True)
    aciklama = fields.Text(string='Açıklama', required=True, tracking=True)
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ariza.kayit') or _('New')
        return super().create(vals_list)
    
    def action_onayla(self):
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
        # Kaynak konum: analitik_hesap/stok
        # Hedef konum: arıza/stok
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