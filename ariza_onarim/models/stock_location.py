# -*- coding: utf-8 -*-
"""
stock.location genişletmesi - DTL/Stok konumu sadece "DTL/Stok" olarak gösterilir
"""

from odoo import models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    def name_get(self):
        """DTL/Stok konumu için sadece 'DTL/Stok' göster."""
        dtl_stok_id = False
        try:
            ref = self.env.ref('ariza_onarim.stock_location_dtl_stok', raise_if_not_found=False)
            if ref:
                dtl_stok_id = ref.id
        except Exception:
            pass

        result = []
        for loc in self:
            if loc.id == dtl_stok_id:
                result.append((loc.id, 'DTL/Stok'))
            else:
                result.append((loc.id, loc.complete_name or loc.name))
        return result
