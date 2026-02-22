# -*- coding: utf-8 -*-
"""
Partner Helper - Partner/Contact Service Layer

This service provides centralized partner (contact/customer/vendor) lookup
with proper error handling and flexible search strategies.

Best Practices Applied:
- Proper exception handling
- Flexible partner search with fallbacks
- Address formatting utilities
- Comprehensive logging
- Caching consideration for performance

Author: Arıza Onarım Module - Refactored
License: LGPL-3
"""

import logging
from odoo import _, models
from odoo.exceptions import UserError

from ..ariza_constants import (
    TeknikServis,
    PartnerNames,
)

_logger = logging.getLogger(__name__)


class PartnerHelper:
    """
    Partner Service for Repair Module

    Provides centralized partner lookup for technical service centers,
    vendors, and related contacts with fallback strategies.
    """

    @staticmethod
    def _find_partner_flexible(env, primary_search, fallback_searches=None,
                               raise_if_not_found=False, partner_type='Partner'):
        """
        Generic partner finder with flexible search strategies.

        Args:
            env: Odoo environment
            primary_search (list): Primary search domain
            fallback_searches (list, optional): List of fallback search domains
            raise_if_not_found (bool): Raise UserError if not found
            partner_type (str): Partner type description for error messages

        Returns:
            res.partner: Found partner or False

        Raises:
            UserError: If partner not found and raise_if_not_found=True
        """
        # Primary search
        partner = env['res.partner'].search(primary_search, limit=1)
        if partner:
            _logger.debug(f"{partner_type} found: {partner.name}")
            return partner

        # Fallback searches
        if fallback_searches:
            for search_domain in fallback_searches:
                partner = env['res.partner'].search(search_domain, limit=1)
                if partner:
                    _logger.info(
                        f"{partner_type} found using fallback: {partner.name}"
                    )
                    return partner

        # Not found
        error_msg = _(
            "%s bulunamadı.\n\n"
            "Lütfen sistem yöneticinize başvurun ve cari kaydının "
            "sistemde tanımlı olduğundan emin olun."
        ) % partner_type

        _logger.error(f"{partner_type} not found")

        if raise_if_not_found:
            raise UserError(error_msg)

        return False

    @staticmethod
    def get_dtl_partner(env, raise_if_not_found=False):
        """
        Get DTL Elektronik partner.

        Args:
            env: Odoo environment
            raise_if_not_found (bool): Raise error if not found

        Returns:
            res.partner: DTL partner or False

        Raises:
            UserError: If not found and raise_if_not_found=True
        """
        primary_search = [('name', 'ilike', PartnerNames.DTL_ELEKTRONIK)]
        fallback_searches = [
            [('name', 'ilike', 'DTL')],
        ]
        return PartnerHelper._find_partner_flexible(
            env,
            primary_search,
            fallback_searches=fallback_searches,
            raise_if_not_found=raise_if_not_found,
            partner_type='DTL Elektronik'
        )

    @staticmethod
    def get_dtl_okmeydani_partner(env, raise_if_not_found=False):
        """
        Get DTL OKMEYDANI partner (child contact of DTL).

        Falls back to main DTL partner if child contact not found.

        Args:
            env: Odoo environment
            raise_if_not_found (bool): Raise error if DTL parent not found

        Returns:
            res.partner: DTL OKMEYDANI or DTL parent or False
        """
        dtl_partner = PartnerHelper.get_dtl_partner(env, raise_if_not_found)
        if not dtl_partner:
            return False

        # Search for child contact
        dtl_okmeydani = env['res.partner'].search([
            ('parent_id', '=', dtl_partner.id),
            ('name', 'ilike', TeknikServis.DTL_OKMEYDANI)
        ], limit=1)

        if dtl_okmeydani:
            _logger.debug(f"DTL OKMEYDANI child contact found: {dtl_okmeydani.name}")
            return dtl_okmeydani
        else:
            _logger.info("DTL OKMEYDANI not found, falling back to parent DTL")
            return dtl_partner

    @staticmethod
    def get_zuhal_partner(env, raise_if_not_found=False):
        """
        Get Zuhal Dış Ticaret A.Ş. partner.

        Args:
            env: Odoo environment
            raise_if_not_found (bool): Raise error if not found

        Returns:
            res.partner: Zuhal partner or False

        Raises:
            UserError: If not found and raise_if_not_found=True
        """
        primary_search = [('name', '=', PartnerNames.ZUHAL_DIS_TICARET)]
        fallback_searches = [
            [('name', 'ilike', 'Zuhal')],
        ]
        return PartnerHelper._find_partner_flexible(
            env,
            primary_search,
            fallback_searches=fallback_searches,
            raise_if_not_found=raise_if_not_found,
            partner_type='Zuhal Dış Ticaret'
        )

    @staticmethod
    def get_zuhal_ariza_depo_partner(env, raise_if_not_found=False):
        """
        Get Zuhal Arıza Depo partner (child contact of Zuhal).

        Falls back to main Zuhal partner if child contact not found.

        Args:
            env: Odoo environment
            raise_if_not_found (bool): Raise error if Zuhal parent not found

        Returns:
            res.partner: Zuhal Arıza Depo or Zuhal parent or False
        """
        zuhal_partner = PartnerHelper.get_zuhal_partner(env, raise_if_not_found)
        if not zuhal_partner:
            return False

        zuhal_ariza = env['res.partner'].search([
            ('parent_id', '=', zuhal_partner.id),
            ('name', 'ilike', 'Arıza Depo')
        ], limit=1)

        if zuhal_ariza:
            _logger.debug(f"Zuhal Arıza Depo found: {zuhal_ariza.name}")
            return zuhal_ariza
        else:
            _logger.info("Zuhal Arıza Depo not found, falling back to parent Zuhal")
            return zuhal_partner

    @staticmethod
    def get_zuhal_nefesli_partner(env, raise_if_not_found=False):
        """
        Get Zuhal Nefesli Arıza partner (child contact of Zuhal).

        Falls back to main Zuhal partner if child contact not found.

        Args:
            env: Odoo environment
            raise_if_not_found (bool): Raise error if Zuhal parent not found

        Returns:
            res.partner: Zuhal Nefesli or Zuhal parent or False
        """
        zuhal_partner = PartnerHelper.get_zuhal_partner(env, raise_if_not_found)
        if not zuhal_partner:
            return False

        zuhal_nefesli = env['res.partner'].search([
            ('parent_id', '=', zuhal_partner.id),
            ('name', 'ilike', 'Nefesli Arıza')
        ], limit=1)

        if zuhal_nefesli:
            _logger.debug(f"Zuhal Nefesli found: {zuhal_nefesli.name}")
            return zuhal_nefesli
        else:
            _logger.info("Zuhal Nefesli not found, falling back to parent Zuhal")
            return zuhal_partner

    @staticmethod
    def get_partner_by_teknik_servis(env, teknik_servis, raise_if_not_found=False):
        """
        Get partner by technical service type.

        Maps technical service selection to corresponding partner record.

        Args:
            env: Odoo environment
            teknik_servis (str): Technical service constant from TeknikServis
            raise_if_not_found (bool): Raise error if not found

        Returns:
            res.partner: Matched partner or False

        Raises:
            UserError: If not found and raise_if_not_found=True
        """
        partner_map = {
            TeknikServis.DTL_BEYOGLU: PartnerHelper.get_dtl_partner,
            TeknikServis.DTL_OKMEYDANI: PartnerHelper.get_dtl_okmeydani_partner,
            TeknikServis.ZUHAL_ARIZA_DEPO: PartnerHelper.get_zuhal_ariza_depo_partner,
            TeknikServis.ZUHAL_NEFESLI: PartnerHelper.get_zuhal_nefesli_partner,
        }

        if teknik_servis in partner_map:
            return partner_map[teknik_servis](env, raise_if_not_found)

        if raise_if_not_found:
            raise UserError(
                _("Teknik servis için partner bulunamadı: %s") % teknik_servis
            )

        return False

    @staticmethod
    def format_partner_address(partner):
        """
        Format partner address for display.

        Combines street, city, state, zip, and country into a readable format.

        Args:
            partner (res.partner): Partner record

        Returns:
            str: Formatted address string (comma-separated)

        Example:
            "Atatürk Cad. No:123, Kadıköy, Istanbul 34710, Turkey"
        """
        if not partner:
            return ''

        address_parts = []

        if partner.street:
            address_parts.append(partner.street)
        if partner.street2:
            address_parts.append(partner.street2)
        if partner.city:
            address_parts.append(partner.city)
        if partner.state_id:
            address_parts.append(partner.state_id.name)
        if partner.zip:
            address_parts.append(partner.zip)
        if partner.country_id:
            address_parts.append(partner.country_id.name)

        return ', '.join(address_parts) if address_parts else ''

    @staticmethod
    def validate_partner_contact_info(partner, require_phone=False, require_email=False):
        """
        Validate that partner has required contact information.

        Args:
            partner (res.partner): Partner record to validate
            require_phone (bool): Whether phone/mobile is required
            require_email (bool): Whether email is required

        Returns:
            tuple: (bool is_valid, str error_message)

        Example:
            is_valid, error = PartnerHelper.validate_partner_contact_info(
                partner, require_phone=True
            )
            if not is_valid:
                raise UserError(error)
        """
        if not partner:
            return False, _("Partner belirtilmemiş.")

        errors = []

        if require_phone and not (partner.phone or partner.mobile):
            errors.append(_("Telefon numarası eksik"))

        if require_email and not partner.email:
            errors.append(_("E-posta adresi eksik"))

        if errors:
            error_msg = _("Partner iletişim bilgileri eksik: %s\nPartner: %s") % (
                ', '.join(errors),
                partner.name
            )
            return False, error_msg

        return True, ''
