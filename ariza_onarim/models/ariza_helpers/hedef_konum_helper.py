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

    @staticmethod
    def update_hedef_konum(record):
        """Hedef konumu günceller ve mesaj gönderir."""
        if not record.ariza_tipi or not record.teknik_servis:
            return
        konum = HedefKonumHelper.get_hedef_konum(
            record.env,
            record.teknik_servis,
            record.ariza_tipi,
            company_id=record.company_id.id if record.company_id else record.env.company.id,
            tedarikci_id=record.tedarikci_id,
        )
        record.hedef_konum_id = konum
        if record.ariza_tipi == ArizaTipi.MAGAZA and record.teknik_servis != TeknikServis.MAGAZA:
            try:
                if konum:
                    record.message_post(
                        body=f"✅ Hedef Konum otomatik atandı: <b>{konum.display_name}</b> (Teknik Servis: {record.teknik_servis})",
                        message_type='notification'
                    )
                else:
                    record.message_post(
                        body="⚠️ Hedef konum bulunamadı! Lütfen hedef konumu manuel seçin.",
                        message_type='notification'
                    )
            except Exception:
                pass

    @staticmethod
    def hedef_konum_otomatik_mi(ariza_tipi, teknik_servis, tedarikci_id=None):
        """Bu kombinasyon hedef konumu otomatik atıyor mu?"""
        if not ariza_tipi or not teknik_servis:
            return False
        if ariza_tipi == ArizaTipi.MUSTERI:
            return teknik_servis in (
                TeknikServis.DTL_SERVISLER
                + [TeknikServis.ZUHAL_ARIZA_DEPO, TeknikServis.ZUHAL_NEFESLI, TeknikServis.MAGAZA]
            )
        if ariza_tipi == ArizaTipi.MAGAZA:
            return teknik_servis in (
                TeknikServis.DTL_SERVISLER
                + [
                    TeknikServis.ZUHAL_ARIZA_DEPO,
                    TeknikServis.ZUHAL_NEFESLI,
                    TeknikServis.NGAUDIO,
                    TeknikServis.MATT_GUITAR,
                    TeknikServis.PROHAN_ELK,
                    TeknikServis.ERK_ENSTRUMAN,
                    TeknikServis.MAGAZA,
                ]
            ) or (teknik_servis == TeknikServis.TEDARIKCI and bool(tedarikci_id))
        return False
