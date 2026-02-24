# -*- coding: utf-8 -*-
"""
Arıza Onarım - Constants Testleri

Sabit değerlerin doğruluğunu kontrol eder. Veritabanı gerektirmez.
"""

from odoo.tests import TransactionCase


class TestArizaConstants(TransactionCase):
    """ariza_constants modülü testleri"""

    def test_ariza_states_defined(self):
        """ArizaStates tüm durumları içermeli"""
        from ..models.ariza_constants import ArizaStates

        expected = [
            ('DRAFT', 'draft'), ('PERSONEL_ONAY', 'personel_onay'),
            ('KABUL_EDILDI', 'kabul_edildi'), ('TEKNIK_ONARIM', 'teknik_onarim'),
            ('ONAYLANDI', 'onaylandi'), ('YONETICI_TAMAMLANDI', 'yonetici_tamamlandi'),
            ('TAMAMLANDI', 'tamamlandi'), ('TESLIM_EDILDI', 'teslim_edildi'),
            ('ONARIM_DISI', 'onarim_disi'), ('KILITLI', 'kilitli'), ('IPTAL', 'iptal'),
        ]
        for attr_name, expected_val in expected:
            self.assertTrue(hasattr(ArizaStates, attr_name),
                            f"ArizaStates.{attr_name} tanımlı olmalı")
            self.assertEqual(getattr(ArizaStates, attr_name), expected_val)

    def test_teknik_servis_selection(self):
        """TeknikServis SELECTION boş olmamalı"""
        from ..models.ariza_constants import TeknikServis

        self.assertGreater(len(TeknikServis.SELECTION), 0)
        for code, label in TeknikServis.SELECTION:
            self.assertTrue(code, "Teknik servis kodu boş olmamalı")
            self.assertTrue(label, "Teknik servis etiketi boş olmamalı")

    def test_ariza_tipi_values(self):
        """ArizaTipi MUSTERI ve MAGAZA içermeli"""
        from ..models.ariza_constants import ArizaTipi

        self.assertEqual(ArizaTipi.MUSTERI, 'musteri')
        self.assertEqual(ArizaTipi.MAGAZA, 'magaza')
