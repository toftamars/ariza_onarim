# -*- coding: utf-8 -*-
"""
Search Utility Functions - Arama yardımcı fonksiyonları
"""

import logging

_logger = logging.getLogger(__name__)


class SearchUtils:
    """Odoo record arama yardımcı fonksiyonları"""

    @staticmethod
    def find_partner(env, partner_name, exact=False):
        """
        Partner (res.partner) bulur.

        Args:
            env: Odoo environment
            partner_name (str): Partner adı
            exact (bool): Tam eşleşme mi, ilike ile arama mı

        Returns:
            res.partner recordset veya False
        """
        if not partner_name:
            return False

        domain = [('name', '=', partner_name)] if exact else [('name', 'ilike', partner_name)]
        partner = env['res.partner'].search(domain, limit=1)

        if partner:
            _logger.info(f"Partner bulundu: {partner.name} (ID: {partner.id})")
        else:
            _logger.warning(f"Partner bulunamadı: {partner_name}")

        return partner

    @staticmethod
    def find_warehouse(env, warehouse_name):
        """
        Warehouse (stock.warehouse) bulur.

        Args:
            env: Odoo environment
            warehouse_name (str): Warehouse adı (ilike arama yapılır)

        Returns:
            stock.warehouse recordset veya False
        """
        if not warehouse_name:
            return False

        warehouse = env['stock.warehouse'].search([
            ('name', 'ilike', warehouse_name)
        ], limit=1)

        if warehouse:
            _logger.info(f"Warehouse bulundu: {warehouse.name} (ID: {warehouse.id})")
        else:
            _logger.warning(f"Warehouse bulunamadı: {warehouse_name}")

        return warehouse

    @staticmethod
    def find_location(env, location_name, location_type=None):
        """
        Stok konumu (stock.location) bulur.

        Args:
            env: Odoo environment
            location_name (str): Konum adı
            location_type (str): Konum tipi ('internal', 'customer', 'supplier', vb.)

        Returns:
            stock.location recordset veya False
        """
        if not location_name:
            return False

        domain = [('name', 'ilike', location_name)]
        if location_type:
            domain.append(('usage', '=', location_type))

        location = env['stock.location'].search(domain, limit=1)

        if location:
            _logger.info(f"Location bulundu: {location.display_name} (ID: {location.id})")
        else:
            _logger.warning(f"Location bulunamadı: {location_name}")

        return location

    @staticmethod
    def find_product(env, product_name=None, default_code=None):
        """
        Ürün (product.product) bulur.

        Args:
            env: Odoo environment
            product_name (str): Ürün adı
            default_code (str): Ürün kodu (Internal Reference)

        Returns:
            product.product recordset veya False
        """
        if not product_name and not default_code:
            return False

        domain = []
        if default_code:
            domain.append(('default_code', '=', default_code))
        if product_name:
            domain.append(('name', 'ilike', product_name))

        product = env['product.product'].search(domain, limit=1)

        if product:
            _logger.info(f"Ürün bulundu: {product.name} (ID: {product.id})")
        else:
            search_criteria = default_code or product_name
            _logger.warning(f"Ürün bulunamadı: {search_criteria}")

        return product

    @staticmethod
    def find_company(env, company_name):
        """
        Şirket (res.company) bulur.

        Args:
            env: Odoo environment
            company_name (str): Şirket adı

        Returns:
            res.company recordset veya False
        """
        if not company_name:
            return False

        company = env['res.company'].search([
            ('name', 'ilike', company_name)
        ], limit=1)

        if company:
            _logger.info(f"Company bulundu: {company.name} (ID: {company.id})")
        else:
            _logger.warning(f"Company bulunamadı: {company_name}")

        return company

    @staticmethod
    def find_analytic_account(env, account_name):
        """
        Analitik hesap (account.analytic.account) bulur.

        Args:
            env: Odoo environment
            account_name (str): Hesap adı

        Returns:
            account.analytic.account recordset veya False
        """
        if not account_name:
            return False

        account = env['account.analytic.account'].search([
            ('name', 'ilike', account_name)
        ], limit=1)

        if account:
            _logger.info(f"Analytic Account bulundu: {account.name} (ID: {account.id})")
        else:
            _logger.warning(f"Analytic Account bulunamadı: {account_name}")

        return account

    @staticmethod
    def find_partner_child(env, parent_partner, child_name):
        """
        Parent partner'ın child'ını bulur (örn: DTL -> DTL Okmeydanı).

        Args:
            env: Odoo environment
            parent_partner: Parent partner recordset
            child_name (str): Child partner adı

        Returns:
            res.partner recordset veya False
        """
        if not parent_partner or not child_name:
            return False

        child = env['res.partner'].search([
            ('parent_id', '=', parent_partner.id),
            ('name', 'ilike', child_name)
        ], limit=1)

        if child:
            _logger.info(f"Child partner bulundu: {child.name} (Parent: {parent_partner.name})")
        else:
            _logger.warning(f"Child partner bulunamadı: {child_name} (Parent: {parent_partner.name})")

        return child
