# -*- coding: utf-8 -*-
"""
Post-install hooks - Modül yüklendikten sonra çalışacak işlemler
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """
    Modül yüklendikten sonra kritik stok konumlarının varlığını doğrular.
    Eksik konumlar varsa log'a yazılır (modül yüklenmesi engellenmez).
    """
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})

    try:
        from .models.ariza_helpers.location_helper import LocationHelper

        success, missing = LocationHelper.validate_critical_locations(env)
        if not success:
            _logger.warning(
                "Arıza Onarım: Kritik stok konumları eksik: %s. "
                "Transfer işlemleri çalışmayabilir. Lütfen bu konumları oluşturun.",
                ", ".join(missing),
            )
        else:
            _logger.info("Arıza Onarım: Tüm kritik stok konumları doğrulandı.")

    except Exception as e:
        _logger.error("Arıza Onarım post-init hook hatası: %s", str(e))
