from odoo import models, fields, api, _
from odoo.exceptions import UserError
import qrcode
import base64
from io import BytesIO

class ArizaKayit(models.Model):
    _name = 'ariza.kayit'
    _description = 'Arıza Kayıt'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Arıza Numarası', required=True, copy=False, 
                      readonly=True, default=lambda self: _('New'))
    state = fields.Selection([
        ('draft', 'Taslak'),
        ('onaylandi', 'Onaylandı'),
        ('tamamlandi', 'Tamamlandı'),
        ('iptal', 'İptal')
    ], string='Durum', default='draft', tracking=True)
    
    # QR Kod Alanı
    qr_code = fields.Binary(string='QR Kod', compute='_generate_qr_code', store=True)
    qr_code_url = fields.Char(string='QR Kod URL', compute='_compute_qr_code_url')
    
    # Temel Bilgiler
    ariza_tipi = fields.Selection([
        ('musteri', 'Müşteri Ürünü'),
        ('magaza', 'Mağaza Ürünü'),
        ('teknik_servis', 'Teknik Servis')
    ], string='Arıza Tipi', required=True)
    
    # Müşteri Ürünü Alanları
    partner_id = fields.Many2one('res.partner', string='Müşteri', required=True)
    sale_order_id = fields.Many2one('sale.order', string='Sipariş')
    siparis_yok = fields.Boolean(string='Sipariş Yok')
    urun = fields.Char(string='Ürün')
    marka = fields.Char(string='Marka')
    model = fields.Char(string='Model')
    fatura_tarihi = fields.Date(string='Fatura Tarihi')
    garanti_durumu = fields.Selection([
        ('garanti_kapsaminda', 'Garanti Kapsamında'),
        ('garanti_disinda', 'Garanti Dışında')
    ], string='Garanti Durumu')
    notlar = fields.Text(string='Notlar')
    sorumlu_id = fields.Many2one('res.users', string='Sorumlu', required=True)
    tarih = fields.Date(string='Tarih', required=True, default=fields.Date.context_today)
    
    # Mağaza Ürünü Alanları
    magaza_ariza_tipi = fields.Selection([
        ('depo', 'Depo Arıza'),
        ('tedarikci', 'Tedarikçiler'),
        ('nefesli', 'Nefesli Arıza')
    ], string='Mağaza Arıza Tipi')
    analitik_hesap_id = fields.Many2one('account.analytic.account', string='Analitik Hesap')
    tedarikci_id = fields.Many2one('res.partner', string='Tedarikçi', 
                                  domain="[('supplier_rank', '>', 0)]")
    transfer_irsaliye = fields.Boolean(string='E-İrsaliye Oluştur')
    
    # Arıza Detayları
    ariza_tanimi = fields.Text(string='Arıza ve Onarım Tanımı', required=True)
    
    # Stok Transfer Bilgileri
    transfer_id = fields.Many2one('stock.picking', string='Transfer Belgesi', readonly=True)

    @api.depends('name')
    def _generate_qr_code(self):
        for record in self:
            if record.name:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(record.name)
                qr.make(fit=True)
                img = qr.make_image()
                temp = BytesIO()
                img.save(temp, format="PNG")
                qr_image = base64.b64encode(temp.getvalue())
                record.qr_code = qr_image
            else:
                record.qr_code = False

    @api.depends('name')
    def _compute_qr_code_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            if record.name:
                record.qr_code_url = f"{base_url}/ariza/{record.name}"
            else:
                record.qr_code_url = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ariza.kayit') or _('New')
        return super().create(vals_list)
    
    def action_onayla(self):
        self.state = 'onaylandi'
        if self.ariza_tipi == 'magaza':
            self._create_stock_transfer()
    
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