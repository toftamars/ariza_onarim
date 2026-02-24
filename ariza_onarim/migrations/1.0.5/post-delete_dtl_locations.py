# -*- coding: utf-8 -*-
"""
Migration: Modülün oluşturduğu stok konumlarını siler.

UYARI: Bu listedeki 7 konum DIŞINDA başka hiçbir konum SİLİNMEZ.
Sadece complete_name tam eşleşen konumlar silinir.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

# SADECE bu 7 konum silinir - bunların dışında başka konum ASLA silinmez
_ALLOWED_COMPLETE_NAMES = frozenset([
    'DEPO/Stok/ARIZA/NGaudio',
    'DEPO/Stok/ARIZA/MATT',
    'DEPO/Stok/ARIZA',
    'DEPO/Stok/ANTL/Antalya Teknik Servis',
    'DEPO/Stok/ANTL',
    'DEPO/Stok/ANKDEPO/Ankara Teknik Servis',
    'DEPO/Stok/ANKDEPO',
])


def migrate(cr, version):
    """Sadece modülün oluşturduğu ve complete_name ile doğrulanan konumları sil."""
    env = api.Environment(cr, SUPERUSER_ID, {})

    # ir.model.data'dan ariza_onarim modülünün oluşturduğu stock.location kayıtları
    imd = env['ir.model.data'].sudo()
    module_data = imd.search([
        ('module', '=', 'ariza_onarim'),
        ('model', '=', 'stock.location'),
        ('res_id', '!=', False),
    ])

    # DOĞRULAMA: Modülün oluşturduğu TÜM konumları logla
    all_module_locations = []
    for data in module_data:
        loc = env['stock.location'].browse(data.res_id)
        if loc.exists():
            all_module_locations.append((data.complete_name, loc.complete_name or '-', loc.id))
    if all_module_locations:
        _logger.info(
            "ariza_onarim modülünün oluşturduğu stock.location kayıtları: %s",
            [(xml_id, complete, lid) for xml_id, complete, lid in all_module_locations]
        )
    else:
        _logger.info("ariza_onarim modülünün oluşturduğu stock.location kaydı yok (silinecek bir şey yok)")

    to_delete = []
    for data in module_data:
        loc = env['stock.location'].browse(data.res_id)
        if not loc.exists():
            continue
        complete = (loc.complete_name or '').strip()
        if complete not in _ALLOWED_COMPLETE_NAMES:
            _logger.info(
                "Atlanıyor (izin verilen listede değil, SİLİNMEZ): xml_id=%s complete_name=%s",
                data.complete_name, complete
            )
            continue
        to_delete.append((data.complete_name, loc, complete))

    # Child önce (en uzun yol), parent sonra
    to_delete.sort(key=lambda x: -len(x[2]))

    # Güvenlik: Silinecek her konum listede olmalı (zaten filtrelendi, ek doğrulama)
    for xml_id, loc, complete in to_delete:
        assert complete in _ALLOWED_COMPLETE_NAMES, f"Güvenlik: {complete} listede yok, silinmeyecek"
        try:
            _logger.info("Silinecek: xml_id=%s complete_name=%s id=%s", xml_id, complete, loc.id)
            loc.unlink()
            _logger.info("Silindi: %s", complete)
        except Exception as e:
            _logger.warning("Silinemedi %s: %s", complete, e)
