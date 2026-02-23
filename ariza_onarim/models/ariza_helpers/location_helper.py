# -*- coding: utf-8 -*-
"""
Location Helper - Stock Location Service Layer

This service provides robust stock location lookup with proper error handling,
flexible searching, and database-based configuration.

Best Practices Applied:
- Proper exception handling with UserError
- Flexible location search strategies
- Database configuration instead of file system
- Comprehensive logging
- Single responsibility principle

Author: Arıza Onarım Module - Refactored
License: LGPL-3
"""

import logging
from odoo import models, _
from odoo.exceptions import UserError

from ..ariza_constants import (
    TeknikServis,
    LocationNames,
)

_logger = logging.getLogger(__name__)


class LocationHelper:
    """
    Stock Location Service for Repair Module

    Provides centralized location lookup with multiple search strategies:
    1. Exact name match with company filter
    2. Exact name match without company filter (legacy)
    3. Flexible ilike search for partial matches
    4. Complete name (path) search for nested locations
    """

    @staticmethod
    def _find_location_flexible(env, primary_name, fallback_patterns=None,
                                company_id=None, raise_if_not_found=False):
        """
        Generic location finder with flexible search strategies.

        Args:
            env: Odoo environment
            primary_name (str): Primary location name for exact match
            fallback_patterns (list, optional): List of (field, operator, value)
                                               search patterns for fallback
            company_id (int, optional): Company ID filter
            raise_if_not_found (bool): Raise UserError if location not found

        Returns:
            stock.location: Found location record or False

        Raises:
            UserError: If location not found and raise_if_not_found=True
        """
        if company_id is None:
            company_id = env.company.id

        # Strategy 1: Exact match with company
        location = env['stock.location'].search([
            ('name', '=', primary_name),
            ('company_id', '=', company_id)
        ], limit=1)
        if location:
            _logger.debug(f"Location found (exact+company): {primary_name}")
            return location

        # Strategy 2: Exact match without company (legacy compatibility)
        location = env['stock.location'].search([
            ('name', '=', primary_name)
        ], limit=1)
        if location:
            _logger.debug(f"Location found (exact): {primary_name}")
            return location

        # Strategy 3: Fallback patterns
        if fallback_patterns:
            for pattern in fallback_patterns:
                location = env['stock.location'].search([pattern], limit=1)
                if location:
                    _logger.info(
                        f"Location found using fallback pattern: {primary_name} -> {location.name}"
                    )
                    return location

        # Not found
        error_msg = _(
            "Stok konumu bulunamadı: %s\n\n"
            "Lütfen sistem yöneticinize başvurun ve aşağıdaki konumun "
            "sistemde tanımlı olduğundan emin olun:\n"
            "- Konum Adı: %s\n"
            "- Şirket: %s"
        ) % (primary_name, primary_name, env.company.name)

        _logger.error(f"Location not found: {primary_name}")

        if raise_if_not_found:
            raise UserError(error_msg)

        return False

    @staticmethod
    def get_dtl_stok_location(env, company_id=None, raise_if_not_found=False):
        """
        Get DTL/Stok location.

        Args:
            env: Odoo environment
            company_id (int, optional): Company ID
            raise_if_not_found (bool): Raise error if not found

        Returns:
            stock.location: DTL/Stok location or False

        Raises:
            UserError: If not found and raise_if_not_found=True
        """
        # complete_name fallback: DTL/Stok hiyerarşik olabilir (parent DTL, child Stok → name sadece "Stok")
        fallback_patterns = [
            ('complete_name', 'ilike', 'DTL/Stok'),
        ]
        return LocationHelper._find_location_flexible(
            env,
            LocationNames.DTL_STOK,
            fallback_patterns=fallback_patterns,
            company_id=company_id,
            raise_if_not_found=raise_if_not_found
        )

    @staticmethod
    def get_ariza_stok_location(env, company_id=None, raise_if_not_found=False):
        """
        Get Arıza/Stok location.

        Args:
            env: Odoo environment
            company_id (int, optional): Company ID
            raise_if_not_found (bool): Raise error if not found

        Returns:
            stock.location: Arıza/Stok location or False

        Raises:
            UserError: If not found and raise_if_not_found=True
        """
        fallback_patterns = [
            ('complete_name', 'ilike', LocationNames.ARIZA_STOK),
        ]
        return LocationHelper._find_location_flexible(
            env,
            LocationNames.ARIZA_STOK,
            fallback_patterns=fallback_patterns,
            company_id=company_id,
            raise_if_not_found=raise_if_not_found
        )

    @staticmethod
    def get_nfsl_arizali_location(env, company_id=None, raise_if_not_found=False):
        """
        Get NFSL/Arızalı location.

        Args:
            env: Odoo environment
            company_id (int, optional): Company ID
            raise_if_not_found (bool): Raise error if not found

        Returns:
            stock.location: NFSL/Arızalı location or False

        Raises:
            UserError: If not found and raise_if_not_found=True
        """
        fallback_patterns = [
            ('complete_name', 'ilike', LocationNames.NFSL_ARIZALI),
        ]
        return LocationHelper._find_location_flexible(
            env,
            LocationNames.NFSL_ARIZALI,
            fallback_patterns=fallback_patterns,
            company_id=company_id,
            raise_if_not_found=raise_if_not_found
        )

    @staticmethod
    def get_nfsl_stok_location(env, company_id=None, raise_if_not_found=False):
        """
        Get NFSL/Stok location.

        Args:
            env: Odoo environment
            company_id (int, optional): Company ID
            raise_if_not_found (bool): Raise error if not found

        Returns:
            stock.location: NFSL/Stok location or False

        Raises:
            UserError: If not found and raise_if_not_found=True
        """
        fallback_patterns = [
            ('complete_name', 'ilike', LocationNames.NFSL_STOK),
            ('name', 'ilike', 'NFSL'),
        ]
        return LocationHelper._find_location_flexible(
            env,
            LocationNames.NFSL_STOK,
            fallback_patterns=fallback_patterns,
            company_id=company_id,
            raise_if_not_found=raise_if_not_found
        )

    @staticmethod
    def get_arizali_location(env, konum_kodu, company_id=None, raise_if_not_found=False):
        """
        Get faulty stock location based on location code.

        Constructs location name as: [LOCATION_PREFIX]/arızalı
        Example: "ADANA/Stok" -> "ADANA/arızalı"

        Args:
            env: Odoo environment
            konum_kodu (str): Location code (e.g., "ADANA/Stok")
            company_id (int, optional): Company ID
            raise_if_not_found (bool): Raise error if not found

        Returns:
            stock.location: Faulty location or False

        Raises:
            UserError: If not found and raise_if_not_found=True
        """
        if not konum_kodu:
            if raise_if_not_found:
                raise UserError(_("Konum kodu belirtilmemiş. Arızalı konum belirlenemedi."))
            return False

        try:
            # Extract location prefix (e.g., "ADANA/Stok" -> "ADANA")
            location_prefix = konum_kodu.split('/')[0]
            arizali_name = f"{location_prefix}/arızalı"

            fallback_patterns = [
                ('complete_name', 'ilike', arizali_name),
                ('name', '=', 'arızalı'),  # Generic faulty location
            ]

            return LocationHelper._find_location_flexible(
                env,
                arizali_name,
                fallback_patterns=fallback_patterns,
                company_id=company_id,
                raise_if_not_found=raise_if_not_found
            )
        except Exception as e:
            _logger.error(f"Error getting faulty location for code {konum_kodu}: {str(e)}")
            if raise_if_not_found:
                raise UserError(
                    _("Arızalı konum bulunamadı: %s\nHata: %s") % (konum_kodu, str(e))
                )
            return False

    @staticmethod
    def get_ngaudio_location(env, company_id=None, raise_if_not_found=False):
        """Get ARIZA/NGaudio location."""
        fallback_patterns = [
            ('complete_name', 'ilike', 'ARIZA/NGaudio'),
            ('name', 'ilike', 'NGaudio'),
        ]
        return LocationHelper._find_location_flexible(
            env,
            'NGaudio',
            fallback_patterns=fallback_patterns,
            company_id=company_id,
            raise_if_not_found=raise_if_not_found
        )

    @staticmethod
    def get_matt_guitar_location(env, company_id=None, raise_if_not_found=False):
        """Get ARIZA/MATT location."""
        fallback_patterns = [
            ('complete_name', 'ilike', 'ARIZA/MATT'),
            ('name', 'ilike', 'MATT'),
        ]
        return LocationHelper._find_location_flexible(
            env,
            'MATT',
            fallback_patterns=fallback_patterns,
            company_id=company_id,
            raise_if_not_found=raise_if_not_found
        )

    @staticmethod
    def get_prohan_elk_location(env, company_id=None, raise_if_not_found=False):
        """Get ANTL/Antalya Teknik Servis location."""
        fallback_patterns = [
            ('complete_name', 'ilike', 'ANTL/Antalya Teknik Servis'),
        ]
        return LocationHelper._find_location_flexible(
            env,
            'Antalya Teknik Servis',
            fallback_patterns=fallback_patterns,
            company_id=company_id,
            raise_if_not_found=raise_if_not_found
        )

    @staticmethod
    def get_erk_enstruman_location(env, company_id=None, raise_if_not_found=False):
        """Get ANKDEPO/Ankara Teknik Servis location."""
        fallback_patterns = [
            ('complete_name', 'ilike', 'ANKDEPO/Ankara Teknik Servis'),
            ('name', 'ilike', 'Ankara Teknik Servis'),
        ]
        return LocationHelper._find_location_flexible(
            env,
            'Ankara Teknik Servis',
            fallback_patterns=fallback_patterns,
            company_id=company_id,
            raise_if_not_found=raise_if_not_found
        )

    @staticmethod
    def get_location_by_name(env, location_name, company_id=None, raise_if_not_found=False):
        """
        Get location by exact name.

        Args:
            env: Odoo environment
            location_name (str): Location name
            company_id (int, optional): Company ID
            raise_if_not_found (bool): Raise error if not found

        Returns:
            stock.location: Found location or False

        Raises:
            UserError: If not found and raise_if_not_found=True
        """
        if not location_name:
            if raise_if_not_found:
                raise UserError(_("Konum adı belirtilmemiş."))
            return False

        fallback_patterns = [
            ('complete_name', 'ilike', location_name),
        ]
        return LocationHelper._find_location_flexible(
            env,
            location_name,
            fallback_patterns=fallback_patterns,
            company_id=company_id,
            raise_if_not_found=raise_if_not_found
        )

    @staticmethod
    def get_konum_kodu_from_analytic(env, analitik_hesap_name):
        """
        Get location code from analytic account via database parameter.

        This replaces file system dependency with database configuration.
        Uses ir.config_parameter for location code mapping.

        Args:
            env: Odoo environment
            analitik_hesap_name (str): Analytic account name

        Returns:
            str: Location code or False

        Configuration:
        Create ir.config_parameter records with key pattern:
        ariza_onarim.location_code.[analytic_name_lowercase]

        Example:
            Key: ariza_onarim.location_code.adana
            Value: ADANA/Stok
        """
        if not analitik_hesap_name:
            return False

        try:
            # Normalize analytic account name for parameter key
            normalized_name = analitik_hesap_name.lower().strip().replace(' ', '_')
            param_key = f'ariza_onarim.location_code.{normalized_name}'

            # Try to get from system parameters
            config_param = env['ir.config_parameter'].sudo()
            konum_kodu = config_param.get_param(param_key, default=False)

            if konum_kodu:
                _logger.debug(
                    f"Location code found for {analitik_hesap_name}: {konum_kodu}"
                )
                return konum_kodu

            # Fallback: Try to get from analytic account's konum_kodu field directly
            analytic = env['account.analytic.account'].search([
                ('name', '=', analitik_hesap_name)
            ], limit=1)

            if analytic and analytic.konum_kodu:
                _logger.debug(
                    f"Location code found from analytic account: {analytic.konum_kodu}"
                )
                return analytic.konum_kodu

            _logger.warning(
                f"Location code not found for analytic account: {analitik_hesap_name}. "
                f"Please configure ir.config_parameter: {param_key}"
            )
            return False

        except Exception as e:
            _logger.error(
                f"Error getting location code for {analitik_hesap_name}: {str(e)}"
            )
            return False

    @staticmethod
    def validate_critical_locations(env, location_names=None):
        """
        Validate that critical locations exist in the system.

        Useful for module installation checks and preventive validation.

        Args:
            env: Odoo environment
            location_names (list, optional): List of location names to check.
                                            If None, checks all critical locations.

        Returns:
            tuple: (bool success, list of missing locations)

        Example:
            success, missing = LocationHelper.validate_critical_locations(env)
            if not success:
                raise UserError(f"Missing locations: {', '.join(missing)}")
        """
        if location_names is None:
            location_names = [
                LocationNames.DTL_STOK,
                LocationNames.ARIZA_STOK,
                LocationNames.NFSL_ARIZALI,
                LocationNames.NFSL_STOK,
            ]

        missing_locations = []
        for loc_name in location_names:
            location = env['stock.location'].search([('name', '=', loc_name)], limit=1)
            if not location:
                missing_locations.append(loc_name)
                _logger.warning(f"Critical location missing: {loc_name}")

        if missing_locations:
            _logger.error(
                f"Location validation failed. Missing locations: {missing_locations}"
            )
            return False, missing_locations

        _logger.info("All critical locations validated successfully")
        return True, []
