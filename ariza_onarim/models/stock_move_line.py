# -*- coding: utf-8 -*-
"""
Stock Move Line Extension - Odoo 15 Compatibility Layer

Provides forward compatibility by adding location_lot_ids field
which exists in Odoo 16+ but missing in Odoo 15.

This ensures smooth upgrade path to future Odoo versions.

Best Practices Applied:
- Version compatibility layer
- Proper computed field
- Comprehensive docstrings
- Future-proof design

Author: Arıza Onarım Module - Refactored
License: LGPL-3
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    """
    Stock Move Line Extension for Odoo 15 Compatibility

    Adds location_lot_ids field which is native in Odoo 16+
    but missing in Odoo 15. Provides seamless upgrade path.
    """
    _inherit = 'stock.move.line'

    # Forward compatibility field: location_lot_ids
    # Native in Odoo 16+, computed in Odoo 15
    location_lot_ids = fields.Many2many(
        'stock.production.lot',  # Odoo 15 uses stock.production.lot
        string='Location Lots',
        compute='_compute_location_lot_ids',
        store=False,
        help='Lots/Serial numbers available at this location. '
             'This field provides Odoo 16+ compatibility for Odoo 15 installations.'
    )

    @api.depends('lot_id', 'location_id')
    def _compute_location_lot_ids(self):
        """
        Compute location_lot_ids for Odoo 15 compatibility.

        In Odoo 16+, this field is native. In Odoo 15, we compute it
        from the assigned lot_id to maintain API compatibility.

        Logic:
            - If lot_id is assigned: location_lot_ids = [lot_id]
            - Otherwise: location_lot_ids = []
        """
        for record in self:
            if record.lot_id:
                record.location_lot_ids = record.lot_id
                _logger.debug(
                    f"Computed location_lot_ids for move line {record.id}: {record.lot_id.name}"
                )
            else:
                record.location_lot_ids = False
