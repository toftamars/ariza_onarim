# -*- coding: utf-8 -*-
"""
Arıza Onarım Modülü - Constants Dosyası

Bu dosya modülde kullanılan tüm sabit değerleri içerir.
Magic string'lerin ve hardcoded değerlerin merkezi kaynağıdır.
"""


class ArizaStates:
    """Arıza kaydı durumları (state field için)"""
    DRAFT = 'draft'
    PERSONEL_ONAY = 'personel_onay'
    TEKNIK_ONARIM = 'teknik_onarim'
    ONAYLANDI = 'onaylandi'
    YONETICI_TAMAMLANDI = 'yonetici_tamamlandi'
    TAMAMLANDI = 'tamamlandi'
    TESLIM_EDILDI = 'teslim_edildi'
    KILITLI = 'kilitli'
    IPTAL = 'iptal'
    
    # State selection listesi (Odoo field için)
    SELECTION = [
        (DRAFT, 'Taslak'),
        (PERSONEL_ONAY, 'Personel Onayı'),
        (TEKNIK_ONARIM, 'Teknik Onarım'),
        (ONAYLANDI, 'Onaylandı'),
        (YONETICI_TAMAMLANDI, 'Yönetici Tamamlandı'),
        (TAMAMLANDI, 'Tamamlandı'),
        (TESLIM_EDILDI, 'Teslim Edildi'),
        (KILITLI, 'Kilitli'),
        (IPTAL, 'İptal'),
    ]


class StateManager:
    """Yönetici görünümü için durum değerleri (state_manager field için)"""
    DRAFT = 'draft'
    ONAYLANDI = 'onaylandi'
    ONARIMDA = 'onarimda'
    ONARIM_TAMAMLANDI = 'onarim_tamamlandi'
    TAMAMLANDI = 'tamamlandi'
    TESLIM_EDILDI = 'teslim_edildi'
    KILITLI = 'kilitli'
    IPTAL = 'iptal'
    
    # State manager selection listesi
    SELECTION = [
        (DRAFT, 'Taslak'),
        (ONAYLANDI, 'Onaylandı'),
        (ONARIMDA, 'Onarımda'),
        (ONARIM_TAMAMLANDI, 'Onarım Tamamlandı'),
        (TAMAMLANDI, 'Tamamlandı'),
        (TESLIM_EDILDI, 'Teslim Edildi'),
        (KILITLI, 'Kilitli'),
        (IPTAL, 'İptal'),
    ]


class TeknikServis:
    """Teknik servis seçenekleri"""
    DTL_BEYOGLU = 'DTL BEYOĞLU'
    DTL_OKMEYDANI = 'DTL OKMEYDANI'
    ZUHAL_ARIZA_DEPO = 'ZUHAL ARIZA DEPO'
    MAGAZA = 'MAĞAZA'
    ZUHAL_NEFESLI = 'ZUHAL NEFESLİ'
    TEDARIKCI = 'TEDARİKÇİ'
    
    # Teknik servis selection listesi
    SELECTION = [
        (DTL_BEYOGLU, 'DTL BEYOĞLU'),
        (DTL_OKMEYDANI, 'DTL OKMEYDANI'),
        (ZUHAL_ARIZA_DEPO, 'ZUHAL ARIZA DEPO'),
        (MAGAZA, 'MAĞAZA'),
        (ZUHAL_NEFESLI, 'ZUHAL NEFESLİ'),
        (TEDARIKCI, 'TEDARİKÇİ'),
    ]
    
    # DTL teknik servisleri listesi (karşılaştırma için)
    DTL_SERVISLER = [DTL_BEYOGLU, DTL_OKMEYDANI]
    
    # Zuhal teknik servisleri listesi
    ZUHAL_SERVISLER = [ZUHAL_ARIZA_DEPO, ZUHAL_NEFESLI]


class ArizaTipi:
    """Arıza tipi seçenekleri"""
    MUSTERI = 'musteri'
    MAGAZA = 'magaza'
    
    # Arıza tipi selection listesi
    SELECTION = [
        (MUSTERI, 'Müşteri Ürünü'),
        (MAGAZA, 'Mağaza Ürünü'),
    ]


class IslemTipi:
    """İşlem tipi seçenekleri"""
    ARIZA_KABUL = 'ariza_kabul'
    
    # İşlem tipi selection listesi
    SELECTION = [
        (ARIZA_KABUL, 'Arıza Kabul'),
    ]


class TransferMetodu:
    """Transfer metodu seçenekleri"""
    ARAC = 'arac'
    UCRETSIZ_KARGO = 'ucretsiz_kargo'
    UCRETLI_KARGO = 'ucretli_kargo'
    MAGAZA = 'magaza'
    
    # Transfer metodu selection listesi
    SELECTION = [
        (ARAC, 'Araç'),
        (UCRETSIZ_KARGO, 'Ücretsiz Kargo'),
        (UCRETLI_KARGO, 'Ücretli Kargo'),
        (MAGAZA, 'Mağaza'),
    ]


class GarantiKapsam:
    """Garanti kapsamı seçenekleri"""
    EVET = 'evet'
    HAYIR = 'hayir'
    URUN_DEGISIMI = 'urun_degisimi'
    
    # Garanti kapsamı selection listesi
    SELECTION = [
        (EVET, 'Evet'),
        (HAYIR, 'Hayır'),
        (URUN_DEGISIMI, 'Ürün Değişimi'),
    ]


class TeslimAlan:
    """Teslim alan seçenekleri (Char field olarak kullanılıyor ama değerler sabit)"""
    TESLIM_MAGAZASI = 'Teslim Mağazası'
    ADRESE_GONDERIM = 'Adrese Gönderim'
    
    # Teslim alan seçenekleri listesi
    OPTIONS = [TESLIM_MAGAZASI, ADRESE_GONDERIM]


class LocationNames:
    """Konum isimleri (stock.location için)"""
    DTL_STOK = 'DTL/Stok'


class PartnerNames:
    """Partner isimleri (res.partner için)"""
    ZUHAL_DIS_TICARET = 'Zuhal Dış Ticaret A.Ş.'
    DTL_ELEKTRONIK = 'Dtl Elektronik Servis Hiz. Tic. Ltd Şti'


class DefaultValues:
    """Default değerler ve sabitler"""
    # Default driver ID (system parameter'a taşınacak)
    DEFAULT_DRIVER_ID = 2205
    
    # Default transfer metodu
    DEFAULT_TRANSFER_METODU = TransferMetodu.ARAC
    
    # Default işlem tipi
    DEFAULT_ISLEM_TIPI = IslemTipi.ARIZA_KABUL
    
    # Default state
    DEFAULT_STATE = ArizaStates.DRAFT
    
    # Default garanti kapsamı
    DEFAULT_GARANTI_KAPSAM = GarantiKapsam.HAYIR

