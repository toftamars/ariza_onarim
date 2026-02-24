# -*- coding: utf-8 -*-
"""
Arıza Computed Helper - Computed alan hesaplama mantığı

_compute_* metodlarından taşınan hesaplama mantığı.
"""

from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from ..ariza_constants import ArizaStates, ArizaTipi, MagicNumbers, StateManager, TeknikServis


class ArizaComputedHelper:
    """Arıza kaydı computed alan hesaplamaları"""

    @staticmethod
    def compute_fatura_tarihi(record):
        """Fatura tarihini döner."""
        if record.invoice_line_id and record.invoice_line_id.move_id:
            return record.invoice_line_id.move_id.invoice_date
        return False

    @staticmethod
    def compute_garanti_suresi(record):
        """(garanti_suresi, garanti_bitis_tarihi, kalan_garanti) tuple döner."""
        if not record.invoice_line_id or not record.fatura_tarihi:
            return (False, False, False)
        garanti_ay = MagicNumbers.DEFAULT_GARANTI_AY
        if record.invoice_line_id.product_id and hasattr(record.invoice_line_id.product_id, 'garanti_suresi'):
            garanti_ay = record.invoice_line_id.product_id.garanti_suresi or MagicNumbers.GARANTI_AY_FALLBACK
        garanti_bitis = record.fatura_tarihi + relativedelta(months=garanti_ay)
        garanti_suresi = f"{garanti_ay} ay"
        bugun = datetime.now().date()
        if garanti_bitis > bugun:
            kalan_gun = (garanti_bitis - bugun).days
            kalan_ay = kalan_gun // MagicNumbers.GUN_AY_CARPI
            kalan_gun_kalan = kalan_gun % MagicNumbers.GUN_AY_CARPI
            kalan_garanti = f"{kalan_ay} ay {kalan_gun_kalan} gün" if kalan_ay > 0 else f"{kalan_gun} gün"
        else:
            kalan_garanti = "Garanti süresi dolmuş"
        return (garanti_suresi, garanti_bitis, kalan_garanti)

    @staticmethod
    def compute_beklenen_tamamlanma_tarihi(record, default_today):
        """Belge tarihinden iş günü sonrasını hesaplar."""
        baslangic_tarihi = record.tarih or default_today
        is_gunu_sayisi = 0
        hedef_tarih = baslangic_tarihi
        while is_gunu_sayisi < MagicNumbers.ONARIM_IS_GUNU:
            hedef_tarih += timedelta(days=1)
            if hedef_tarih.weekday() < MagicNumbers.HAFTA_SONU_BASLANGIC:
                is_gunu_sayisi += 1
        return hedef_tarih

    @staticmethod
    def compute_kalan_is_gunu(record):
        """(kalan_is_gunu, onarim_durumu_update) döner. onarim_durumu_update None veya yeni değer."""
        if not record.beklenen_tamamlanma_tarihi:
            return (0, None)
        bugun = datetime.now().date()
        hedef_tarih = record.beklenen_tamamlanma_tarihi
        if hedef_tarih <= bugun:
            onarim_durumu = 'gecikti' if record.onarim_durumu != 'tamamlandi' else None
            return (0, onarim_durumu)
        kalan_gun = 0
        current_date = bugun
        while current_date < hedef_tarih:
            current_date += timedelta(days=1)
            if current_date.weekday() < MagicNumbers.HAFTA_SONU_BASLANGIC:
                kalan_gun += 1
        onarim_durumu = None
        if kalan_gun <= MagicNumbers.UYARI_IS_GUNU and record.onarim_durumu == 'beklemede':
            onarim_durumu = 'devam_ediyor'
        return (kalan_gun, onarim_durumu)

    @staticmethod
    def compute_kalan_sure_gosterimi(record):
        """Kalan süre gösterim metni."""
        if record.state == ArizaStates.TESLIM_EDILDI:
            return ''
        if record.state == ArizaStates.TAMAMLANDI and record.ariza_tipi == ArizaTipi.MAGAZA:
            return ''
        if record.state == ArizaStates.ONARIM_DISI and record.ariza_tipi == ArizaTipi.MAGAZA:
            return ''
        if record.kalan_is_gunu == 0:
            return "Süre Aşıldı"
        return f"{record.kalan_is_gunu} gün"

    @staticmethod
    def compute_kalan_sure_gosterimi_visible(record):
        """Kalan süre gösterimi görünür mü?"""
        if record.state == ArizaStates.TESLIM_EDILDI:
            return False
        if record.state == ArizaStates.TAMAMLANDI and record.ariza_tipi == ArizaTipi.MAGAZA:
            return False
        if record.state == ArizaStates.ONARIM_DISI and record.ariza_tipi == ArizaTipi.MAGAZA:
            return False
        return True

    @staticmethod
    def compute_state_manager(record):
        """Yönetici görünümü için state_manager değeri."""
        mapping = {
            ArizaStates.DRAFT: StateManager.DRAFT,
            ArizaStates.PERSONEL_ONAY: StateManager.ONAYLANDI,
            ArizaStates.KABUL_EDILDI: StateManager.ONAYLANDI,
            ArizaStates.TEKNIK_ONARIM: StateManager.ONARIMDA,
            ArizaStates.ONAYLANDI: StateManager.ONARIM_TAMAMLANDI,
            ArizaStates.YONETICI_TAMAMLANDI: StateManager.ONARIM_TAMAMLANDI,
            ArizaStates.TAMAMLANDI: StateManager.TAMAMLANDI,
            ArizaStates.TESLIM_EDILDI: StateManager.TESLIM_EDILDI,
            ArizaStates.ONARIM_DISI: StateManager.IPTAL,
            ArizaStates.KILITLI: StateManager.KILITLI,
            ArizaStates.IPTAL: StateManager.IPTAL,
        }
        return mapping.get(record.state, StateManager.DRAFT)

    @staticmethod
    def compute_onarim_ucreti_tl(record):
        """Onarım ücreti TL formatı."""
        if record.onarim_ucreti and record.currency_id:
            return f"{record.onarim_ucreti:,.2f} {record.currency_id.symbol}"
        return ""

    @staticmethod
    def compute_user_permissions(record, current_user):
        """(can_approve, can_start_repair) tuple döner."""
        can_approve = current_user.has_group('ariza_onarim.group_ariza_manager')
        if record.teknik_servis == TeknikServis.MAGAZA:
            return (True, True)
        can_start_repair = current_user.has_group('ariza_onarim.group_ariza_manager')
        return (can_approve, can_start_repair)

    @staticmethod
    def compute_musteri_gosterim(record):
        """Müşteri/mağaza gösterim metni."""
        if record.ariza_tipi == ArizaTipi.MUSTERI and record.partner_id:
            return record.partner_id.name
        if record.ariza_tipi == ArizaTipi.MAGAZA:
            if record.analitik_hesap_id and record.analitik_hesap_id.name:
                magaza_adi = record.analitik_hesap_id.name
                if magaza_adi.startswith("Perakende - "):
                    magaza_adi = magaza_adi[MagicNumbers.PERAKENDE_PREFIX_LENGTH:]
                return f"{magaza_adi} Mağaza Ürünü"
            return "Mağaza Ürünü"
        return ''

    @staticmethod
    def compute_magaza_urun_adi(record):
        """Mağaza ürün adı [kodu] ad formatı."""
        if not record.magaza_urun_id:
            return ''
        urun_adi = record.magaza_urun_id.name or ''
        urun_kodu = record.magaza_urun_id.default_code or ''
        if urun_kodu:
            return f"[{urun_kodu}] {urun_adi}"
        return urun_adi

    @staticmethod
    def compute_urun_gosterimi(record):
        """Birleşik ürün gösterimi."""
        if record.ariza_tipi == ArizaTipi.MAGAZA:
            return record.magaza_urun_adi or ''
        return record.urun or ''

    @staticmethod
    def compute_is_manager(env):
        """Süper yönetici hariç, normal yönetici grubunda mı?"""
        if env.user.has_group('ariza_onarim.group_ariza_super_manager'):
            return False
        if env.user.has_group('ariza_onarim.group_ariza_manager'):
            return True
        return False

    @staticmethod
    def compute_teslim_al_visible(record):
        """Mağaza ürünü + yönetici tamamlandı durumunda True"""
        from ..ariza_constants import ArizaStates, ArizaTipi
        return (
            record.ariza_tipi == ArizaTipi.MAGAZA
            and record.state == ArizaStates.YONETICI_TAMAMLANDI
        )

    @staticmethod
    def compute_analitik_hesap_bilgileri(record):
        """(adres, telefon, email) tuple döner."""
        if not record.analitik_hesap_id:
            return ('', '', '')
        acc = record.analitik_hesap_id
        return (
            acc.adres or acc.name or '',
            acc.telefon or '',
            acc.email or '',
        )

    @staticmethod
    def clean_magaza_adi(magaza_adi):
        """Mağaza adından 'Perakende - ' önekini temizle"""
        if magaza_adi and magaza_adi.startswith("Perakende - "):
            return magaza_adi[MagicNumbers.PERAKENDE_PREFIX_LENGTH:]
        return magaza_adi

    @staticmethod
    def compute_teknik_servis_adres(record):
        """Teknik servis adresini döner (lazy import - circular önleme)"""
        from . import teknik_servis_helper
        return teknik_servis_helper.TeknikServisHelper.get_adres(
            record.teknik_servis,
            tedarikci_id=record.tedarikci_id,
            tedarikci_adresi=record.tedarikci_adresi,
        )

    @staticmethod
    def compute_teknik_servis_telefon(record):
        """Teknik servis telefonunu döner (lazy import - circular önleme)"""
        from . import teknik_servis_helper
        return teknik_servis_helper.TeknikServisHelper.get_telefon(
            record.teknik_servis,
            tedarikci_id=record.tedarikci_id,
        )

    @staticmethod
    def compute_musteri_telefon(record):
        """Müşteri telefonunu döner (phone veya mobile)"""
        if not record.partner_id:
            return ''
        return record.partner_id.phone or record.partner_id.mobile or ''

    @staticmethod
    def get_musteri_faturalari(env, partner_id):
        """Müşteriye ait gelen faturaları döner (posted, stok ürünleri)"""
        if not partner_id:
            return env['account.move'].browse()
        return env['account.move'].search([
            ('partner_id', '=', partner_id.id),
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('invoice_line_ids.product_id.type', '=', 'product')
        ])
