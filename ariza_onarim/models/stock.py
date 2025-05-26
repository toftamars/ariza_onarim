from odoo import models, fields, api

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    ariza_kayit_id = fields.Many2one('ariza.kayit', string='Arıza Kaydı', tracking=True) 