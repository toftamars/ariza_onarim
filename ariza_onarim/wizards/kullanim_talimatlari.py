# -*- coding: utf-8 -*-
"""
Kullanım Talimatları Wizard - Kullanım talimatları görüntüleme wizard'ı
"""

from odoo import models, fields, api


class KullanimTalimatlari(models.TransientModel):
    _name = 'ariza.kullanim.talimatlari'
    _description = 'Arıza Onarım Modülü Kullanım Talimatları'

    name = fields.Char(string='Başlık', default='Arıza Onarım Modülü Kullanım Talimatları', readonly=True)

