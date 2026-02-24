# -*- coding: utf-8 -*-
"""
Delivery Carrier Model - Shipping Method Customizations

This module extends delivery.carrier model for repair module integration.
Kargo taşıma yöntemi seçimi transfer işlemlerinde kullanılır.

Author: Arıza Onarım Module
License: LGPL-3
"""

from odoo import models


class DeliveryCarrier(models.Model):
    """Delivery Carrier Model Extension"""
    _inherit = 'delivery.carrier'
