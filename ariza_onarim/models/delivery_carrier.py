# -*- coding: utf-8 -*-
"""
Delivery Carrier Model - Shipping Method Customizations

This module extends delivery.carrier model to add vehicle assignment
functionality for delivery/shipping operations.

Author: Arıza Onarım Module
License: LGPL-3
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class DeliveryCarrier(models.Model):
    """
    Delivery Carrier Model Extension

    Extends delivery.carrier to add vehicle (driver) assignment capability.
    Vehicles are represented as res.partner records with is_driver=True flag.
    """
    _inherit = 'delivery.carrier'

    vehicle_id = fields.Many2one(
        'res.partner',
        string='Araç No',
        domain="[('is_driver', '=', True)]",
        help="Bu taşıma yöntemi için atanmış araç/sürücü. "
             "Sadece 'Sürücü' olarak işaretlenmiş cari kayıtları seçilebilir."
    )

    @api.constrains('vehicle_id')
    def _check_vehicle_is_driver(self):
        """
        Validate that assigned vehicle is marked as driver.

        Raises:
            ValidationError: If vehicle_id is not a driver partner.
        """
        for carrier in self:
            if carrier.vehicle_id and not carrier.vehicle_id.is_driver:
                raise ValidationError(
                    _("Seçilen cari (%s) sürücü olarak işaretlenmemiş. "
                      "Lütfen sürücü kaydı seçin.") % carrier.vehicle_id.name
                )
