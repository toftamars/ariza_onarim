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
                # ZORLA Matbu yap (mevcut değeri override et)
                vals['edespatch_delivery_type'] = 'printed'
                _logger.info(f"[CREATE] Matbu ayarı yapıldı - Transfer Origin: {origin}")
        
        records = super().create(vals_list)
        
        # Create sonrası da kontrol et ve gerekirse tekrar set et
        for record in records:
            if record.origin and 'ARZ' in record.origin.upper():
                if record.edespatch_delivery_type != 'printed':
                    _logger.warning(f"[CREATE SONRASI] edespatch_delivery_type değişmiş! Origin: {record.origin}, Mevcut: {record.edespatch_delivery_type}, Düzeltiliyor...")
                    record.write({'edespatch_delivery_type': 'printed'})
                    _logger.info(f"[CREATE SONRASI] Matbu olarak düzeltildi: {record.name}")
                    # Chatter'a da mesaj ekle
                    try:
                        record.message_post(
                            body=f"✅ Teslimat Türü otomatik olarak 'Matbu' yapıldı (Arıza Modülü)",
                            message_type='notification'
                        )
                    except:
                        pass
                else:
                    # Başarılı - Chatter'a bilgi ekle
                    try:
                        record.message_post(
                            body=f"✅ Teslimat Türü: Matbu (Arıza Modülü - Otomatik)",
                            message_type='notification'
                        )
                    except:
                        pass
        
        return records
    
    def write(self, vals):
        """
        Arıza onarım modülünden gelen transferlerde edespatch_delivery_type değiştirilmesin
        """
        result = super().write(vals)
        
        # Write sonrası kontrol - ARZ ile başlayan origin'ler için
        for record in self:
            if record.origin and 'ARZ' in record.origin.upper():
                if record.edespatch_delivery_type != 'printed':
                    _logger.warning(f"[WRITE SONRASI] edespatch_delivery_type değiştirilmiş! Origin: {record.origin}, Mevcut: {record.edespatch_delivery_type}, Geri alınıyor...")
                    super(StockPicking, record).write({'edespatch_delivery_type': 'printed'})
                    _logger.info(f"[WRITE SONRASI] Matbu olarak geri alındı: {record.name}")
        
        return result

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

 