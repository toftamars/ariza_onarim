# -*- coding: utf-8 -*-
"""
Hedef Konum Helper - Teknik servise göre hedef konum belirleme

Arıza tipi ve teknik servis seçimine göre hedef stok konumunu döner.
"""

import logging
from ..ariza_constants import ArizaTipi, TeknikServis
from . import location_helper

_logger = logging.getLogger(__name__)


class HedefKonumHelper:
    """Teknik servis -> hedef konum eşlemesi"""

    @staticmethod
    def get_hedef_konum(env, teknik_servis, ariza_tipi, company_id=None, tedarikci_id=None):
        """
        Teknik servis ve arıza tipine göre hedef konumu döner.

        Args:
            env: Odoo environment
            teknik_servis: Teknik servis kodu
            ariza_tipi: Müşteri veya Mağaza
            company_id: Şirket ID (opsiyonel)
            tedarikci_id: res.partner (Tedarikçi seçiliyse)

        Returns:
            stock.location veya False
        """
        if not teknik_servis or not ariza_tipi:
            return False

        company_id = company_id or env.company.id

        # MAGAZA teknik servisi -> hedef boş
        if teknik_servis == TeknikServis.MAGAZA:
            return False

        # TEDARİKÇİ -> tedarikçi konumu
        if teknik_servis == TeknikServis.TEDARIKCI and tedarikci_id:
            return tedarikci_id.property_stock_supplier or False

        # DTL servisleri
        if teknik_servis in TeknikServis.DTL_SERVISLER:
            return location_helper.LocationHelper.get_dtl_stok_location(
                env, company_id
            )

        # ZUHAL ARIZA DEPO
        if teknik_servis == TeknikServis.ZUHAL_ARIZA_DEPO:
            konum = location_helper.LocationHelper.get_ariza_stok_location(
                env, company_id
            )
            if not konum:
                konum = env['stock.location'].search([
                    ('complete_name', 'ilike', 'Arıza/Stok')
                ], limit=1) or env['stock.location'].search([
                    ('name', 'ilike', 'Arıza'),
                    ('name', 'ilike', 'Stok'),
                ], limit=1)
            return konum or False

        # ZUHAL NEFESLİ
        if teknik_servis == TeknikServis.ZUHAL_NEFESLI:
            konum = location_helper.LocationHelper.get_nfsl_stok_location(
                env, company_id
            )
            if not konum:
                konum = env['stock.location'].search([
                    ('complete_name', 'ilike', 'NFSL/Stok')
                ], limit=1) or env['stock.location'].search([
                    ('name', 'ilike', 'NFSL'),
                    ('name', 'ilike', 'Stok'),
                ], limit=1)
            return konum or False

        # NGaudio
        if teknik_servis == TeknikServis.NGAUDIO:
            konum = location_helper.LocationHelper.get_ngaudio_location(
                env, company_id
            )
            if not konum:
                konum = env['stock.location'].search([
                    ('complete_name', 'ilike', 'ARIZA/NGaudio')
                ], limit=1) or env['stock.location'].search([
                    ('name', 'ilike', 'NGaudio')
                ], limit=1)
            return konum or False

        # MATT Guitar
        if teknik_servis == TeknikServis.MATT_GUITAR:
            konum = location_helper.LocationHelper.get_matt_guitar_location(
                env, company_id
            )
            if not konum:
                konum = env['stock.location'].search([
                    ('complete_name', 'ilike', 'ARIZA/MATT')
                ], limit=1) or env['stock.location'].search([
                    ('name', 'ilike', 'MATT')
                ], limit=1)
            return konum or False

        # Prohan Elk
        if teknik_servis == TeknikServis.PROHAN_ELK:
            konum = location_helper.LocationHelper.get_prohan_elk_location(
                env, company_id
            )
            if not konum:
                konum = env['stock.location'].search([
                    ('complete_name', 'ilike', 'ANTL/Antalya Teknik Servis')
                ], limit=1)
            return konum or False

        # ERK ENSTRÜMAN
        if teknik_servis == TeknikServis.ERK_ENSTRUMAN:
            konum = location_helper.LocationHelper.get_erk_enstruman_location(
                env, company_id
            )
            if not konum:
                konum = env['stock.location'].search([
                    ('complete_name', 'ilike', 'ANKDEPO/Ankara Teknik Servis')
                ], limit=1) or env['stock.location'].search([
                    ('complete_name', 'ilike', 'ANKDEPO'),
                    ('name', 'ilike', 'Ankara')
                ], limit=1)
            return konum or False

        return False
