# -*- coding: utf-8 -*-
"""
Location Helper - Konum işlemleri için helper metodlar
"""

import logging
from odoo import models, _
from odoo.exceptions import UserError

from ..ariza_constants import (
    TeknikServis,
    LocationNames,
    MagicNumbers,
)

_logger = logging.getLogger(__name__)


class LocationHelper:
    """Konum işlemleri için helper metodlar"""

    @staticmethod
    def get_dtl_stok_location(env, company_id=None):
        """
        DTL/Stok konumunu bulur.
        
        Args:
            env: Odoo environment
            company_id: Company ID (opsiyonel, varsayılan: env.company.id)
            
        Returns:
            stock.location record veya False
        """
        if company_id is None:
            company_id = env.company.id
        
        try:
            # Önce şirket filtreli ara
            dtl_konum = env['stock.location'].search([
                ('name', '=', LocationNames.DTL_STOK),
                ('company_id', '=', company_id)
            ], limit=1)
            if dtl_konum:
                return dtl_konum

            # Bulunamazsa şirket filtresi olmadan dene (eski kayıtlar için)
            dtl_konum = env['stock.location'].search([
                ('name', '=', LocationNames.DTL_STOK),
            ], limit=1)
            if dtl_konum:
                return dtl_konum

            # Son çare: isimde DTL ve Stok geçen konumu yakala (manuel elle girilmiş)
            dtl_konum = env['stock.location'].search([
                ('name', 'ilike', 'DTL'),
                ('name', 'ilike', 'Stok'),
            ], limit=1)
            return dtl_konum if dtl_konum else False
        except Exception as e:
            _logger.warning(f"DTL/Stok konumu bulunamadı: {str(e)}")
            return False

    @staticmethod
    def get_ariza_stok_location(env, company_id=None):
        """
        Arıza/Stok konumunu bulur.
        
        Args:
            env: Odoo environment
            company_id: Company ID (opsiyonel, varsayılan: env.company.id)
            
        Returns:
            stock.location record veya False
        """
        if company_id is None:
            company_id = env.company.id
        
        try:
            ariza_konum = env['stock.location'].search([
                ('name', '=', LocationNames.ARIZA_STOK),
                ('company_id', '=', company_id)
            ], limit=1)
            return ariza_konum if ariza_konum else False
        except Exception as e:
            _logger.warning(f"Arıza/Stok konumu bulunamadı: {str(e)}")
            return False

    @staticmethod
    def get_nfsl_arizali_location(env, company_id=None):
        """
        NFSL/Arızalı konumunu bulur.
        
        Args:
            env: Odoo environment
            company_id: Company ID (opsiyonel, varsayılan: env.company.id)
            
        Returns:
            stock.location record veya False
        """
        if company_id is None:
            company_id = env.company.id
        
        try:
            nfsl_konum = env['stock.location'].search([
                ('name', '=', LocationNames.NFSL_ARIZALI),
                ('company_id', '=', company_id)
            ], limit=1)
            return nfsl_konum if nfsl_konum else False
        except Exception as e:
            _logger.warning(f"NFSL/Arızalı konumu bulunamadı: {str(e)}")
            return False

    @staticmethod
    def get_arizali_location(env, konum_kodu, company_id=None):
        """
        Arızalı konumunu bulur ([KOD]/arızalı formatında).
        
        Args:
            env: Odoo environment
            konum_kodu: Konum kodu (örn: "ADANA/Stok")
            company_id: Company ID (opsiyonel, varsayılan: env.company.id)
            
        Returns:
            stock.location record veya False
        """
        if not konum_kodu:
            return False
        
        if company_id is None:
            company_id = env.company.id
        
        try:
            konum_adi = f"{konum_kodu.split('/')[0]}/arızalı"
            arizali_konum = env['stock.location'].search([
                ('name', '=', konum_adi),
                ('company_id', '=', company_id)
            ], limit=1)
            return arizali_konum if arizali_konum else False
        except Exception as e:
            _logger.warning(f"Arızalı konumu bulunamadı: {str(e)} - Konum Kodu: {konum_kodu}")
            return False

    @staticmethod
    def get_location_by_name(env, location_name, company_id=None):
        """
        İsme göre konum bulur.
        
        Args:
            env: Odoo environment
            location_name: Konum adı
            company_id: Company ID (opsiyonel, varsayılan: env.company.id)
            
        Returns:
            stock.location record veya False
        """
        if not location_name:
            return False
        
        if company_id is None:
            company_id = env.company.id
        
        try:
            konum = env['stock.location'].search([
                ('name', '=', location_name),
                ('company_id', '=', company_id)
            ], limit=1)
            return konum if konum else False
        except Exception as e:
            _logger.warning(f"Konum bulunamadı: {str(e)} - Konum Adı: {location_name}")
            return False

    @staticmethod
    def parse_konum_kodu_from_file(env, analitik_hesap_name, dosya_yolu):
        """
        Analitik bilgileri dosyasından konum kodu parse eder.
        
        Args:
            env: Odoo environment
            analitik_hesap_name: Analitik hesap adı
            dosya_yolu: Dosya yolu
            
        Returns:
            str: Konum kodu veya False
        """
        if not analitik_hesap_name or not dosya_yolu:
            return False
        
        konum_kodu = False
        try:
            import os
            if os.path.exists(dosya_yolu):
                with open(dosya_yolu, 'r', encoding='utf-8') as f:
                    hesap_adi = analitik_hesap_name.lower()
                    for satir in f:
                        if hesap_adi in satir.lower():
                            parcalar = satir.strip().split('\t')
                            if len(parcalar) == MagicNumbers.DOSYA_PARSE_PARCA_SAYISI:
                                konum_kodu = parcalar[1]
                                break
        except Exception as e:
            _logger.warning(
                f"Analitik bilgileri dosyası okunamadı veya parse edilemedi: "
                f"{str(e)} - Analitik Hesap: {analitik_hesap_name}"
            )
        
        return konum_kodu

