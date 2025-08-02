from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    is_driver = fields.Boolean(string='Sürücü mü?', default=False, help='Bu partner sürücü ise işaretleyin')
    vehicle_plate = fields.Char(string='Araç Plakası', help='Sürücünün kullandığı aracın plakası')
    vehicle_type = fields.Selection([
        ('car', 'Otomobil'),
        ('van', 'Minibüs'),
        ('truck', 'Kamyon'),
        ('motorcycle', 'Motosiklet'),
        ('other', 'Diğer')
    ], string='Araç Tipi')
    license_number = fields.Char(string='Ehliyet Numarası')
    phone_driver = fields.Char(string='Sürücü Telefonu')
    
    @api.model
    def get_available_drivers(self):
        """Mevcut sürücüleri döndürür"""
        return self.search([('is_driver', '=', True), ('active', '=', True)])
    
    @api.model
    def get_driver_by_plate(self, plate):
        """Plakaya göre sürücü bulur"""
        return self.search([
            ('is_driver', '=', True),
            ('vehicle_plate', 'ilike', plate),
            ('active', '=', True)
        ], limit=1) 