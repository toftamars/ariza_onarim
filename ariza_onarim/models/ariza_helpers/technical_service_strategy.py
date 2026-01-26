# -*- coding: utf-8 -*-
"""
Technical Service Strategy Pattern - Teknik servis işlemlerini yönetir
"""

import logging
from ..ariza_constants import TeknikServis, LocationNames
from . import location_helper

_logger = logging.getLogger(__name__)


class BaseTechnicalServiceStrategy:
    """Tüm teknik servis stratejilerinin base class'ı"""

    service_name = None  # Alt sınıflarda override edilecek

    @classmethod
    def get_location(cls, env, company_id=None):
        """
        Teknik servis için hedef konumu bulur.
        Alt sınıflarda override edilmeli.

        Args:
            env: Odoo environment
            company_id: Company ID

        Returns:
            stock.location record veya False
        """
        raise NotImplementedError("Alt sınıflarda implement edilmeli")

    @classmethod
    def get_success_message(cls, location):
        """
        Konum bulunduğunda gösterilecek başarı mesajı.

        Args:
            location: stock.location record

        Returns:
            str: Başarı mesajı
        """
        return f"✅ Hedef Konum: <strong>{location.display_name}</strong> olarak belirlendi."

    @classmethod
    def get_error_message(cls):
        """
        Konum bulunamadığında gösterilecek hata mesajı.

        Returns:
            str: Hata mesajı
        """
        return f"⚠️ {cls.service_name or 'Teknik servis'} konumu bulunamadı. Lütfen manuel olarak hedef konum seçiniz."


class DTLBeyogluStrategy(BaseTechnicalServiceStrategy):
    """DTL Beyoğlu teknik servis stratejisi"""

    service_name = "DTL BEYOĞLU"

    @classmethod
    def get_location(cls, env, company_id=None):
        return location_helper.LocationHelper.get_dtl_beyoglu_location(env, company_id)


class DTLOkmeydaniStrategy(BaseTechnicalServiceStrategy):
    """DTL Okmeydanı teknik servis stratejisi"""

    service_name = "DTL OKMEYDANI"

    @classmethod
    def get_location(cls, env, company_id=None):
        return location_helper.LocationHelper.get_dtl_okmeydani_location(env, company_id)


class ZuhalArizaDepoStrategy(BaseTechnicalServiceStrategy):
    """Zuhal Arıza Depo teknik servis stratejisi"""

    service_name = "ZUHAL ARIZA DEPO"

    @classmethod
    def get_location(cls, env, company_id=None):
        return location_helper.LocationHelper.get_zuhal_ariza_depo_location(env, company_id)


class ZuhalNefesliStrategy(BaseTechnicalServiceStrategy):
    """Zuhal Nefesli teknik servis stratejisi"""

    service_name = "ZUHAL NEFESLİ"

    @classmethod
    def get_location(cls, env, company_id=None):
        return location_helper.LocationHelper.get_nfsl_arizali_location(env, company_id)


class NGAudioStrategy(BaseTechnicalServiceStrategy):
    """NGAUDIO teknik servis stratejisi"""

    service_name = "NGAUDIO"

    @classmethod
    def get_location(cls, env, company_id=None):
        return location_helper.LocationHelper.get_ngaudio_location(env, company_id)


class MattGuitarStrategy(BaseTechnicalServiceStrategy):
    """Matt Guitar teknik servis stratejisi"""

    service_name = "MATT GUITAR"

    @classmethod
    def get_location(cls, env, company_id=None):
        return location_helper.LocationHelper.get_matt_guitar_location(env, company_id)


class ProhanElkStrategy(BaseTechnicalServiceStrategy):
    """Prohan Elk teknik servis stratejisi"""

    service_name = "PROHAN ELK"

    @classmethod
    def get_location(cls, env, company_id=None):
        return location_helper.LocationHelper.get_prohan_elk_location(env, company_id)


class ErkEnstrumanStrategy(BaseTechnicalServiceStrategy):
    """Erk Enstrüman teknik servis stratejisi"""

    service_name = "ERK ENSTRÜMAN"

    @classmethod
    def get_location(cls, env, company_id=None):
        return location_helper.LocationHelper.get_erk_enstruman_location(env, company_id)


class TechnicalServiceStrategyFactory:
    """
    Technical Service Strategy Factory - Teknik servise göre doğru strategy'yi döndürür.

    Bu factory sınıfı, teknik servis tipine göre ilgili strategy instance'ını döndürür.
    Strategy Pattern kullanarak kod tekrarını azaltır ve yeni teknik servis eklemeyi kolaylaştırır.
    """

    # Teknik servis -> Strategy class mapping
    _strategies = {
        TeknikServis.DTL_BEYOGLU: DTLBeyogluStrategy,
        TeknikServis.DTL_OKMEYDANI: DTLOkmeydaniStrategy,
        TeknikServis.ZUHAL_ARIZA_DEPO: ZuhalArizaDepoStrategy,
        TeknikServis.ZUHAL_NEFESLI: ZuhalNefesliStrategy,
        TeknikServis.NGAUDIO: NGAudioStrategy,
        TeknikServis.MATT_GUITAR: MattGuitarStrategy,
        TeknikServis.PROHAN_ELK: ProhanElkStrategy,
        TeknikServis.ERK_ENSTRUMAN: ErkEnstrumanStrategy,
    }

    @classmethod
    def get_strategy(cls, teknik_servis):
        """
        Teknik servise göre ilgili strategy class'ını döndürür.

        Args:
            teknik_servis (str): Teknik servis tipi (TeknikServis constant'larından biri)

        Returns:
            BaseTechnicalServiceStrategy subclass veya None
        """
        return cls._strategies.get(teknik_servis)

    @classmethod
    def update_location_for_service(cls, record, teknik_servis, env=None):
        """
        Teknik servise göre hedef konumu bulur ve kaydı günceller.

        Args:
            record: ArizaKayit record (self)
            teknik_servis: Teknik servis tipi
            env: Odoo environment (opsiyonel, record.env kullanılır)

        Returns:
            tuple: (success: bool, message: str)
        """
        if env is None:
            env = record.env

        strategy = cls.get_strategy(teknik_servis)

        if not strategy:
            _logger.warning(f"Teknik servis için strategy bulunamadı: {teknik_servis}")
            return False, "Teknik servis için konum stratejisi bulunamadı."

        # Konum bul
        company_id = record.company_id.id if record.company_id else env.company.id
        location = strategy.get_location(env, company_id)

        if location:
            # Hedef konumu güncelle
            record.hedef_konum_id = location
            success_msg = strategy.get_success_message(location)
            record.message_post(body=success_msg)
            _logger.info(f"Hedef konum belirlendi: {location.display_name} (Teknik Servis: {strategy.service_name})")
            return True, success_msg
        else:
            # Konum bulunamadı
            error_msg = strategy.get_error_message()
            record.message_post(body=error_msg)
            _logger.warning(f"Konum bulunamadı (Teknik Servis: {strategy.service_name})")
            return False, error_msg

    @classmethod
    def register_strategy(cls, teknik_servis, strategy_class):
        """
        Yeni bir teknik servis stratejisi kaydeder.

        Bu method, dinamik olarak yeni teknik servis stratejileri eklemek için kullanılabilir.

        Args:
            teknik_servis (str): Teknik servis tipi
            strategy_class: BaseTechnicalServiceStrategy'den türeyen class
        """
        if not issubclass(strategy_class, BaseTechnicalServiceStrategy):
            raise ValueError(f"{strategy_class} BaseTechnicalServiceStrategy'den türemelidir")

        cls._strategies[teknik_servis] = strategy_class
        _logger.info(f"Yeni teknik servis stratejisi kaydedildi: {teknik_servis} -> {strategy_class.__name__}")

    @classmethod
    def get_all_strategies(cls):
        """
        Tüm kayıtlı stratejileri döndürür.

        Returns:
            dict: {teknik_servis: strategy_class} mapping
        """
        return cls._strategies.copy()
