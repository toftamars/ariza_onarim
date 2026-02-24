# -*- coding: utf-8 -*-
"""
Arıza Onchange Helper - Onchange mantığı
"""

import logging
from odoo import _
from odoo.exceptions import UserError

from ..ariza_constants import ArizaTipi, IslemTipi, TeknikServis
from . import hedef_konum_helper
from . import location_helper
from . import teknik_servis_helper

_logger = logging.getLogger(__name__)

# DTL teslim adresi sabiti
DTL_TESLIM_ADRESI = 'MAHMUT ŞEVKET PAŞA MAH. ŞAHİNKAYA SOK NO 31 OKMEYDANI'


class ArizaOnchangeHelper:
    """Onchange işlemleri"""

    @staticmethod
    def onchange_ariza_tipi(record):
        """ariza_tipi değişince alanları güncelle"""
        if record.ariza_tipi == ArizaTipi.MUSTERI:
            record.partner_id = False
            record.urun = False
            record.model = False
            record.magaza_urun_id = False
            record.teslim_magazasi_id = False
            record.teslim_adresi = False
            record.transfer_id = False
            record._update_hedef_konum()
        elif record.ariza_tipi == ArizaTipi.MAGAZA:
            record.partner_id = False
            record.urun = False
            record.model = False
            record.magaza_urun_id = False
            record.teslim_magazasi_id = record.env.user.employee_id.magaza_id
            if record.teslim_magazasi_id and record.teslim_magazasi_id.name in [TeknikServis.DTL_OKMEYDANI, TeknikServis.DTL_BEYOGLU]:
                record.teslim_adresi = DTL_TESLIM_ADRESI
            if record.analitik_hesap_id:
                konum = location_helper.LocationHelper.get_kaynak_konum_for_analitik(
                    record.env, record.analitik_hesap_id
                )
                if konum:
                    record.kaynak_konum_id = konum
                    _logger.info(f"Kaynak konum belirlendi: {konum.name}")
                else:
                    _logger.warning(
                        f"Konum kodu bulunamadı - Analitik Hesap: {record.analitik_hesap_id.name} "
                        f"(ID: {record.analitik_hesap_id.id}). Warehouse atanmış mı kontrol edin."
                    )
            if record.ariza_tipi == ArizaTipi.MAGAZA:
                ArizaOnchangeHelper.onchange_magaza_konumlar(record)
        elif record.ariza_tipi == 'teknik':
            record.partner_id = False
            record.urun = False
            record.model = False
            record.magaza_urun_id = False
            record.teslim_magazasi_id = False
            record.teslim_adresi = False

    @staticmethod
    def onchange_teknik_servis(record):
        """teknik_servis değişince - warning dönebilir"""
        if record.ariza_tipi == ArizaTipi.MAGAZA and record.teknik_servis == TeknikServis.MAGAZA:
            record.teknik_servis = False
            return {
                'warning': {
                    'title': 'Uyarı',
                    'message': 'Arıza Tipi Mağaza Ürünü seçildiğinde Teknik Servis olarak MAĞAZA seçilemez!'
                }
            }
        if record.teknik_servis not in [TeknikServis.MAGAZA, TeknikServis.TEDARIKCI] and record.islem_tipi not in [IslemTipi.ARIZA_KABUL]:
            record.islem_tipi = IslemTipi.ARIZA_KABUL
        if record.ariza_tipi == ArizaTipi.MAGAZA and record.analitik_hesap_id:
            konum = location_helper.LocationHelper.get_kaynak_konum_for_analitik(
                record.env, record.analitik_hesap_id
            )
            if konum:
                record.kaynak_konum_id = konum
                _logger.info(f"Kaynak konum belirlendi: {konum.name}")
            else:
                _logger.warning(
                    f"Konum kodu bulunamadı - Analitik Hesap: {record.analitik_hesap_id.name} "
                    f"(ID: {record.analitik_hesap_id.id}). Warehouse atanmış mı kontrol edin."
                )
        record.tedarikci_adresi = teknik_servis_helper.TeknikServisHelper.get_adres(
            record.teknik_servis,
            tedarikci_id=record.tedarikci_id,
            tedarikci_adresi=record.tedarikci_adresi,
        )
        if record.ariza_tipi == ArizaTipi.MAGAZA:
            ArizaOnchangeHelper.onchange_magaza_konumlar(record)
        return None

    @staticmethod
    def onchange_analitik_hesap_id(record):
        """analitik_hesap_id değişince"""
        record.teslim_adresi = ''
        record.tedarikci_telefon = ''
        record.tedarikci_email = ''
        if record.analitik_hesap_id:
            if record.analitik_hesap_id.adres:
                record.teslim_adresi = record.analitik_hesap_id.adres
            if record.analitik_hesap_id.telefon:
                record.tedarikci_telefon = record.analitik_hesap_id.telefon
            if record.analitik_hesap_id.email:
                record.tedarikci_email = record.analitik_hesap_id.email
        if record.ariza_tipi == ArizaTipi.MAGAZA:
            ArizaOnchangeHelper.onchange_magaza_konumlar(record)

    @staticmethod
    def onchange_magaza_konumlar(record):
        """Mağaza ürünü için kaynak ve hedef konumları otomatik belirle"""
        if record.ariza_tipi != ArizaTipi.MAGAZA:
            return
        if record.analitik_hesap_id:
            konum = location_helper.LocationHelper.get_kaynak_konum_for_analitik(
                record.env, record.analitik_hesap_id
            )
            if konum:
                record.kaynak_konum_id = konum
        if record.teknik_servis:
            hedef_konum_helper.HedefKonumHelper.update_hedef_konum(record)

    @staticmethod
    def onchange_invoice_line_id(record):
        """invoice_line_id değişince - ürün/marka/tedarikçi"""
        if not record.invoice_line_id or not record.invoice_line_id.product_id:
            return
        product = record.invoice_line_id.product_id
        record.urun = product.name
        record.model = product.default_code or ''
        if hasattr(product, 'brand_id') and product.brand_id:
            record.marka_id = product.brand_id.id
            if record.marka_id:
                marka = record.env['product.brand'].browse(record.marka_id)
                if marka and marka.partner_id:
                    record.tedarikci_id = marka.partner_id.id
                    ArizaOnchangeHelper.onchange_tedarikci(record)
        else:
            record.marka_id = False
            record.tedarikci_id = False
            record.tedarikci_adresi = False
            record.tedarikci_telefon = False
            record.tedarikci_email = False

    @staticmethod
    def onchange_partner_id(record):
        if not record.partner_id:
            record.invoice_line_id = False
            record.siparis_yok = False
            record.urun = False
            record.model = False

    @staticmethod
    def onchange_marka_id(record):
        if record.marka_id:
            if record.marka_id.partner_id:
                record.tedarikci_id = record.marka_id.partner_id.id
                ArizaOnchangeHelper.onchange_tedarikci(record)
        else:
            record.tedarikci_id = False
            record.tedarikci_adresi = False
            record.tedarikci_telefon = False
            record.tedarikci_email = False
            record.marka_urunleri_ids = False
            record.magaza_urun_id = False

    @staticmethod
    def onchange_tedarikci(record):
        """tedarikci_id değişince - UserError raise edebilir"""
        if not record.tedarikci_id:
            return
        record.tedarikci_adresi = teknik_servis_helper.TeknikServisHelper.get_adres(
            record.teknik_servis,
            tedarikci_id=record.tedarikci_id,
            tedarikci_adresi=None,
        )
        record.tedarikci_telefon = record.tedarikci_id.phone
        record.tedarikci_email = record.tedarikci_id.email
        delivery_contact = record.tedarikci_id.child_ids.filtered(lambda c: c.type == 'delivery')
        record.contact_id = delivery_contact[0].id if delivery_contact else record.tedarikci_id.id
        if record.teknik_servis == TeknikServis.TEDARIKCI:
            if not record.tedarikci_id.property_stock_supplier:
                raise UserError(_('Seçilen tedarikçinin stok konumu tanımlı değil! Lütfen tedarikçi kartında "Satıcı Konumu" alanını doldurun.'))
            record.hedef_konum_id = record.tedarikci_id.property_stock_supplier

    @staticmethod
    def onchange_islem_tipi(record):
        if record.islem_tipi != IslemTipi.ARIZA_KABUL:
            record.garanti_kapsaminda_mi = False

    @staticmethod
    def onchange_ariza_tipi_teknik(record):
        if record.ariza_tipi == 'teknik' and record.analitik_hesap_id:
            if hasattr(record.analitik_hesap_id, 'konum_id') and record.analitik_hesap_id.konum_id:
                record.kaynak_konum_id = record.analitik_hesap_id.konum_id
            dtl_konum = location_helper.LocationHelper.get_dtl_stok_location(
                record.env, record.company_id.id or record.env.company.id
            )
            if dtl_konum:
                record.hedef_konum_id = dtl_konum

    @staticmethod
    def onchange_ariza_kabul_id(record):
        if record.ariza_kabul_id:
            fields_to_copy = [
                'partner_id', 'analitik_hesap_id', 'kaynak_konum_id',
                'hedef_konum_id', 'tedarikci_id', 'marka_id',
                'tedarikci_adresi', 'tedarikci_telefon', 'tedarikci_email',
                'urun', 'model', 'fatura_tarihi', 'notlar',
                'onarim_ucreti', 'yapilan_islemler', 'ariza_tanimi',
                'garanti_suresi', 'garanti_bitis_tarihi', 'kalan_garanti',
                'transfer_metodu', 'magaza_urun_id', 'marka_urunleri_ids',
                'teknik_servis', 'onarim_bilgisi', 'ucret_bilgisi',
                'garanti_kapsaminda_mi', 'ariza_tipi', 'invoice_line_id',
                'siparis_yok'
            ]
            for field in fields_to_copy:
                setattr(record, field, getattr(record.ariza_kabul_id, field, False))

    @staticmethod
    def onchange_magaza_urun_id(record):
        if record.magaza_urun_id:
            record.urun = record.magaza_urun_id.name or ''
            record.model = record.magaza_urun_id.default_code or ''
            if hasattr(record.magaza_urun_id, 'brand_id') and record.magaza_urun_id.brand_id:
                record.marka_id = record.magaza_urun_id.brand_id.id
                if record.marka_id:
                    marka = record.env['product.brand'].browse(record.marka_id)
                    if marka and marka.partner_id:
                        record.tedarikci_id = marka.partner_id.id
                        ArizaOnchangeHelper.onchange_tedarikci(record)
            else:
                record.marka_id = False
                record.tedarikci_id = False
                record.tedarikci_adresi = False
                record.tedarikci_telefon = False
                record.tedarikci_email = False

    @staticmethod
    def onchange_teslim_magazasi(record):
        if record.teslim_magazasi_id and record.teslim_magazasi_id.name in [TeknikServis.DTL_OKMEYDANI, TeknikServis.DTL_BEYOGLU]:
            record.teslim_adresi = DTL_TESLIM_ADRESI
        else:
            record.teslim_adresi = False

    @staticmethod
    def onchange_sorumlu_id(record):
        if record.sorumlu_id and record.sorumlu_id.employee_id and record.sorumlu_id.employee_id.magaza_id:
            record.analitik_hesap_id = record.sorumlu_id.employee_id.magaza_id.id

    @staticmethod
    def onchange_fatura_kalem_id(record):
        if record.fatura_kalem_id:
            record.urun = record.fatura_kalem_id.product_id.name
            record.model = record.fatura_kalem_id.product_id.default_code
            if record.fatura_kalem_id.product_id.brand_id:
                record.marka_id = record.fatura_kalem_id.product_id.brand_id.id
            else:
                record.marka_id = False
