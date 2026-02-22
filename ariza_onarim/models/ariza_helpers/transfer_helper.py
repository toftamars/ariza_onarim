# -*- coding: utf-8 -*-
"""
Transfer Helper - Stock Transfer Service Layer

This service provides centralized stock transfer management with
proper error handling, validation, and flexible search strategies.

Best Practices Applied:
- Proper exception handling with UserError
- Flexible search with fallbacks
- Comprehensive logging
- Database configuration
- Caching for performance

Author: Arıza Onarım Module - Refactored
License: LGPL-3
"""

import logging
from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TransferHelper:
    """
    Stock Transfer Service for Repair Module

    Provides centralized transfer-related lookups: delivery carriers,
    picking types, warehouses, and e-dispatch sequences.
    """

    @staticmethod
    def get_delivery_carrier(env, delivery_type='fixed', fixed_price=0.0, raise_if_not_found=False):
        """
        Get delivery carrier by type and price.

        Args:
            env: Odoo environment
            delivery_type (str): Delivery type (default: 'fixed')
            fixed_price (float): Fixed price (default: 0.0 - free shipping)
            raise_if_not_found (bool): Raise error if not found

        Returns:
            delivery.carrier: Delivery carrier record or False

        Raises:
            UserError: If not found and raise_if_not_found=True
        """
        try:
            delivery_carrier = env['delivery.carrier'].sudo().search([
                ('delivery_type', '=', delivery_type),
                ('fixed_price', '=', fixed_price)
            ], limit=1)

            if delivery_carrier:
                _logger.debug(
                    f"Delivery carrier found: {delivery_carrier.name} "
                    f"(type={delivery_type}, price={fixed_price})"
                )
                return delivery_carrier

            error_msg = _(
                "Kargo şirketi bulunamadı.\n"
                "Tip: %s\n"
                "Fiyat: %s\n\n"
                "Lütfen Stok > Ayarlar > Kargo Şirketleri menüsünden "
                "uygun kargo şirketi tanımı yapın."
            ) % (delivery_type, fixed_price)

            _logger.warning(f"Delivery carrier not found: type={delivery_type}, price={fixed_price}")

            if raise_if_not_found:
                raise UserError(error_msg)

            return False

        except Exception as e:
            _logger.error(f"Error getting delivery carrier: {str(e)}")
            if raise_if_not_found:
                raise UserError(
                    _("Kargo şirketi arama sırasında hata oluştu: %s") % str(e)
                )
            return False

    @staticmethod
    def get_picking_type(env, warehouse, picking_type_code, company_id=None, raise_if_not_found=False):
        """
        Get picking type for warehouse and operation type.

        Args:
            env: Odoo environment
            warehouse (stock.warehouse): Warehouse record
            picking_type_code (str): Operation type ('internal', 'outgoing', 'incoming')
            company_id (int, optional): Company ID
            raise_if_not_found (bool): Raise error if not found

        Returns:
            stock.picking.type: Picking type record or False

        Raises:
            UserError: If not found and raise_if_not_found=True
        """
        if not warehouse:
            error_msg = _("Warehouse belirtilmemiş. Picking type belirlenemedi.")
            if raise_if_not_found:
                raise UserError(error_msg)
            return False

        if company_id is None:
            company_id = env.company.id

        try:
            picking_type = env['stock.picking.type'].search([
                ('warehouse_id', '=', warehouse.id),
                ('code', '=', picking_type_code),
                ('company_id', '=', company_id)
            ], limit=1)

            if picking_type:
                _logger.debug(
                    f"Picking type found: {picking_type.name} "
                    f"(warehouse={warehouse.name}, code={picking_type_code})"
                )
                return picking_type

            error_msg = _(
                "Picking type bulunamadı.\n"
                "Warehouse: %s\n"
                "Operasyon Tipi: %s\n"
                "Şirket: %s\n\n"
                "Lütfen warehouse ayarlarını kontrol edin."
            ) % (warehouse.name, picking_type_code, env.company.name)

            _logger.warning(
                f"Picking type not found: warehouse={warehouse.name}, code={picking_type_code}"
            )

            if raise_if_not_found:
                raise UserError(error_msg)

            return False

        except Exception as e:
            _logger.error(
                f"Error getting picking type: {str(e)} - "
                f"warehouse={warehouse.name if warehouse else 'N/A'}, code={picking_type_code}"
            )
            if raise_if_not_found:
                raise UserError(
                    _("Picking type arama sırasında hata oluştu: %s") % str(e)
                )
            return False

    @staticmethod
    def get_warehouse_by_analitik_hesap(env, analitik_hesap_name, raise_if_not_found=False):
        """
        Get warehouse by analytic account name.

        Args:
            env: Odoo environment
            analitik_hesap_name (str): Analytic account name
            raise_if_not_found (bool): Raise error if not found

        Returns:
            stock.warehouse: Warehouse record or False

        Raises:
            UserError: If not found and raise_if_not_found=True
        """
        if not analitik_hesap_name:
            error_msg = _("Analitik hesap adı belirtilmemiş.")
            if raise_if_not_found:
                raise UserError(error_msg)
            return False

        try:
            # Primary search: exact name match
            warehouse = env['stock.warehouse'].search([
                ('name', '=', analitik_hesap_name)
            ], limit=1)

            if warehouse:
                _logger.debug(f"Warehouse found: {warehouse.name}")
                return warehouse

            # Fallback: ilike search
            warehouse = env['stock.warehouse'].search([
                ('name', 'ilike', analitik_hesap_name)
            ], limit=1)

            if warehouse:
                _logger.info(
                    f"Warehouse found using fallback: {warehouse.name} "
                    f"(searched for: {analitik_hesap_name})"
                )
                return warehouse

            error_msg = _(
                "Warehouse bulunamadı.\n"
                "Aranılan: %s\n\n"
                "Lütfen Stok > Ayarlar > Depolar menüsünden "
                "bu analitik hesap için warehouse tanımı yapın."
            ) % analitik_hesap_name

            _logger.warning(f"Warehouse not found: {analitik_hesap_name}")

            if raise_if_not_found:
                raise UserError(error_msg)

            return False

        except Exception as e:
            _logger.error(f"Error getting warehouse: {str(e)} - analytic={analitik_hesap_name}")
            if raise_if_not_found:
                raise UserError(
                    _("Warehouse arama sırasında hata oluştu: %s") % str(e)
                )
            return False

    @staticmethod
    def get_warehouse_by_location_code(env, konum_kodu, raise_if_not_found=False):
        """
        Get warehouse by location code (from analytic account).

        More flexible alternative to get_warehouse_by_analitik_hesap.
        Searches by location code prefix (e.g., "ADANA/Stok" -> "ADANA").

        Args:
            env: Odoo environment
            konum_kodu (str): Location code (e.g., "ADANA/Stok")
            raise_if_not_found (bool): Raise error if not found

        Returns:
            stock.warehouse: Warehouse record or False

        Raises:
            UserError: If not found and raise_if_not_found=True
        """
        if not konum_kodu:
            error_msg = _("Konum kodu belirtilmemiş.")
            if raise_if_not_found:
                raise UserError(error_msg)
            return False

        try:
            # Extract location prefix (e.g., "ADANA/Stok" -> "ADANA")
            location_prefix = konum_kodu.split('/')[0]

            # Search warehouse by name starting with prefix
            warehouse = env['stock.warehouse'].search([
                ('name', 'ilike', location_prefix)
            ], limit=1)

            if warehouse:
                _logger.debug(
                    f"Warehouse found by location code: {warehouse.name} "
                    f"(code={konum_kodu})"
                )
                return warehouse

            error_msg = _(
                "Konum koduna göre warehouse bulunamadı.\n"
                "Konum Kodu: %s\n"
                "Aranan Prefix: %s"
            ) % (konum_kodu, location_prefix)

            _logger.warning(f"Warehouse not found by location code: {konum_kodu}")

            if raise_if_not_found:
                raise UserError(error_msg)

            return False

        except Exception as e:
            _logger.error(f"Error getting warehouse by location code: {str(e)} - code={konum_kodu}")
            if raise_if_not_found:
                raise UserError(
                    _("Warehouse arama sırasında hata oluştu: %s") % str(e)
                )
            return False

    @staticmethod
    def get_edespatch_sequence(env, warehouse, company_id=None, raise_if_not_found=False):
        """
        Get e-Dispatch sequence for warehouse.

        Args:
            env: Odoo environment
            warehouse (stock.warehouse): Warehouse record
            company_id (int, optional): Company ID
            raise_if_not_found (bool): Raise error if not found

        Returns:
            ir.sequence: Sequence record or False

        Raises:
            UserError: If not found and raise_if_not_found=True
        """
        if not warehouse:
            error_msg = _("Warehouse belirtilmemiş. E-İrsaliye sequence belirlenemedi.")
            if raise_if_not_found:
                raise UserError(error_msg)
            return False

        if company_id is None:
            company_id = env.company.id

        try:
            # Construct sequence name (format: "{warehouse_name} - E-İrsaliye")
            warehouse_name = warehouse.name or ''
            sequence_name = f"{warehouse_name} - E-İrsaliye"

            edespatch_sequence = env['ir.sequence'].search([
                ('name', '=', sequence_name),
                ('company_id', '=', company_id)
            ], limit=1)

            if edespatch_sequence:
                _logger.debug(f"E-Dispatch sequence found: {edespatch_sequence.name}")
                return edespatch_sequence

            # Fallback: search by partial name
            edespatch_sequence = env['ir.sequence'].search([
                ('name', 'ilike', f"{warehouse_name}%İrsaliye"),
                ('company_id', '=', company_id)
            ], limit=1)

            if edespatch_sequence:
                _logger.info(
                    f"E-Dispatch sequence found using fallback: {edespatch_sequence.name}"
                )
                return edespatch_sequence

            error_msg = _(
                "E-İrsaliye sequence bulunamadı.\n"
                "Warehouse: %s\n"
                "Aranılan Sequence: %s\n\n"
                "Lütfen Ayarlar > Teknik > Sequence'ler menüsünden "
                "bu warehouse için e-irsaliye sequence tanımı yapın."
            ) % (warehouse.name, sequence_name)

            _logger.warning(
                f"E-Dispatch sequence not found: warehouse={warehouse.name}"
            )

            if raise_if_not_found:
                raise UserError(error_msg)

            return False

        except Exception as e:
            _logger.error(
                f"Error getting e-dispatch sequence: {str(e)} - "
                f"warehouse={warehouse.name if warehouse else 'N/A'}"
            )
            if raise_if_not_found:
                raise UserError(
                    _("E-İrsaliye sequence arama sırasında hata oluştu: %s") % str(e)
                )
            return False

    @staticmethod
    def validate_transfer_data(source_location, dest_location, picking_type, product=None):
        """
        Validate required data for transfer creation.

        Args:
            source_location (stock.location): Source location
            dest_location (stock.location): Destination location
            picking_type (stock.picking.type): Picking type
            product (product.product, optional): Product for transfer

        Returns:
            tuple: (bool is_valid, str error_message)

        Example:
            is_valid, error = TransferHelper.validate_transfer_data(
                source, dest, picking_type
            )
            if not is_valid:
                raise UserError(error)
        """
        errors = []

        if not source_location:
            errors.append(_("Kaynak konum belirtilmemiş"))

        if not dest_location:
            errors.append(_("Hedef konum belirtilmemiş"))

        if not picking_type:
            errors.append(_("Picking type belirtilmemiş"))

        if product and product.type != 'product':
            errors.append(
                _("Seçilen ürün stoğa tabi değil (type=%s)") % product.type
            )

        if errors:
            error_msg = _("Transfer oluşturma için gerekli veriler eksik:\n%s") % '\n'.join(errors)
            return False, error_msg

        return True, ''
