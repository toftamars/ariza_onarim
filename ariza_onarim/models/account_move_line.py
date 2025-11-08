# -*- coding: utf-8 -*-
"""
Account Move Line Model - Fatura kalemi görünümü özelleştirmeleri
"""

from odoo import models, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def name_get(self):
        """Fatura kalemi alanında sadece ürün adını göster"""
        result = []
        for record in self:
            if record.product_id:
                # Sadece ürün adını göster
                name = record.product_id.name
            else:
                # Ürün yoksa varsayılan name_get davranışını kullan
                name = super(AccountMoveLine, record).name_get()[0][1] if record.id else ''
            result.append((record.id, name))
        return result 