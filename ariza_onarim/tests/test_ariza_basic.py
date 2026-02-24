# -*- coding: utf-8 -*-
"""
Arıza Onarım - Temel Model Testleri

ariza.kayit modeli ve temel işlemler.
"""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError, UserError


class TestArizaBasic(TransactionCase):
    """ariza.kayit temel testleri"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ArizaKayit = cls.env['ariza.kayit']
        # Analitik hesap oluştur (mağaza kaydı için gerekli)
        cls.analytic = cls.env['account.analytic.account'].create({
            'name': 'Test Mağaza',
        })

    def test_ariza_model_exists(self):
        """ariza.kayit modeli yüklü olmalı"""
        self.assertTrue(self.ArizaKayit._name == 'ariza.kayit')

    def test_ariza_create_magaza_minimal(self):
        """Mağaza ürünü arıza kaydı oluşturulabilmeli"""
        from ..models.ariza_constants import ArizaTipi, TeknikServis

        record = self.ArizaKayit.create({
            'ariza_tipi': ArizaTipi.MAGAZA,
            'teknik_servis': TeknikServis.ZUHAL_ARIZA_DEPO,
            'analitik_hesap_id': self.analytic.id,
        })
        self.assertTrue(record.id)
        self.assertEqual(record.ariza_tipi, ArizaTipi.MAGAZA)
        self.assertEqual(record.state, 'draft')

    def test_ariza_name_auto_generated(self):
        """Arıza numarası otomatik oluşturulmalı"""
        from ..models.ariza_constants import ArizaTipi, TeknikServis

        record = self.ArizaKayit.create({
            'ariza_tipi': ArizaTipi.MAGAZA,
            'teknik_servis': TeknikServis.ZUHAL_ARIZA_DEPO,
            'analitik_hesap_id': self.analytic.id,
        })
        self.assertTrue(record.name)
        self.assertNotEqual(record.name, 'New')
