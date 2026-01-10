# -*- coding: utf-8 -*-
"""
Stock Picking Model - Transfer görünümü özelleştirmeleri
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Arıza onarım modülünden oluşturulan transferler için
        edespatch_delivery_type alanını otomatik olarak 'printed' (Matbu) yap
        """
        for vals in vals_list:
            # Eğer context'te ariza_onarim işareti varsa veya origin'de ARZ varsa
            origin = str(vals.get('origin', ''))
            if self.env.context.get('from_ariza_onarim') or ('ARZ' in origin.upper()):
                # edespatch_delivery_type alanı varsa ve henüz set edilmemişse
                if 'edespatch_delivery_type' not in vals:
                    vals['edespatch_delivery_type'] = 'printed'
                    _logger.info(f"Matbu ayarı yapıldı - Transfer Origin: {origin}")
        
        return super().create(vals_list)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form' and self.env.context.get('hide_note'):
            try:
                from lxml import etree
                arch = etree.fromstring(res.get('arch', ''))
                for node in arch.xpath("//field[@name='note']"):
                    parent = node.getparent()
                    if parent is not None:
                        parent.remove(node)
                # Chatter'ı da kaldır (mail_init_messaging çağrısını engellemek için)
                for node in arch.xpath("//*[contains(concat(' ', normalize-space(@class), ' '), ' oe_chatter ')]"):
                    parent = node.getparent()
                    if parent is not None:
                        parent.remove(node)
                res['arch'] = etree.tostring(arch, encoding='unicode')
            except Exception as e:
                # lxml yoksa veya hata olursa logla
                _logger.warning(f"View işleme hatası (stock.picking): {str(e)}")
        return res

    def _ubl_add_shipment_stage(self, shipment, ns, version='2.1'):
        """Araç bilgisi kontrolü eklendi"""
        super()._ubl_add_shipment_stage(shipment, ns, version=version)
        
        # Araç bilgisi kontrolü
        if hasattr(self, 'vehicle_id') and self.vehicle_id:
            vehicle = shipment.find(ns['cac'] + 'TransportMeans')
            if vehicle is not None:
                vehicle_id = vehicle.find(ns['cac'] + 'ID')
                if vehicle_id is not None:
                    # vehicle_id string değilse boş string olarak ayarla
                    vehicle_id.text = str(self.vehicle_id) if self.vehicle_id else '' 

 