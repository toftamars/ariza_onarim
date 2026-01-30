# -*- coding: utf-8 -*-
"""
Arıza Kayıt - Computed Fields Mixin
Tüm computed field metodlarını içerir (@api.depends)
"""

import logging
from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from .ariza_constants import ArizaTipi, ArizaStates, TeknikServis

_logger = logging.getLogger(__name__)


class ArizaKayitCompute(models.AbstractModel):
    """
    Arıza Kayıt için computed field metodlarını içeren mixin.

    Bu sınıf AbstractModel olarak tanımlanmıştır ve
    ana ArizaKayit modelinde inherit edilir.
    """
    _name = 'ariza.kayit.compute.mixin'
    _description = 'Ariza Kayit Computed Fields Mixin'

    @api.depends()
    def _compute_is_manager(self):
        """Kullanıcının yönetici olup olmadığını kontrol eder"""
        for record in self:
            # Arıza Yöneticisi grubuna üyeliği kontrol et
            is_manager = self.env.user.has_group('ariza_onarim.group_ariza_yonetici')

            # Admin kullanıcı her zaman yönetici
            if self.env.user.id == 2:  # Odoo Admin user ID
                is_manager = True

            record.is_manager = is_manager

    @api.depends('ariza_tipi', 'state')
    def _compute_teslim_al_visible(self):
        """Teslim Al butonunun görünürlüğünü kontrol eder"""
        for record in self:
            # Mağaza ürünü ve Tamir Aşamasında ise görünür
            if record.ariza_tipi == ArizaTipi.MAGAZA and record.state == ArizaStates.TAMIR:
                record.teslim_al_visible = True
            else:
                record.teslim_al_visible = False

    @api.depends('state')
    def _compute_state_manager(self):
        """State manager bilgisini hesaplar"""
        for record in self:
            # StateManager'dan label bilgisini al
            from .ariza_constants import StateManager
            state_info = StateManager.get_state_info(record.state)
            record.state_display = state_info.get('label', record.state)

    @api.depends('onarim_ucreti', 'currency_id')
    def _compute_onarim_ucreti_tl(self):
        """Onarım ücretini TL cinsinden hesaplar"""
        for record in self:
            if record.currency_id and record.onarim_ucreti:
                # Para birimi TRY değilse çevir
                if record.currency_id.name != 'TRY':
                    try_currency = self.env['res.currency'].search([('name', '=', 'TRY')], limit=1)
                    if try_currency:
                        record.onarim_ucreti_tl = record.currency_id._convert(
                            record.onarim_ucreti,
                            try_currency,
                            record.company_id or self.env.company,
                            fields.Date.today()
                        )
                    else:
                        record.onarim_ucreti_tl = record.onarim_ucreti
                else:
                    record.onarim_ucreti_tl = record.onarim_ucreti
            else:
                record.onarim_ucreti_tl = 0.0

    @api.depends('sorumlu_id', 'teknik_servis')
    def _compute_user_permissions(self):
        """Kullanıcı izinlerini hesaplar"""
        for record in self:
            current_user = self.env.user

            # Yönetici her zaman yetkili
            if current_user.has_group('ariza_onarim.group_ariza_yonetici'):
                record.can_edit = True
                record.can_approve = True
                record.can_start = True
            else:
                # Sorumlu kullanıcı düzenleyebilir
                record.can_edit = (record.sorumlu_id.id == current_user.id)

                # Teknik servis sorumlusu onaylayabilir
                record.can_approve = (record.teknik_servis and
                                     current_user.has_group('ariza_onarim.group_teknik_servis'))

                # Başlatma yetkisi
                record.can_start = record.can_edit

    @api.depends('invoice_line_id')
    def _compute_fatura_tarihi(self):
        """Fatura tarihini hesaplar"""
        for record in self:
            if record.invoice_line_id and record.invoice_line_id.move_id:
                record.fatura_tarihi = record.invoice_line_id.move_id.invoice_date
            else:
                record.fatura_tarihi = False

    @api.depends('invoice_line_id', 'fatura_tarihi')
    def _compute_garanti_suresi(self):
        """Garanti süresini hesaplar (aylık olarak)"""
        for record in self:
            if record.invoice_line_id and record.fatura_tarihi:
                # Ürünün garanti süresini al (varsayılan 24 ay)
                product = record.invoice_line_id.product_id
                garanti_ay = getattr(product, 'garanti_suresi', 24)

                # Garanti bitiş tarihini hesapla
                garanti_bitis = record.fatura_tarihi + relativedelta(months=garanti_ay)

                # Kalan ay sayısını hesapla
                bugun = fields.Date.today()
                if bugun < garanti_bitis:
                    kalan_gun = (garanti_bitis - bugun).days
                    record.garanti_suresi = kalan_gun / 30.0  # Aylık olarak
                else:
                    record.garanti_suresi = 0.0
            else:
                record.garanti_suresi = 0.0

    @api.depends('tarih')
    def _compute_beklenen_tamamlanma_tarihi(self):
        """Beklenen tamamlanma tarihini hesaplar (kayıt tarihinden 20 iş günü sonra)"""
        for record in self:
            if record.tarih:
                # 20 iş günü sonrasını hesapla (hafta sonları hariç)
                beklenen_tarih = record.tarih
                is_gunu = 0
                while is_gunu < 20:
                    beklenen_tarih += timedelta(days=1)
                    # Hafta içi günleri say (0=Pazartesi, 6=Pazar)
                    if beklenen_tarih.weekday() < 5:  # Pazartesi-Cuma
                        is_gunu += 1

                record.beklenen_tamamlanma_tarihi = beklenen_tarih
            else:
                record.beklenen_tamamlanma_tarihi = False

    @api.depends('beklenen_tamamlanma_tarihi')
    def _compute_kalan_is_gunu(self):
        """Kalan iş günü sayısını hesaplar"""
        for record in self:
            if record.beklenen_tamamlanma_tarihi:
                bugun = fields.Date.today()
                if bugun <= record.beklenen_tamamlanma_tarihi:
                    # Kalan iş günlerini hesapla
                    kalan_gun = 0
                    tarih = bugun
                    while tarih < record.beklenen_tamamlanma_tarihi:
                        tarih += timedelta(days=1)
                        if tarih.weekday() < 5:  # Hafta içi
                            kalan_gun += 1
                    record.kalan_is_gunu = kalan_gun
                else:
                    # Süre geçmiş
                    record.kalan_is_gunu = 0
            else:
                record.kalan_is_gunu = 0

    @api.depends('kalan_is_gunu', 'state', 'ariza_tipi')
    def _compute_kalan_sure_gosterimi(self):
        """Kalan süre gösterimini hesaplar (renk kodlu)"""
        for record in self:
            if record.state in [ArizaStates.TESLIM_EDILDI, ArizaStates.TAMAMLANDI]:
                # Tamamlanmış kayıtlar için gösterme
                record.kalan_sure_gosterimi = ''
            elif record.kalan_is_gunu >= 15:
                record.kalan_sure_gosterimi = f'🟢 {record.kalan_is_gunu} gün'
            elif record.kalan_is_gunu >= 8:
                record.kalan_sure_gosterimi = f'🟡 {record.kalan_is_gunu} gün'
            elif record.kalan_is_gunu > 0:
                record.kalan_sure_gosterimi = f'🔴 {record.kalan_is_gunu} gün'
            else:
                record.kalan_sure_gosterimi = '⏰ Süresi Geçti'

    @api.depends('state', 'ariza_tipi')
    def _compute_kalan_sure_gosterimi_visible(self):
        """Kalan süre gösteriminin görünür olup olmadığını kontrol eder"""
        for record in self:
            # Yeşil kayıtlarda (Teslim Edildi/Tamamlandı) gizle
            if record.state in [ArizaStates.TESLIM_EDILDI, ArizaStates.TAMAMLANDI]:
                record.kalan_sure_gosterimi_visible = False
            else:
                record.kalan_sure_gosterimi_visible = True

    @api.depends('analitik_hesap_id', 'analitik_hesap_id.partner_id',
                 'analitik_hesap_id.adres', 'analitik_hesap_id.telefon',
                 'analitik_hesap_id.email')
    def _compute_analitik_hesap_bilgileri(self):
        """Analitik hesap bilgilerini computed field'lara kopyalar"""
        for record in self:
            if record.analitik_hesap_id:
                record.magaza_partner_id = record.analitik_hesap_id.partner_id
                record.magaza_adres = record.analitik_hesap_id.adres
                record.magaza_telefon = record.analitik_hesap_id.telefon
                record.magaza_email = record.analitik_hesap_id.email
            else:
                record.magaza_partner_id = False
                record.magaza_adres = False
                record.magaza_telefon = False
                record.magaza_email = False

    @api.depends('partner_id')
    def _get_musteri_faturalari(self):
        """Müşterinin faturalarını getirir"""
        for record in self:
            if record.partner_id:
                faturalar = self.env['account.move'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted')
                ])
                record.musteri_fatura_ids = faturalar
            else:
                record.musteri_fatura_ids = False

    @api.depends('teknik_servis', 'tedarikci_id', 'tedarikci_adresi')
    def _compute_teknik_servis_adres(self):
        """Teknik servis adresini hesaplar"""
        from .ariza_helpers import text_utils

        for record in self:
            if record.tedarikci_adresi:
                # Elle girilmiş adres varsa onu kullan
                record.teknik_servis_adres = record.tedarikci_adresi
            elif record.teknik_servis == TeknikServis.DTL_BEYOGLU:
                record.teknik_servis_adres = 'Şahkulu, Nakkaş Çk. No:1 D:1, 34420 Beyoğlu/İstanbul'
            elif record.teknik_servis in [TeknikServis.ZUHAL_ARIZA_DEPO, TeknikServis.ZUHAL_NEFESLI]:
                record.teknik_servis_adres = 'Halkalı Merkez, 34303 Küçükçekmece/İstanbul'
            elif record.teknik_servis == TeknikServis.TEDARIKCI and record.tedarikci_id:
                # Tedarikçi adresini oluştur
                adres_parcalari = []
                if record.tedarikci_id.street:
                    adres_parcalari.append(record.tedarikci_id.street)
                if record.tedarikci_id.street2:
                    adres_parcalari.append(record.tedarikci_id.street2)
                if record.tedarikci_id.city:
                    adres_parcalari.append(record.tedarikci_id.city)
                if record.tedarikci_id.state_id:
                    adres_parcalari.append(record.tedarikci_id.state_id.name)
                if record.tedarikci_id.zip:
                    adres_parcalari.append(record.tedarikci_id.zip)
                if record.tedarikci_id.country_id:
                    adres_parcalari.append(record.tedarikci_id.country_id.name)

                record.teknik_servis_adres = ', '.join(adres_parcalari) if adres_parcalari else ''
            else:
                record.teknik_servis_adres = ''

    @api.depends('teknik_servis', 'tedarikci_id')
    def _compute_teknik_servis_telefon(self):
        """Teknik servis telefonunu hesaplar"""
        for record in self:
            if record.teknik_servis == TeknikServis.TEDARIKCI and record.tedarikci_id:
                record.teknik_servis_telefon = record.tedarikci_id.phone or record.tedarikci_id.mobile or ''
            else:
                # Diğer teknik servisler için default telefonlar (hard-coded)
                record.teknik_servis_telefon = ''

    @api.depends('partner_id')
    def _compute_musteri_telefon(self):
        """Müşteri telefonunu hesaplar"""
        for rec in self:
            rec.musteri_telefon = rec.partner_id.phone or rec.partner_id.mobile or ''

    @api.depends('ariza_tipi', 'partner_id', 'analitik_hesap_id')
    def _compute_musteri_gosterim(self):
        """List görünümünde müşteri bilgisini gösterir"""
        from .ariza_helpers import text_utils

        for rec in self:
            if rec.ariza_tipi == ArizaTipi.MUSTERI and rec.partner_id:
                rec.musteri_gosterim = rec.partner_id.name
            elif rec.ariza_tipi == ArizaTipi.MAGAZA:
                # Mağaza ürünü için analitik hesap adından mağaza adını al
                if rec.analitik_hesap_id and rec.analitik_hesap_id.name:
                    magaza_adi = text_utils.TextUtils.clean_perakende_prefix(rec.analitik_hesap_id.name)
                    rec.musteri_gosterim = f"{magaza_adi} Mağaza Ürünü"
                else:
                    rec.musteri_gosterim = "Mağaza Ürünü"
            else:
                rec.musteri_gosterim = ''

    @api.depends('magaza_urun_id')
    def _compute_magaza_urun_adi(self):
        """Mağaza ürünü için ürün adını hesapla"""
        for rec in self:
            if rec.magaza_urun_id:
                rec.magaza_urun_adi = rec.magaza_urun_id.display_name
            else:
                rec.magaza_urun_adi = ''

    @api.depends('urun', 'magaza_urun_adi', 'ariza_tipi')
    def _compute_urun_gosterimi(self):
        """
        List görünümünde ürün bilgisini gösterir.
        Müşteri ürünü ise 'urun' field'ı, mağaza ürünü ise 'magaza_urun_adi' gösterilir.
        """
        for rec in self:
            if rec.ariza_tipi == ArizaTipi.MUSTERI:
                rec.urun_gosterimi = rec.urun or ''
            elif rec.ariza_tipi == ArizaTipi.MAGAZA:
                rec.urun_gosterimi = rec.magaza_urun_adi or ''
            else:
                rec.urun_gosterimi = ''
