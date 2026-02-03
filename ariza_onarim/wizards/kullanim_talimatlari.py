# -*- coding: utf-8 -*-
"""
Usage Instructions Wizard

Displays usage instructions and help documentation for repair module.
Simple read-only wizard for showing module documentation.

Author: Arıza Onarım Module - Refactored
License: LGPL-3
"""

from odoo import models, fields, api


class KullanimTalimatlari(models.TransientModel):
    """
    Usage Instructions Wizard

    Transient model for displaying module usage instructions
    and help documentation to users.
    """
    _name = 'ariza.kullanim.talimatlari'
    _description = 'Arıza Onarım Modülü Kullanım Talimatları'

    name = fields.Char(
        string='Başlık',
        default='Arıza Onarım Modülü Kullanım Talimatları',
        readonly=True,
        help='Wizard title - displayed in header'
    )
