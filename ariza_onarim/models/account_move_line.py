# -*- coding: utf-8 -*-
"""
Account Move Line Extension - Invoice Line Display Customization

Extends account.move.line model to customize display format
for invoice line selection in repair module.

Best Practices Applied:
- Clean name_get override
- Proper fallback logic
- Comprehensive docstrings

Author: Arıza Onarım Module - Refactored
License: LGPL-3
"""

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    """
    Invoice Line Extension for Repair Module

    Customizes name_get to show clean product names in dropdowns
    for better user experience in repair record forms.
    """
    _inherit = 'account.move.line'

    def name_get(self):
        """
        Override name_get to show simplified product name.

        Instead of showing full invoice line description with prices,
        shows only the product name for cleaner dropdown display.

        Returns:
            list: List of (id, name) tuples

        Example:
            Standard: "Product ABC - Invoice INV/2024/001 - $100.00"
            Custom:   "Product ABC"
        """
        result = []
        for record in self:
            if record.product_id:
                # Show only product name for clarity
                name = record.product_id.name
            else:
                # Fallback to standard name_get for non-product lines
                try:
                    parent_result = super(AccountMoveLine, record).name_get()
                    name = parent_result[0][1] if parent_result and record.id else ''
                except Exception as e:
                    _logger.warning(
                        f"Error in name_get fallback for invoice line {record.id}: {e}"
                    )
                    name = record.name or ''

            result.append((record.id, name))

        return result

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        """
        Override name search to include product name in search.

        Allows searching invoice lines by product name directly.

        Args:
            name (str): Search term
            args (list): Additional domain filters
            operator (str): Search operator (default: 'ilike')
            limit (int): Maximum results (default: 100)
            name_get_uid (int, optional): User ID for access rights

        Returns:
            list: List of matching record IDs
        """
        args = args or []
        domain = []

        if name:
            domain = [
                '|', ('name', operator, name),
                '|', ('product_id.name', operator, name),
                ('product_id.default_code', operator, name)
            ]

        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)
