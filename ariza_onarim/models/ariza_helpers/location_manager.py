# -*- coding: utf-8 -*-
"""
Location Manager - Merkezi konum yönetimi sınıfı
"""

import logging
from .technical_service_strategy import TechnicalServiceStrategyFactory
from ..ariza_constants import TeknikServis

_logger = logging.getLogger(__name__)


class LocationManager:
    """
    Merkezi konum yönetimi sınıfı.

    Bu sınıf, arıza kayıtları için hedef konum belirleme işlemlerini yönetir.
    TechnicalServiceStrategy pattern'ini kullanarak kod tekrarını önler.
    """

    @staticmethod
    def update_hedef_konum_from_service(record):
        """
        Teknik servise göre hedef konumu günceller.

        Bu metod, create(), _update_hedef_konum() ve _onchange_teknik_servis()
        metodlarındaki tekrarlı kodu elimine eder.

        Args:
            record: ArizaKayit record (self)

        Returns:
            bool: Konum başarıyla güncellendiyse True, aksi halde False
        """
        if not record.teknik_servis:
            _logger.debug("Teknik servis belirtilmediği için konum güncellenemedi")
            return False

        # Strategy factory kullanarak konum güncelle
        success, message = TechnicalServiceStrategyFactory.update_location_for_service(
            record=record,
            teknik_servis=record.teknik_servis
        )

        return success

    @staticmethod
    def validate_hedef_konum(record):
        """
        Hedef konumun doğru bir şekilde ayarlandığını kontrol eder.

        Args:
            record: ArizaKayit record (self)

        Returns:
            tuple: (is_valid: bool, error_message: str or None)
        """
        if not record.hedef_konum_id:
            return False, "Hedef konum belirtilmemiş"

        if not record.hedef_konum_id.active:
            return False, f"Hedef konum ({record.hedef_konum_id.name}) pasif durumda"

        return True, None

    @staticmethod
    def get_kaynak_konum(record):
        """
        Kayıt için kaynak konumu belirler.

        Args:
            record: ArizaKayit record (self)

        Returns:
            stock.location record veya False
        """
        # Önce elle girilmiş kaynak konumu kontrol et
        if record.kaynak_konum_id:
            return record.kaynak_konum_id

        # Mağaza kaydıysa ve analitik hesap varsa
        if record.magaza_id and record.magaza_id.konum_kodu:
            # Konum kodundan konumu bul
            konum = record.env['stock.location'].search([
                ('name', '=', record.magaza_id.konum_kodu)
            ], limit=1)
            if konum:
                return konum

        # Warehouse varsa lot_stock_id'sini döndür
        if record.warehouse_id and record.warehouse_id.lot_stock_id:
            return record.warehouse_id.lot_stock_id

        _logger.warning(f"Kaynak konum belirlenemedi (Arıza: {record.name})")
        return False

    @staticmethod
    def get_arizali_konum(record):
        """
        Arızalı ürünlerin bulunacağı konumu belirler.

        Args:
            record: ArizaKayit record (self)

        Returns:
            stock.location record veya False
        """
        # Kaynak konumdan türetilen arızalı konum
        kaynak_konum = LocationManager.get_kaynak_konum(record)

        if not kaynak_konum:
            return False

        # Kaynak konumun parent'ına ait "Arızalı" child konumu bul
        # Örnek: "ADANA/Stok" -> "ADANA/Arızalı"
        if kaynak_konum.location_id:
            arizali_konum = record.env['stock.location'].search([
                ('location_id', '=', kaynak_konum.location_id.id),
                ('name', 'ilike', 'Arızalı')
            ], limit=1)

            if arizali_konum:
                return arizali_konum

        _logger.warning(f"Arızalı konum belirlenemedi (Arıza: {record.name})")
        return False

    @staticmethod
    def sync_locations_on_create(record):
        """
        Kayıt oluşturulurken (create) konum alanlarını senkronize eder.

        Args:
            record: ArizaKayit record (self)
        """
        # 1. Teknik servise göre hedef konum belirle
        if record.teknik_servis:
            LocationManager.update_hedef_konum_from_service(record)

        # 2. Kaynak konum belirle (eğer yoksa)
        if not record.kaynak_konum_id:
            kaynak = LocationManager.get_kaynak_konum(record)
            if kaynak:
                record.kaynak_konum_id = kaynak

        # 3. Arızalı konum belirle (eğer yoksa)
        if not record.arizali_konum_id:
            arizali = LocationManager.get_arizali_konum(record)
            if arizali:
                record.arizali_konum_id = arizali

    @staticmethod
    def clear_location_if_service_removed(record):
        """
        Teknik servis kaldırıldığında hedef konumu temizler.

        Args:
            record: ArizaKayit record (self)
        """
        if not record.teknik_servis and record.hedef_konum_id:
            record.hedef_konum_id = False
            record.message_post(body="ℹ️ Teknik servis kaldırıldığı için hedef konum temizlendi.")
            _logger.info(f"Hedef konum temizlendi (Arıza: {record.name})")
