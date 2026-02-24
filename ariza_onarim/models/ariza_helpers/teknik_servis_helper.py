# -*- coding: utf-8 -*-
"""
Teknik Servis Helper - Adres ve telefon bilgileri

Teknik servis adres/telefon hesaplamasını merkezileştirir.
"""

from ..ariza_constants import TeknikServis


class TeknikServisHelper:
    """Teknik servis adres ve telefon bilgileri"""

    # Sabit adresler (teknik_servis kodu -> adres)
    ADRES_MAP = {
        TeknikServis.ZUHAL_ARIZA_DEPO: 'Halkalı merkez mh. Dereboyu cd. No:8/B İstanbul',
        TeknikServis.DTL_BEYOGLU: 'Şahkulu mh. Nakkas çıkmazı No: 1/1 No:10-46 / 47',
        TeknikServis.DTL_OKMEYDANI: 'MAHMUT ŞEVKET PAŞA MAH. ŞAHİNKAYA SOK NO 31 OKMEYDANI',
        TeknikServis.ZUHAL_NEFESLI: 'Şahkulu, Galip Dede Cd. No:33, 34421 Beyoğlu/İstanbul',
        TeknikServis.PROHAN_ELK: 'ÜÇGEN MAH. 107 SK NO: 7/1, Antalya, 07040',
        TeknikServis.NGAUDIO: 'Alata Mah şehit yüksel ulak cad no26/b Erdemli Mersin',
        TeknikServis.MATT_GUITAR: 'HASANPASA MAH. ALIBEY SOK. 21/A, KADIKÖY, İstanbul, 34000',
        TeknikServis.ERK_ENSTRUMAN: 'KOCATEPE MAH İNKLAP SOK ÖZSOY APT NO:31/1, ÇANKAYA, Ankara, 06000',
    }

    # Sabit telefonlar (teknik_servis kodu -> telefon)
    TELEFON_MAP = {
        TeknikServis.ZUHAL_ARIZA_DEPO: '0212 555 55 55',
        TeknikServis.DTL_BEYOGLU: '0212 555 55 56',
        TeknikServis.DTL_OKMEYDANI: '0212 555 55 57',
        TeknikServis.ZUHAL_NEFESLI: '0212 555 55 58',
        TeknikServis.NGAUDIO: '0546 786 06 99',
    }

    @staticmethod
    def get_adres(teknik_servis, tedarikci_id=None, tedarikci_adresi=None):
        """
        Teknik servis adresini döner.

        Args:
            teknik_servis: Teknik servis kodu
            tedarikci_id: res.partner (Tedarikçi seçiliyse)
            tedarikci_adresi: Tedarikçi adresi (özel alan)

        Returns:
            str: Adres metni
        """
        if teknik_servis == TeknikServis.TEDARIKCI and tedarikci_id:
            if tedarikci_adresi:
                return tedarikci_adresi
            adres_parcalari = []
            if tedarikci_id.street:
                adres_parcalari.append(tedarikci_id.street)
            if tedarikci_id.street2:
                adres_parcalari.append(tedarikci_id.street2)
            if tedarikci_id.city:
                adres_parcalari.append(tedarikci_id.city)
            if tedarikci_id.state_id:
                adres_parcalari.append(tedarikci_id.state_id.name)
            if tedarikci_id.zip:
                adres_parcalari.append(tedarikci_id.zip)
            if tedarikci_id.country_id:
                adres_parcalari.append(tedarikci_id.country_id.name)
            return ', '.join(adres_parcalari) if adres_parcalari else ''
        return TeknikServisHelper.ADRES_MAP.get(teknik_servis, '')

    @staticmethod
    def get_telefon(teknik_servis, tedarikci_id=None):
        """
        Teknik servis telefonunu döner.

        Args:
            teknik_servis: Teknik servis kodu
            tedarikci_id: res.partner (Tedarikçi seçiliyse)

        Returns:
            str: Telefon numarası
        """
        if teknik_servis == TeknikServis.TEDARIKCI and tedarikci_id:
            return tedarikci_id.phone or tedarikci_id.mobile or ''
        return TeknikServisHelper.TELEFON_MAP.get(teknik_servis, '')
