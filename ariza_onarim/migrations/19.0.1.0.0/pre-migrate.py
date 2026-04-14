# -*- coding: utf-8 -*-
"""
Migration: 15.0 → 19.0 geçiş için ön hazırlık.

Bu migration Odoo 19 uyumluluk geçişi kapsamında oluşturulmuştur.
Mevcut veriler üzerinde herhangi bir yıkıcı işlem yapılmamaktadır.

Odoo 17-19 arası breaking change'ler Python/model katmanında
kod düzeyinde ele alındığından (fields_view_get→get_views,
stock.production.lot→stock.lot vb.) veritabanı düzeyinde
migration gerekmemektedir.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Pre-migration: 19.0.1.0.0 için hazırlık logu."""
    if not version:
        return
    _logger.info(
        "ariza_onarim: Odoo 19 uyumluluk geçişi başladı "
        "(önceki versiyon: %s)", version
    )
