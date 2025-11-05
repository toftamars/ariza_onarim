# -*- coding: utf-8 -*-
"""
Partner Helper - Partner işlemleri için helper metodlar
"""

import logging
from odoo import models

from ..ariza_constants import (
    TeknikServis,
    PartnerNames,
)

_logger = logging.getLogger(__name__)


class PartnerHelper:
    """Partner işlemleri için helper metodlar"""

    @staticmethod
    def get_dtl_partner(env):
        """
        DTL Elektronik partner'ını bulur.
        
        Args:
            env: Odoo environment
            
        Returns:
            res.partner record veya False
        """
        try:
            dtl_partner = env['res.partner'].search(
                [('name', 'ilike', PartnerNames.DTL_ELEKTRONIK)],
                limit=1
            )
            return dtl_partner if dtl_partner else False
        except Exception as e:
            _logger.warning(f"DTL partner bulunamadı: {str(e)}")
            return False

    @staticmethod
    def get_dtl_okmeydani_partner(env):
        """
        DTL OKMEYDANI partner'ını bulur (DTL partner'ının alt kontağı).
        
        Args:
            env: Odoo environment
            
        Returns:
            res.partner record veya False (fallback: DTL partner)
        """
        dtl_partner = PartnerHelper.get_dtl_partner(env)
        if not dtl_partner:
            return False
        
        try:
            dtl_okmeydani = env['res.partner'].search([
                ('parent_id', '=', dtl_partner.id),
                ('name', 'ilike', TeknikServis.DTL_OKMEYDANI)
            ], limit=1)
            return dtl_okmeydani if dtl_okmeydani else dtl_partner
        except Exception as e:
            _logger.warning(f"DTL OKMEYDANI partner bulunamadı: {str(e)}")
            return dtl_partner

    @staticmethod
    def get_zuhal_partner(env):
        """
        Zuhal Dış Ticaret A.Ş. partner'ını bulur.
        
        Args:
            env: Odoo environment
            
        Returns:
            res.partner record veya False
        """
        try:
            zuhal_partner = env['res.partner'].search(
                [('name', '=', PartnerNames.ZUHAL_DIS_TICARET)],
                limit=1
            )
            return zuhal_partner if zuhal_partner else False
        except Exception as e:
            _logger.warning(f"Zuhal partner bulunamadı: {str(e)}")
            return False

    @staticmethod
    def get_zuhal_ariza_depo_partner(env):
        """
        Zuhal Arıza Depo partner'ını bulur (Zuhal partner'ının alt kontağı).
        
        Args:
            env: Odoo environment
            
        Returns:
            res.partner record veya False (fallback: Zuhal partner)
        """
        zuhal_partner = PartnerHelper.get_zuhal_partner(env)
        if not zuhal_partner:
            return False
        
        try:
            zuhal_ariza = env['res.partner'].search([
                ('parent_id', '=', zuhal_partner.id),
                ('name', 'ilike', 'Arıza Depo')
            ], limit=1)
            return zuhal_ariza if zuhal_ariza else zuhal_partner
        except Exception as e:
            _logger.warning(f"Zuhal Arıza Depo partner bulunamadı: {str(e)}")
            return zuhal_partner

    @staticmethod
    def get_zuhal_nefesli_partner(env):
        """
        Zuhal Nefesli Arıza partner'ını bulur (Zuhal partner'ının alt kontağı).
        
        Args:
            env: Odoo environment
            
        Returns:
            res.partner record veya False (fallback: Zuhal partner)
        """
        zuhal_partner = PartnerHelper.get_zuhal_partner(env)
        if not zuhal_partner:
            return False
        
        try:
            zuhal_nefesli = env['res.partner'].search([
                ('parent_id', '=', zuhal_partner.id),
                ('name', 'ilike', 'Nefesli Arıza')
            ], limit=1)
            return zuhal_nefesli if zuhal_nefesli else zuhal_partner
        except Exception as e:
            _logger.warning(f"Zuhal Nefesli partner bulunamadı: {str(e)}")
            return zuhal_partner

    @staticmethod
    def get_partner_by_teknik_servis(env, teknik_servis):
        """
        Teknik servise göre partner bulur.
        
        Args:
            env: Odoo environment
            teknik_servis: Teknik servis değeri (TeknikServis constant)
            
        Returns:
            res.partner record veya False
        """
        if teknik_servis == TeknikServis.DTL_BEYOGLU:
            return PartnerHelper.get_dtl_partner(env)
        elif teknik_servis == TeknikServis.DTL_OKMEYDANI:
            return PartnerHelper.get_dtl_okmeydani_partner(env)
        elif teknik_servis == TeknikServis.ZUHAL_ARIZA_DEPO:
            return PartnerHelper.get_zuhal_ariza_depo_partner(env)
        elif teknik_servis == TeknikServis.ZUHAL_NEFESLI:
            return PartnerHelper.get_zuhal_nefesli_partner(env)
        else:
            return False

    @staticmethod
    def format_partner_address(partner):
        """
        Partner adresini formatlar.
        
        Args:
            partner: res.partner record
            
        Returns:
            str: Formatlanmış adres
        """
        if not partner:
            return ''
        
        adres_parcalari = []
        if partner.street:
            adres_parcalari.append(partner.street)
        if partner.street2:
            adres_parcalari.append(partner.street2)
        if partner.city:
            adres_parcalari.append(partner.city)
        if partner.state_id:
            adres_parcalari.append(partner.state_id.name)
        if partner.zip:
            adres_parcalari.append(partner.zip)
        if partner.country_id:
            adres_parcalari.append(partner.country_id.name)
        
        return ', '.join(adres_parcalari) if adres_parcalari else ''

