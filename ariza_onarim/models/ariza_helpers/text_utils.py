# -*- coding: utf-8 -*-
"""
Text Utility Functions - Metin işleme yardımcı fonksiyonları
"""

from ..ariza_constants import MagicNumbers


class TextUtils:
    """Metin işleme yardımcı fonksiyonları"""

    @staticmethod
    def clean_perakende_prefix(magaza_adi):
        """
        Mağaza adından 'Perakende - ' önekini temizler.

        Args:
            magaza_adi (str): Mağaza adı

        Returns:
            str: Temizlenmiş mağaza adı

        Example:
            >>> TextUtils.clean_perakende_prefix("Perakende - İstanbul")
            "İstanbul"
            >>> TextUtils.clean_perakende_prefix("İstanbul")
            "İstanbul"
        """
        if not magaza_adi:
            return magaza_adi

        if magaza_adi.startswith("Perakende - "):
            return magaza_adi[MagicNumbers.PERAKENDE_PREFIX_LENGTH:]

        return magaza_adi

    @staticmethod
    def format_phone(phone):
        """
        Telefon numarasını formatlar (boşlukları ve özel karakterleri temizler).

        Args:
            phone (str): Ham telefon numarası

        Returns:
            str: Formatlanmış telefon numarası
        """
        if not phone:
            return phone

        # Boşlukları, tire ve parantezleri temizle
        return phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    @staticmethod
    def truncate_text(text, max_length=50, suffix="..."):
        """
        Metni belirtilen uzunlukta keser.

        Args:
            text (str): Kesilecek metin
            max_length (int): Maksimum uzunluk
            suffix (str): Kesilen metne eklenecek son ek

        Returns:
            str: Kesilmiş metin
        """
        if not text:
            return text

        if len(text) <= max_length:
            return text

        return text[:max_length - len(suffix)] + suffix
