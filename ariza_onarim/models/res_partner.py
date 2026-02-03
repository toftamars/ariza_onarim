# -*- coding: utf-8 -*-
"""
Res Partner Extension - Driver Management

Extends res.partner model to add driver/vehicle management functionality
for delivery and transfer operations.

Best Practices Applied:
- Proper field constraints
- Validation decorators
- Search optimization with indexes
- Comprehensive docstrings

Author: Arıza Onarım Module - Refactored
License: LGPL-3
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """
    Partner Extension for Driver Management

    Adds driver-specific fields and methods for vehicle tracking
    and driver assignment in repair module transfers.
    """
    _inherit = 'res.partner'

    is_driver = fields.Boolean(
        string='Sürücü mü?',
        default=False,
        index=True,
        help='Bu partner sürücü ise işaretleyin. '
             'Sürücüler transfer ve teslimat işlemlerinde kullanılır.'
    )
    vehicle_plate = fields.Char(
        string='Araç Plakası',
        help='Sürücünün kullandığı aracın plakası (örn: 34 ABC 1234)',
        index=True
    )
    vehicle_type = fields.Selection(
        [
            ('car', 'Otomobil'),
            ('van', 'Minibüs'),
            ('truck', 'Kamyon'),
            ('motorcycle', 'Motosiklet'),
            ('other', 'Diğer')
        ],
        string='Araç Tipi',
        help='Sürücünün kullandığı araç tipi'
    )
    license_number = fields.Char(
        string='Ehliyet Numarası',
        help='Sürücünün ehliyet numarası'
    )
    phone_driver = fields.Char(
        string='Sürücü Telefonu',
        help='Sürücüye ait özel telefon numarası'
    )

    @api.constrains('is_driver', 'vehicle_plate')
    def _check_driver_vehicle_plate(self):
        """
        Validate that driver has vehicle plate.

        Ensures drivers have vehicle plate information when marked as driver.
        """
        for partner in self:
            if partner.is_driver and not partner.vehicle_plate:
                raise ValidationError(
                    _("Sürücü olarak işaretlenen partner için araç plakası zorunludur.\n"
                      "Partner: %s") % partner.name
                )

    @api.constrains('vehicle_plate')
    def _check_vehicle_plate_format(self):
        """
        Basic validation for vehicle plate format.

        Checks that plate is not too short or too long.
        """
        for partner in self:
            if partner.vehicle_plate:
                plate = partner.vehicle_plate.strip()
                if len(plate) < 5:
                    raise ValidationError(
                        _("Araç plakası çok kısa. Minimum 5 karakter olmalı.\n"
                          "Girilen: %s") % partner.vehicle_plate
                    )
                if len(plate) > 20:
                    raise ValidationError(
                        _("Araç plakası çok uzun. Maximum 20 karakter olabilir.\n"
                          "Girilen: %s") % partner.vehicle_plate
                    )

    @api.model
    def get_available_drivers(self, include_inactive=False):
        """
        Get all available drivers.

        Args:
            include_inactive (bool): Include inactive drivers if True

        Returns:
            recordset: Available driver partners

        Example:
            drivers = env['res.partner'].get_available_drivers()
            for driver in drivers:
                print(f"{driver.name}: {driver.vehicle_plate}")
        """
        domain = [('is_driver', '=', True)]
        if not include_inactive:
            domain.append(('active', '=', True))

        drivers = self.search(domain, order='name')
        _logger.debug(f"Found {len(drivers)} available drivers")
        return drivers

    @api.model
    def get_driver_by_plate(self, plate, raise_if_not_found=False):
        """
        Find driver by vehicle plate number.

        Args:
            plate (str): Vehicle plate number (partial match supported)
            raise_if_not_found (bool): Raise error if driver not found

        Returns:
            res.partner: Driver partner or False

        Raises:
            ValidationError: If driver not found and raise_if_not_found=True

        Example:
            driver = env['res.partner'].get_driver_by_plate('34 ABC')
        """
        if not plate:
            if raise_if_not_found:
                raise ValidationError(_("Araç plakası belirtilmemiş."))
            return False

        driver = self.search([
            ('is_driver', '=', True),
            ('vehicle_plate', 'ilike', plate),
            ('active', '=', True)
        ], limit=1)

        if not driver and raise_if_not_found:
            raise ValidationError(
                _("Belirtilen plakaya sahip aktif sürücü bulunamadı: %s") % plate
            )

        if driver:
            _logger.debug(f"Driver found: {driver.name} - {driver.vehicle_plate}")

        return driver

    @api.model
    def get_driver_by_phone(self, phone):
        """
        Find driver by phone number.

        Args:
            phone (str): Phone number (partial match supported)

        Returns:
            res.partner: Driver partner or False
        """
        if not phone:
            return False

        driver = self.search([
            ('is_driver', '=', True),
            '|', ('phone', 'ilike', phone),
            '|', ('mobile', 'ilike', phone),
            ('phone_driver', 'ilike', phone),
            ('active', '=', True)
        ], limit=1)

        return driver

    def name_get(self):
        """
        Override name_get to show vehicle plate for drivers.

        Returns driver name with vehicle plate in format: "Name [PLATE]"
        """
        result = []
        for partner in self:
            if partner.is_driver and partner.vehicle_plate:
                name = f"{partner.name} [{partner.vehicle_plate}]"
            else:
                name = partner.name
            result.append((partner.id, name))
        return result

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        """
        Override name search to include vehicle plate in search.

        Allows searching drivers by vehicle plate number.
        """
        args = args or []
        domain = []

        if name:
            domain = [
                '|', ('name', operator, name),
                ('vehicle_plate', operator, name)
            ]

        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)

    def validate_driver_info(self):
        """
        Validate all required driver information.

        Returns:
            tuple: (bool is_valid, list of error messages)

        Example:
            is_valid, errors = driver.validate_driver_info()
            if not is_valid:
                raise ValidationError('\n'.join(errors))
        """
        self.ensure_one()
        errors = []

        if not self.is_driver:
            errors.append(_("Partner sürücü olarak işaretlenmemiş"))

        if not self.vehicle_plate:
            errors.append(_("Araç plakası eksik"))

        if not self.phone and not self.mobile and not self.phone_driver:
            errors.append(_("Telefon numarası eksik"))

        return len(errors) == 0, errors
