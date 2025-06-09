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

    def button_validate(self):
        res = super().button_validate()
        # Origin alanı üzerinden arıza kaydını bul
        for picking in self:
            if picking.origin:
                ariza = self.env['ariza.kayit'].search([('name', '=', picking.origin)], limit=1)
                if ariza:
                    # Arıza kaydını otomatik olarak kilitli duruma getir
                    ariza.action_lock()
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'ariza.kayit',
                        'res_id': ariza.id,
                        'view_mode': 'form',
                        'target': 'current',
                    }
        return res 