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
    KABUL_EDILDI = 'kabul_edildi'
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
        (KABUL_EDILDI, 'Kabul Edildi'),
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
    NGAUDIO = 'NGAUDIO'
    ERK_ENSTRUMAN = 'ERK ENSTRÜMAN'
    MATT_GUITAR = 'MATT Guitar'
    PROHAN_ELK = 'Prohan Elk.'
    
    # Teknik servis selection listesi
    SELECTION = [
        (DTL_BEYOGLU, 'DTL BEYOĞLU'),
        (DTL_OKMEYDANI, 'DTL OKMEYDANI'),
        (ZUHAL_ARIZA_DEPO, 'ZUHAL ARIZA DEPO'),
        (MAGAZA, 'MAĞAZA'),
        (ZUHAL_NEFESLI, 'ZUHAL NEFESLİ'),
        (TEDARIKCI, 'TEDARİKÇİ'),
        (NGAUDIO, 'NGaudio'),
        (ERK_ENSTRUMAN, 'ERK ENSTRÜMAN'),
        (MATT_GUITAR, 'MATT Guitar'),
        (PROHAN_ELK, 'Prohan Elk.'),
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
    ARIZA_STOK = 'Arıza/Stok'
    NFSL_ARIZALI = 'NFSL/Arızalı'
    NFSL_STOK = 'NFSL/Stok'


class PartnerNames:
    """Partner isimleri (res.partner için)"""
    ZUHAL_DIS_TICARET = 'Zuhal Dış Ticaret A.Ş.'
    DTL_ELEKTRONIK = 'Dtl Elektronik Servis Hiz. Tic. Ltd Şti'


class MagicNumbers:
    """Magic number'lar - Kod içinde kullanılan sabit sayısal değerler"""
    # Garanti süresi (ay)
    DEFAULT_GARANTI_AY = 24  # 2 yıl
    GARANTI_AY_FALLBACK = 24  # Fallback değer
    
    # Tarih hesaplamaları
    GUN_AY_CARPI = 30  # Gün/ay dönüşümü için
    
    # Onarım süresi (iş günü)
    ONARIM_IS_GUNU = 20  # Onarım için beklenen iş günü
    
    # Hafta günü kontrolü
    HAFTA_SONU_BASLANGIC = 5  # 5 = Cuma, 0-4 = Pazartesi-Cuma (iş günü)
    
    # Hatırlatma ve uyarı limitleri
    HATIRLATMA_IS_GUNU = 3  # 3 iş günü veya daha az kaldıysa hatırlat
    UYARI_IS_GUNU = 5  # 5 gün veya daha az kaldıysa uyar
    KRITIK_IS_GUNU = 7  # 7 gün veya daha az kaldıysa kritik
    
    # String işlemleri
    PERAKENDE_PREFIX_LENGTH = 12  # "Perakende - " uzunluğu
    
    # Dosya parse
    DOSYA_PARSE_PARCA_SAYISI = 2  # Tab-separated dosya parse için beklenen parça sayısı


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


class SMSTemplates:
    """
    SMS Şablonları - SMS metinlerini buradan kolayca değiştirebilirsiniz.
    
    Placeholder'lar:
    - {musteri_adi}: Müşteri adı
    - {urun}: Ürün adı
    - {kayit_no}: Arıza kayıt numarası
    - {magaza_adi}: Mağaza adı (temizlenmiş)
    - {teslim_tarihi}: Teslim tarihi ve saati (format: dd.mm.yyyy HH:MM)
    - {teslim_alan_kisi}: Teslim alan kişi adı
    
    Örnek kullanım:
        template = SMSTemplates.ILK_SMS.format(
            musteri_adi="Ahmet Yılmaz",
            urun="iPhone 14 Pro",
            kayit_no="ARIZA-2024-001"
        )
    """
    
    # İlk SMS - Personel Onayı (Onayla butonuna basıldığında)
    ILK_SMS = (
        "Sayın {musteri_adi}., {urun} ürününüz teslim alındı, "
        "Ürününüz onarım sürecine alınmıştır. Kayıt No: {kayit_no} B021"
    )
    
    # İkinci SMS - Teslim Edilmeye Hazır (Hazır butonuna basıldığında)
    IKINCI_SMS = (
        "Sayın {musteri_adi}., {urun} ürününüz teslim edilmeye hazırdır. "
        "Ürününüzü {magaza_adi} mağazamızdan teslim alabilirsiniz. "
        "Kayıt No: {kayit_no} B021"
    )
    
    # Üçüncü SMS - Teslim Edildi (Teslim Et wizard'ında - Mağazadan teslim)
    UCUNCU_SMS = (
        "Sayın {musteri_adi}. {urun} ürününüz {magaza_adi} mağazamızdan "
        "{teslim_tarihi} tarihinde {teslim_alan_kisi} kişisine teslim edilmiştir. "
        "Kayıt No: {kayit_no} B021"
    )
    
    # Adrese Gönderim SMS - Adresime Gönderilsin seçeneği için
    ADRESE_GONDERIM_SMS = (
        "Sayın {musteri_adi}. {urun} ürününüz adresinize gönderilmiştir. "
        "{teslim_tarihi} tarihinde. "
        "Kayıt No: {kayit_no} B021"
    )
    
    # Garanti/Ürün Değişimi Eklentisi (Üçüncü SMS'e eklenir)
    GARANTI_EKLENTISI = " Ürününüzün değişimi sağlanmıştır."

