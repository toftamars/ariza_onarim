from odoo import models, fields, api, _
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

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

 