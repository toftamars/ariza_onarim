# -*- coding: utf-8 -*-
"""
Transfer Helper - Transfer işlemleri için helper metodlar
"""

import logging
from odoo import models

_logger = logging.getLogger(__name__)


class TransferHelper:
    """Transfer işlemleri için helper metodlar"""

    @staticmethod
    def get_delivery_carrier(env, delivery_type='fixed', fixed_price=0.0):
        """
        Kargo şirketini bulur.
        
        Args:
            env: Odoo environment
            delivery_type: Delivery type (varsayılan: 'fixed')
            fixed_price: Fixed price (varsayılan: 0.0 - ücretsiz kargo)
            
        Returns:
            delivery.carrier record veya False
        """
        try:
            delivery_carrier = env['delivery.carrier'].sudo().search([
                ('delivery_type', '=', delivery_type),
                ('fixed_price', '=', fixed_price)
            ], limit=1)
            return delivery_carrier if delivery_carrier else False
        except Exception as e:
            _logger.warning(f"Kargo şirketi bulunamadı: {str(e)}")
            return False

    @staticmethod
    def get_picking_type(env, warehouse, picking_type_code, company_id=None):
        """
        Picking type bulur.
        
        Args:
            env: Odoo environment
            warehouse: stock.warehouse record
            picking_type_code: Picking type kodu ('internal', 'outgoing', 'incoming')
            company_id: Company ID (opsiyonel, varsayılan: env.company.id)
            
        Returns:
            stock.picking.type record veya False
        """
        if not warehouse:
            return False
        
        if company_id is None:
            company_id = env.company.id
        
        try:
            picking_type = env['stock.picking.type'].search([
                ('warehouse_id', '=', warehouse.id),
                ('code', '=', picking_type_code),
                ('company_id', '=', company_id)
            ], limit=1)
            return picking_type if picking_type else False
        except Exception as e:
            _logger.warning(
                f"Picking type bulunamadı: {str(e)} - "
                f"Warehouse: {warehouse.name if warehouse else 'N/A'}, "
                f"Code: {picking_type_code}"
            )
            return False

    @staticmethod
    def get_warehouse_by_analitik_hesap(env, analitik_hesap_name):
        """
        Analitik hesap adına göre warehouse bulur.
        
        Args:
            env: Odoo environment
            analitik_hesap_name: Analitik hesap adı
            
        Returns:
            stock.warehouse record veya False
        """
        if not analitik_hesap_name:
            return False
        
        try:
            warehouse = env['stock.warehouse'].search([
                ('name', '=', analitik_hesap_name)
            ], limit=1)
            return warehouse if warehouse else False
        except Exception as e:
            _logger.warning(
                f"Warehouse bulunamadı: {str(e)} - "
                f"Analitik Hesap: {analitik_hesap_name}"
            )
            return False

    @staticmethod
    def get_edespatch_sequence(env, warehouse, company_id=None):
        """
        E-İrsaliye sequence'ini bulur.
        
        Args:
            env: Odoo environment
            warehouse: stock.warehouse record
            company_id: Company ID (opsiyonel, varsayılan: env.company.id)
            
        Returns:
            ir.sequence record veya False
        """
        if not warehouse:
            return False
        
        if company_id is None:
            company_id = env.company.id
        
        try:
            # Warehouse'un adına göre sequence bul
            warehouse_name = warehouse.name or ''
            sequence_name = f"{warehouse_name} - E-İrsaliye"
            
            edespatch_sequence = env['ir.sequence'].search([
                ('name', '=', sequence_name),
                ('company_id', '=', company_id)
            ], limit=1)
            
            return edespatch_sequence if edespatch_sequence else False
        except Exception as e:
            _logger.warning(
                f"E-İrsaliye sequence bulunamadı: {str(e)} - "
                f"Warehouse: {warehouse.name if warehouse else 'N/A'}"
            )
            return False

