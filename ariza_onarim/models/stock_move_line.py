from odoo import models, fields, api

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    # Odoo 15'te eksik olan alan - Odoo 16'da mevcut
    location_lot_ids = fields.Many2many(
        'stock.lot',
        string='Location Lots',
        compute='_compute_location_lot_ids',
        store=False
    )

    @api.depends('lot_id', 'location_id')
    def _compute_location_lot_ids(self):
        """Odoo 15 uyumluluğu için location_lot_ids alanını hesapla"""
        for record in self:
            if record.lot_id:
                record.location_lot_ids = record.lot_id
            else:
                record.location_lot_ids = False 