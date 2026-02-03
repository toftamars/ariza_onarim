# -*- coding: utf-8 -*-
"""
Account Analytic Account Extension

Extends analytic account model to add:
- Partner relationship
- Contact information (address, phone, email)
- Warehouse integration
- Location code auto-computation
- Zuhal addresses setup utility

Author: Arıza Onarım Module - Refactored
License: LGPL-3
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

from .ariza_constants import PartnerNames

_logger = logging.getLogger(__name__)


class AccountAnalyticAccount(models.Model):
    """
    Analytic Account Extension for Repair Module

    Adds store/branch management functionality to analytic accounts,
    integrating with warehouse and location systems.
    """
    _inherit = 'account.analytic.account'

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        help='Partner associated with this analytic account (store/branch)'
    )
    adres = fields.Text(
        string='Adres',
        help='Full address of the store/branch'
    )
    telefon = fields.Char(
        string='Telefon',
        help='Phone number for this location'
    )
    email = fields.Char(
        string='E-posta',
        help='Email address for this location'
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        help='Warehouse associated with this store/branch'
    )
    konum_kodu = fields.Char(
        string='Konum Kodu',
        compute='_compute_konum_kodu',
        store=True,
        help='Stock location code (e.g., ADANA/Stok, UNIQ/Stok). '
             'Used to determine source and faulty locations. '
             'Auto-computed from warehouse.'
    )

    @api.depends('warehouse_id', 'warehouse_id.lot_stock_id')
    def _compute_konum_kodu(self):
        """
        Auto-compute location code from warehouse.

        Extracts the location name from warehouse's main stock location.
        Example: If warehouse.lot_stock_id.name = "ADANA/Stok"
                Then konum_kodu = "ADANA/Stok"
        """
        for record in self:
            if record.warehouse_id and record.warehouse_id.lot_stock_id:
                record.konum_kodu = record.warehouse_id.lot_stock_id.name
                _logger.debug(
                    f"Location code computed for {record.name}: {record.konum_kodu}"
                )
            else:
                record.konum_kodu = False

    @api.model
    def _setup_zuhal_addresses(self):
        """
        Setup analytic accounts for Zuhal Dış Ticaret delivery addresses.

        Creates or updates analytic accounts for each delivery address
        of Zuhal Dış Ticaret partner. Useful for initial setup or data sync.

        Returns:
            int: Number of analytic accounts created/updated
        """
        # Find Zuhal partner
        zuhal_partner = self.env['res.partner'].search(
            [('name', '=', PartnerNames.ZUHAL_DIS_TICARET)],
            limit=1
        )
        if not zuhal_partner:
            _logger.warning(
                f"Zuhal partner not found: {PartnerNames.ZUHAL_DIS_TICARET}"
            )
            return 0

        # Get Zuhal delivery addresses
        zuhal_addresses = self.env['res.partner'].search([
            ('parent_id', '=', zuhal_partner.id),
            ('type', '=', 'delivery')
        ])

        created = 0
        updated = 0

        for address in zuhal_addresses:
            # Check if analytic account exists
            existing_analytic = self.search([
                ('partner_id', '=', address.id)
            ], limit=1)

            address_data = {
                'adres': self._format_address(address),
                'telefon': address.phone or address.mobile,
                'email': address.email,
            }

            if not existing_analytic:
                # Create new analytic account
                self.create({
                    'name': f"{address.name} - {address.street or ''}",
                    'partner_id': address.id,
                    **address_data
                })
                created += 1
                _logger.info(f"Created analytic account for: {address.name}")
            else:
                # Update existing analytic account
                existing_analytic.write(address_data)
                updated += 1
                _logger.debug(f"Updated analytic account for: {address.name}")

        _logger.info(
            f"Zuhal addresses setup completed: {created} created, {updated} updated"
        )
        return created + updated

    def _format_address(self, partner):
        """
        Format partner address as comma-separated string.

        Args:
            partner (res.partner): Partner record with address fields

        Returns:
            str: Formatted address (comma-separated)

        Example:
            "Atatürk Cad. No:123, Kadıköy, Istanbul 34710, Turkey"
        """
        address_parts = []

        if partner.street:
            address_parts.append(partner.street)
        if partner.street2:
            address_parts.append(partner.street2)
        if partner.city:
            address_parts.append(partner.city)
        if partner.state_id:
            address_parts.append(partner.state_id.name)
        if partner.zip:
            address_parts.append(partner.zip)
        if partner.country_id:
            address_parts.append(partner.country_id.name)

        return ', '.join(address_parts) if address_parts else ''

    @api.constrains('warehouse_id', 'konum_kodu')
    def _check_warehouse_location_consistency(self):
        """
        Validate warehouse and location code consistency.

        Ensures that if warehouse is set, location code is properly computed.
        """
        for record in self:
            if record.warehouse_id and not record.konum_kodu:
                raise UserError(
                    _("Warehouse is set but location code could not be computed. "
                      "Please ensure the warehouse has a valid stock location.\n"
                      "Analytic Account: %s\n"
                      "Warehouse: %s") % (record.name, record.warehouse_id.name)
                )
