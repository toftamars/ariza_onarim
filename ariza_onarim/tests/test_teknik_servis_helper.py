# -*- coding: utf-8 -*-
"""
Teknik Servis Helper Testleri

Refactor sonrası adres/telefon hesaplamasının doğruluğunu kontrol eder.
"""

from odoo.tests import TransactionCase

from ..models.ariza_constants import TeknikServis
from ..models.ariza_helpers.teknik_servis_helper import TeknikServisHelper


class TestTeknikServisHelper(TransactionCase):
    """TeknikServisHelper testleri"""

    def test_ngaudio_adres(self):
        """NGaudio adresi doğru dönmeli"""
        adres = TeknikServisHelper.get_adres(TeknikServis.NGAUDIO)
        self.assertEqual(adres, 'Alata Mah şehit yüksel ulak cad no26/b Erdemli Mersin')

    def test_ngaudio_telefon(self):
        """NGaudio telefonu doğru dönmeli"""
        telefon = TeknikServisHelper.get_telefon(TeknikServis.NGAUDIO)
        self.assertEqual(telefon, '0546 786 06 99')

    def test_zuhal_ariza_depo_adres(self):
        """Zuhal Arıza Depo adresi doğru dönmeli"""
        adres = TeknikServisHelper.get_adres(TeknikServis.ZUHAL_ARIZA_DEPO)
        self.assertIn('Halkalı', adres)

    def test_tedarikci_adres_from_partner(self):
        """Tedarikçi adresi partner'dan alınmalı"""
        partner = self.env['res.partner'].create({
            'name': 'Test Tedarikçi',
            'street': 'Test Sokak 1',
            'city': 'İstanbul',
        })
        adres = TeknikServisHelper.get_adres(
            TeknikServis.TEDARIKCI,
            tedarikci_id=partner,
        )
        self.assertIn('Test Sokak', adres)
        self.assertIn('İstanbul', adres)

    def test_tedarikci_adres_ozel_alan_oncelikli(self):
        """Tedarikçi özel adres alanı öncelikli olmalı"""
        partner = self.env['res.partner'].create({
            'name': 'Test Tedarikçi',
            'street': 'Partner Sokak',
        })
        adres = TeknikServisHelper.get_adres(
            TeknikServis.TEDARIKCI,
            tedarikci_id=partner,
            tedarikci_adresi='Özel Teslim Adresi 123',
        )
        self.assertEqual(adres, 'Özel Teslim Adresi 123')
