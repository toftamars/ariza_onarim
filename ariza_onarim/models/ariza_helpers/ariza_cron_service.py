# -*- coding: utf-8 -*-
"""
Arıza Cron Service - Günlük cron işlemleri

_check_onarim_deadlines mantığı - hatırlatma işaretleme.
"""

import logging
from datetime import datetime, timedelta

from odoo import fields

from ..ariza_constants import MagicNumbers

_logger = logging.getLogger(__name__)


class ArizaCronService:
    """Arıza cron işlemleri"""

    @staticmethod
    def check_onarim_deadlines(ariza_model):
        """Onarım süreçlerini kontrol et, hatırlatma işaretle"""
        bugun = datetime.now().date()
        hatirlatma_gereken_kayitlar = ariza_model.search([
            ('onarim_baslangic_tarihi', '!=', False),
            ('onarim_durumu', 'in', ['beklemede', 'devam_ediyor']),
            ('state', 'not in', ['tamamlandi', 'teslim_edildi', 'iptal']),
            '|',
            ('hatirlatma_gonderildi', '=', False),
            ('son_hatirlatma_tarihi', '<', bugun - timedelta(days=3)),
        ])
        for kayit in hatirlatma_gereken_kayitlar:
            if kayit.kalan_is_gunu <= MagicNumbers.HATIRLATMA_IS_GUNU:
                kayit.hatirlatma_gonderildi = True
                kayit.son_hatirlatma_tarihi = fields.Date.today()
                _logger.info(f"Onarım hatırlatma işaretlendi: {kayit.name} - Kalan süre: {kayit.kalan_is_gunu} gün")

    @staticmethod
    def update_kalan_sure(ariza_model):
        """Kalan süre computed alanlarını günceller (cron)"""
        records = ariza_model.search([('state', 'not in', ['teslim_edildi'])])
        if records:
            records.invalidate_cache(['beklenen_tamamlanma_tarihi'])
            records._compute_beklenen_tamamlanma_tarihi()
            records.invalidate_cache(['kalan_is_gunu', 'kalan_sure_gosterimi'])
            records._compute_kalan_is_gunu()
            records._compute_kalan_sure_gosterimi()
            _logger.info(f"Kalan süre güncellendi: {len(records)} kayıt")
