# -*- coding: utf-8 -*-
"""
Arıza Kayıt Modeli - Ana model dosyası
"""

# Standard library imports
import logging
import os

# Third-party imports
from odoo import models, fields, api, _

# Local imports
from .ariza_constants import (
    ArizaStates,
    StateManager,
    TeknikServis,
    ArizaTipi,
    IslemTipi,
    TransferMetodu,
    GarantiKapsam,
    MagicNumbers,
    SMSTemplates,
)
from .ariza_helpers import (
    location_helper,
    partner_helper,
    sequence_helper,
    sms_helper,
    hedef_konum_helper,
    ariza_transfer_service,
    ariza_state_service,
    ariza_computed_helper,
    ariza_teslim_al_service,
    ariza_cron_service,
    ariza_config_helper,
    ariza_create_service,
    ariza_search_helper,
    ariza_onchange_helper,
    ariza_print_service,
)

_logger = logging.getLogger(__name__)


# NOTE: AccountAnalyticAccount model moved to account_analytic_account.py
# for better modularity and separation of concerns.


class ArizaKayit(models.Model):
    _name = 'ariza.kayit'
    _description = 'Arıza Kayıtları'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Arıza No',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    transfer_id = fields.Many2one('stock.picking', string='Transfer', readonly=True)
    islem_tipi = fields.Selection(
        IslemTipi.SELECTION,
        string='İşlem Tipi',
        required=True,
        tracking=True,
        default=IslemTipi.ARIZA_KABUL,
        readonly=True
    )
    

    

    ariza_tipi = fields.Selection(
        ArizaTipi.SELECTION,
        string='Arıza Tipi',
        required=True,
        tracking=True
    )
    teknik_servis = fields.Selection(
        TeknikServis.SELECTION,
        string='Teknik Servis',
        required=True,
        tracking=True
    )
    transfer_metodu = fields.Selection(
        TransferMetodu.SELECTION,
        string='Transfer Metodu',
        tracking=True,
        default=TransferMetodu.ARAC
    )
    partner_id = fields.Many2one('res.partner', string='Müşteri', tracking=True)
    analitik_hesap_id = fields.Many2one('account.analytic.account', string='Analitik Hesap', tracking=True, required=True)
    kaynak_konum_id = fields.Many2one('stock.location', string='Kaynak Konum', tracking=True, domain="[('company_id', '=', company_id)]")
    hedef_konum_id = fields.Many2one('stock.location', string='Hedef Konum', tracking=True, domain="[('company_id', '=', company_id)]")
    hedef_konum_otomatik = fields.Boolean(
        string='Hedef Konum Otomatik',
        compute='_compute_hedef_konum_otomatik',
        help='Otomatik atanan hedef konumlar değiştirilemez.'
    )
    teknik_servis_location_id = fields.Many2one('stock.location', string='Teknik Servis Konumu', tracking=True, domain="[('company_id', '=', company_id)]")
    tedarikci_id = fields.Many2one('res.partner', string='Tedarikçi', tracking=True)
    marka_id = fields.Many2one('product.brand', string='Marka', tracking=True)
    marka_manu = fields.Char(string='Marka (Manuel)', tracking=True)
    tedarikci_adresi = fields.Text(string='Teslim Adresi', tracking=True)
    tedarikci_telefon = fields.Char(string='Tedarikçi Telefon', tracking=True)
    tedarikci_email = fields.Char(string='Tedarikçi E-posta', tracking=True)
    
    # Analitik hesap bilgileri için computed field'lar (form view'da gösterim için)
    analitik_hesap_adres = fields.Text(
        string='Analitik Hesap Adresi',
        compute='_compute_analitik_hesap_bilgileri',
        store=False
    )
    analitik_hesap_telefon = fields.Char(
        string='Analitik Hesap Telefon',
        compute='_compute_analitik_hesap_bilgileri',
        store=False
    )
    analitik_hesap_email = fields.Char(
        string='Analitik Hesap E-posta',
        compute='_compute_analitik_hesap_bilgileri',
        store=False
    )
    sorumlu_id = fields.Many2one('res.users', string='Sorumlu', default=lambda self: self.env.user, tracking=True)
    tarih = fields.Date(string='Tarih', default=fields.Date.context_today, tracking=True)
    state = fields.Selection(
        ArizaStates.SELECTION,
        string='Durum',
        default=ArizaStates.DRAFT,
        tracking=True
    )
    siparis_yok = fields.Boolean(string='Sipariş Yok', default=False)
    invoice_line_id = fields.Many2one(
        'account.move.line',
        string='Fatura Kalemi',
        domain=(
            "[('move_id.partner_id', '=', partner_id), "
            "('product_id.type', '=', 'product'), "
            "('exclude_from_invoice_tab', '=', False), "
            "('quantity', '>', 0)]"
        ),
        tracking=True
    )
    fatura_tarihi = fields.Date(string='Fatura Tarihi', compute='_compute_fatura_tarihi', store=True)
    urun = fields.Char(string='Ürün', required=False)
    model = fields.Char(string='Model', required=False)
    garanti_suresi = fields.Char(string='Garanti Süresi', compute='_compute_garanti_suresi', store=True, tracking=True)
    garanti_bitis_tarihi = fields.Date(string='Garanti Bitiş Tarihi', compute='_compute_garanti_suresi', store=True)
    kalan_garanti = fields.Char(string='Kalan Garanti', compute='_compute_garanti_suresi', store=True)
    garanti_kapsaminda_mi = fields.Selection(
        GarantiKapsam.SELECTION,
        string='Garanti Kapsamında mı?',
        tracking=True
    )
    ariza_tanimi = fields.Text(string='Arıza Tanımı', tracking=True)
    seri_no = fields.Char(string='Seri No', tracking=True)
    notlar = fields.Text(string='Notlar', required=True)
    transfer_irsaliye = fields.Char(string='Transfer İrsaliye No')
    company_id = fields.Many2one('res.company', string='Şirket', default=lambda self: self.env.company)
    onarim_ucreti = fields.Monetary(string='Onarım Ücreti', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Para Birimi', default=lambda self: self.env.company.currency_id)
    onarim_ucreti_tl = fields.Char(string='Onarım Ücreti', compute='_compute_onarim_ucreti_tl', store=True)
    yapilan_islemler = fields.Text(string='Yapılan İşlemler', tracking=True)
    marka_urunleri_ids = fields.Many2many(
        'product.product',
        string='Marka Ürünleri',
        tracking=True
    )
    ariza_kabul_id = fields.Many2one(
        'ariza.kayit',
        string='Arıza Kabul No',
        domain=f"[('islem_tipi', '=', '{IslemTipi.ARIZA_KABUL}')]",
        tracking=True
    )
    onarim_bilgisi = fields.Text(string='Onarım Bilgisi', tracking=True)
    ucret_bilgisi = fields.Char(string='Ücret Bilgisi', tracking=True)
    onarim_disi_aciklama = fields.Text(string='Onarım Dışı Açıklama', tracking=True, readonly=True)
    magaza_urun_id = fields.Many2one(
        'product.product',
        string='Ürün',
        tracking=True,
        required=False
    )
    sms_gonderildi = fields.Boolean(string='SMS Gönderildi', default=False, tracking=True)
    ilk_sms_gonderildi = fields.Boolean(string='İlk SMS Gönderildi', default=False, tracking=True)
    ikinci_sms_gonderildi = fields.Boolean(string='İkinci SMS Gönderildi', default=False, tracking=False)
    ucuncu_sms_gonderildi = fields.Boolean(string='Üçüncü SMS Gönderildi', default=False, tracking=False)
    sms_farkli_noya_gonder = fields.Boolean(
        string="SMS'i Farklı No'ya Gönder",
        default=False,
        tracking=True,
        help="İşaretlenirse tüm SMS'ler müşteri kontağı yerine aşağıdaki numaraya gönderilir."
    )
    sms_farkli_telefon = fields.Char(
        string="SMS Gönderilecek Telefon",
        tracking=True,
        help="SMS'lerin gönderileceği alternatif telefon numarası (SMS'i Farklı No'ya Gönder işaretliyse)."
    )
    teslim_magazasi_id = fields.Many2one('account.analytic.account', string='Teslim Mağazası')
    teslim_adresi = fields.Char(string='Teslim Adresi', tracking=True)
    musteri_faturalari = fields.Many2many('account.move', string='Müşteri Faturaları')
    teknik_servis_adres = fields.Char(string='Teknik Servis Adresi', compute='_compute_teknik_servis_adres', store=False)
    teknik_servis_telefon = fields.Char(string='Teknik Servis Telefonu', compute='_compute_teknik_servis_telefon', store=False)
    teslim_alan = fields.Char(string='Teslim Alan')
    teslim_alan_tc = fields.Char(string='Teslim Alan TC')
    teslim_alan_telefon = fields.Char(string='Teslim Alan Telefon')
    teslim_alan_imza = fields.Binary(string='Teslim Alan İmza')
    teslim_notu = fields.Text(string='Teslim Notu', tracking=True)
    contact_id = fields.Many2one('res.partner', string='Kontak (Teslimat Adresi)', tracking=True)
    vehicle_id = fields.Many2one('res.partner', string='Sürücü', domain="[('is_driver','=',True)]", tracking=True)
    barcode = fields.Char(string='Barkod', tracking=True, copy=False)
    
    # Onarım Süreci Takibi
    onarim_baslangic_tarihi = fields.Date(string='Onarım Başlangıç Tarihi', tracking=True)
    beklenen_tamamlanma_tarihi = fields.Date(string='Beklenen Tamamlanma Tarihi', compute='_compute_beklenen_tamamlanma_tarihi', store=True)
    kalan_is_gunu = fields.Integer(string='Kalan İş Günü', compute='_compute_kalan_is_gunu', store=True)
    kalan_sure_gosterimi = fields.Char(string='Kalan Süre Gösterimi', compute='_compute_kalan_sure_gosterimi', store=True)
    kalan_sure_gosterimi_visible = fields.Boolean(string='Kalan Süre Gösterimi Görünür', compute='_compute_kalan_sure_gosterimi_visible', store=True)
    urun_gosterimi = fields.Char(string='Ürün', compute='_compute_urun_gosterimi', store=True)
    onarim_durumu = fields.Selection([
        ('beklemede', 'Beklemede'),
        ('devam_ediyor', 'Devam Ediyor'),
        ('tamamlandi', 'Tamamlandı'),
        ('gecikti', 'Gecikti')
    ], string='Onarım Durumu', default='beklemede', tracking=True)
    hatirlatma_gonderildi = fields.Boolean(string='Hatırlatma Gönderildi', default=False, tracking=True)
    son_hatirlatma_tarihi = fields.Date(string='Son Hatırlatma Tarihi', tracking=True)
    
    # Kullanıcı bazlı yetki kontrolü
    can_approve = fields.Boolean(string='Onaylayabilir mi?', compute='_compute_user_permissions', store=False)
    can_start_repair = fields.Boolean(string='Onarımı Başlatabilir mi?', compute='_compute_user_permissions', store=False)
    
    # Yönetici için özel durum gösterimi
    state_manager = fields.Selection(
        StateManager.SELECTION,
        string='Durum (Yönetici)',
        compute='_compute_state_manager',
        store=False
    )
    
    # Transfer sayısı takibi
    transfer_sayisi = fields.Integer(string='Transfer Sayısı', default=0, tracking=True)
    musteri_telefon = fields.Char(string='Telefon', readonly=True, compute='_compute_musteri_telefon', store=False)
    musteri_gosterim = fields.Char(
        string='Müşteri',
        compute='_compute_musteri_gosterim',
        store=False,
        readonly=True
    )
    hazir_basildi = fields.Boolean(
        string='Hazır Butonuna Basıldı',
        default=False,
        tracking=True,
        help='Müşteri ürünü için Hazır butonuna basıldı mı kontrolü'
    )
    
    # Mağaza ürünü teslim al butonu için
    teslim_al_visible = fields.Boolean(
        string='Teslim Al Butonu Görünür',
        compute='_compute_teslim_al_visible',
        store=False
    )
    
    # Yönetici kontrolü için
    is_manager = fields.Boolean(
        string='Yönetici mi?',
        compute='_compute_is_manager',
        store=False
    )
    
    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None, count=False):
        """Ürün alanı için özel domain genişletmesi"""
        new_domain = ariza_search_helper.ArizaSearchHelper.expand_urun_domain(domain)
        if new_domain == domain:
            return super()._search(domain, offset=offset, limit=limit, order=order, access_rights_uid=access_rights_uid, count=count)
        return super()._search(new_domain, offset=offset, limit=limit, order=order, access_rights_uid=access_rights_uid, count=count)
    
    @api.depends()
    def _compute_is_manager(self):
        for rec in self:
            rec.is_manager = ariza_computed_helper.ArizaComputedHelper.compute_is_manager(self.env)

    @api.depends('ariza_tipi', 'state')
    def _compute_teslim_al_visible(self):
        for rec in self:
            rec.teslim_al_visible = ariza_computed_helper.ArizaComputedHelper.compute_teslim_al_visible(rec)
    
    # Mağaza ürünü için ürün adı
    magaza_urun_adi = fields.Char(string='Mağaza Ürün Adı', compute='_compute_magaza_urun_adi', store=True)

    @api.depends('state')
    def _compute_state_manager(self):
        """Yönetici için özel durum gösterimi"""
        for record in self:
            record.state_manager = ariza_computed_helper.ArizaComputedHelper.compute_state_manager(record)

    @api.depends('onarim_ucreti', 'currency_id')
    def _compute_onarim_ucreti_tl(self):
        """Onarım ücretini para birimi formatında göster"""
        for record in self:
            record.onarim_ucreti_tl = ariza_computed_helper.ArizaComputedHelper.compute_onarim_ucreti_tl(record)

    @api.depends('sorumlu_id', 'teknik_servis')
    def _compute_user_permissions(self):
        """Kullanıcının yetkilerini kontrol et"""
        for record in self:
            can_approve, can_start_repair = ariza_computed_helper.ArizaComputedHelper.compute_user_permissions(
                record, self.env.user
            )
            record.can_approve = can_approve
            record.can_start_repair = can_start_repair

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            ariza_create_service.ArizaCreateService.prepare_vals(self.env, vals)
        records = super().create(vals_list)
        ariza_create_service.ArizaCreateService.post_create(records)
        return records

    def write(self, vals):
        """Otomatik atanan hedef konum değiştirilemez."""
        if 'hedef_konum_id' in vals:
            otomatik = self.filtered(lambda r: r._hedef_konum_otomatik_mi())
            diger = self - otomatik
            if otomatik:
                super(ArizaKayit, otomatik).write(
                    {k: v for k, v in vals.items() if k != 'hedef_konum_id'}
                )
            return super(ArizaKayit, diger).write(vals) if diger else True
        return super().write(vals)

    @api.model
    def _check_onarim_deadlines(self):
        """Günlük olarak onarım süreçlerini kontrol et ve hatırlatma gönder"""
        ariza_cron_service.ArizaCronService.check_onarim_deadlines(self)

    def action_onayla_kullanici_bazli(self):
        """Kullanıcı bazlı onay sistemi - Onarım sürecini aktif hale getirir"""
        for record in self:
            ariza_state_service.ArizaStateService.onayla_kullanici_bazli(record)

    def action_onarim_baslat(self):
        """Onarım sürecini başlat - Sadece teknik ekip"""
        for record in self:
            ariza_state_service.ArizaStateService.onarim_baslat(record)

    @api.depends('invoice_line_id')
    def _compute_fatura_tarihi(self):
        for record in self:
            record.fatura_tarihi = ariza_computed_helper.ArizaComputedHelper.compute_fatura_tarihi(record)

    @api.depends('invoice_line_id', 'fatura_tarihi')
    def _compute_garanti_suresi(self):
        for record in self:
            gs, gbt, kg = ariza_computed_helper.ArizaComputedHelper.compute_garanti_suresi(record)
            record.garanti_suresi = gs
            record.garanti_bitis_tarihi = gbt
            record.kalan_garanti = kg

    @api.depends('tarih')
    def _compute_beklenen_tamamlanma_tarihi(self):
        """Belge oluşturulma tarihinden belirlenen iş günü sonrasını hesapla"""
        for record in self:
            record.beklenen_tamamlanma_tarihi = ariza_computed_helper.ArizaComputedHelper.compute_beklenen_tamamlanma_tarihi(
                record, fields.Date.today()
            )

    @api.depends('beklenen_tamamlanma_tarihi')
    def _compute_kalan_is_gunu(self):
        """Bugünden itibaren kalan iş günü sayısını hesapla - Her gün otomatik azalır"""
        for record in self:
            kalan, onarim_durumu = ariza_computed_helper.ArizaComputedHelper.compute_kalan_is_gunu(record)
            record.kalan_is_gunu = kalan
            if onarim_durumu is not None:
                record.onarim_durumu = onarim_durumu

    @api.depends('kalan_is_gunu', 'state', 'ariza_tipi')
    def _compute_kalan_sure_gosterimi(self):
        """Kalan süreye göre özel gösterim metni oluştur"""
        for record in self:
            record.kalan_sure_gosterimi = ariza_computed_helper.ArizaComputedHelper.compute_kalan_sure_gosterimi(record)

    @api.depends('state', 'ariza_tipi')
    def _compute_kalan_sure_gosterimi_visible(self):
        """Yeşil kayıtlarda kalan süre gösterimini gizle"""
        for record in self:
            record.kalan_sure_gosterimi_visible = ariza_computed_helper.ArizaComputedHelper.compute_kalan_sure_gosterimi_visible(record)

    @api.depends('ariza_tipi', 'teknik_servis', 'tedarikci_id')
    def _compute_hedef_konum_otomatik(self):
        """Hedef konum otomatik atanıyorsa True (değiştirilemez)."""
        for rec in self:
            rec.hedef_konum_otomatik = rec._hedef_konum_otomatik_mi()

    def _hedef_konum_otomatik_mi(self):
        """Mevcut ariza_tipi + teknik_servis kombinasyonu hedef konumu otomatik atıyor mu?"""
        return hedef_konum_helper.HedefKonumHelper.hedef_konum_otomatik_mi(
            self.ariza_tipi, self.teknik_servis, self.tedarikci_id
        )

    def _update_hedef_konum(self):
        """Hedef konumu günceller - HedefKonumHelper'a delegasyon"""
        hedef_konum_helper.HedefKonumHelper.update_hedef_konum(self)

    @api.onchange('ariza_tipi')
    def _onchange_ariza_tipi(self):
        ariza_onchange_helper.ArizaOnchangeHelper.onchange_ariza_tipi(self)

    @api.onchange('teknik_servis')
    def _onchange_teknik_servis(self):
        result = ariza_onchange_helper.ArizaOnchangeHelper.onchange_teknik_servis(self)
        if result:
            return result

    @api.onchange('ariza_tipi', 'analitik_hesap_id', 'teknik_servis')
    def _onchange_magaza_konumlar(self):
        ariza_onchange_helper.ArizaOnchangeHelper.onchange_magaza_konumlar(self)

    @api.onchange('analitik_hesap_id')
    def _onchange_analitik_hesap_id(self):
        ariza_onchange_helper.ArizaOnchangeHelper.onchange_analitik_hesap_id(self)

    @api.depends('analitik_hesap_id', 'analitik_hesap_id.adres', 'analitik_hesap_id.telefon', 'analitik_hesap_id.email', 'analitik_hesap_id.name')
    def _compute_analitik_hesap_bilgileri(self):
        """Analitik hesap bilgilerini computed field'lara aktar"""
        for record in self:
            adres, telefon, email = ariza_computed_helper.ArizaComputedHelper.compute_analitik_hesap_bilgileri(record)
            record.analitik_hesap_adres = adres
            record.analitik_hesap_telefon = telefon
            record.analitik_hesap_email = email

    @api.onchange('invoice_line_id')
    def _onchange_invoice_line_id(self):
        ariza_onchange_helper.ArizaOnchangeHelper.onchange_invoice_line_id(self)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        ariza_onchange_helper.ArizaOnchangeHelper.onchange_partner_id(self)

    @api.onchange('marka_id')
    def _onchange_marka_id(self):
        ariza_onchange_helper.ArizaOnchangeHelper.onchange_marka_id(self)

    @api.onchange('tedarikci_id')
    def _onchange_tedarikci(self):
        ariza_onchange_helper.ArizaOnchangeHelper.onchange_tedarikci(self)

    @api.onchange('islem_tipi')
    def _onchange_islem_tipi(self):
        ariza_onchange_helper.ArizaOnchangeHelper.onchange_islem_tipi(self)

    @api.onchange('ariza_tipi')
    def _onchange_ariza_tipi_teknik(self):
        ariza_onchange_helper.ArizaOnchangeHelper.onchange_ariza_tipi_teknik(self)

    @api.onchange('ariza_kabul_id')
    def _onchange_ariza_kabul_id(self):
        ariza_onchange_helper.ArizaOnchangeHelper.onchange_ariza_kabul_id(self)

    def _get_default_driver_id(self):
        """Default sürücü ID - ArizaConfigHelper'a delegasyon"""
        return ariza_config_helper.ArizaConfigHelper.get_default_driver_id(self.env)

    def _create_stock_transfer(self, kaynak_konum=None, hedef_konum=None, force_internal=False, delivery_type=None, transfer_tipi=None):
        """Stok transferi oluşturur - ArizaTransferService'e delegasyon"""
        return ariza_transfer_service.ArizaTransferService.create_stock_transfer(
            self, kaynak_konum, hedef_konum, transfer_tipi
        )

    def _send_sms_to_customer(self, message):
        """Müşteriye SMS gönder - SMSHelper'a delegasyon"""
        sms_helper.SMSHelper.send_sms_to_ariza_customer(self, message)
            

    # NOT: _create_delivery_order fonksiyonu kaldırıldı
    # Bu fonksiyon sale modülüne bağımlıydı ve hiçbir yerde kullanılmıyordu
    # Eğer gelecekte gerekirse, sale modülü bağımlılığı eklenmeli ve
    # demo verilere referans yerine gerçek ürün ID'si kullanılmalıdır

    def action_personel_onayla(self):
        """Personel onaylama işlemi - Hem ilk transfer hem de 2. transfer için çalışır"""
        for record in self:
            result = ariza_state_service.ArizaStateService.personel_onayla(record)
            if result is not None:
                return result
                

    def action_kabul_et(self):
        """Kabul etme işlemi - Teknik servis MAĞAZA ise tüm kullanıcılar, diğer durumlar sadece yöneticiler"""
        for record in self:
            ariza_state_service.ArizaStateService.kabul_et(record)

    def action_teknik_onarim_baslat(self):
        """Teknik ekip onarım başlatma işlemi"""
        for record in self:
            ariza_state_service.ArizaStateService.teknik_onarim_baslat(record)

    def action_onayla(self):
        """Final onaylama işlemi - Sadece teknik_onarim durumundan çalışır"""
        for record in self:
            return ariza_state_service.ArizaStateService.onayla(record)

    def action_iptal(self):
        """Arıza kaydını iptal et"""
        for record in self:
            return ariza_state_service.ArizaStateService.iptal(record)

    def action_kullanici_tamamla(self):
        """Kullanıcı tamamlama işlemi - Sadece tamamlandi durumundan çalışır"""
        for record in self:
            return ariza_state_service.ArizaStateService.kullanici_tamamla(record)


    


    def action_print(self):
        return ariza_print_service.ArizaPrintService.action_print(self)

    def action_print_invoice(self):
        return ariza_print_service.ArizaPrintService.action_print_invoice(self)

    @api.onchange('magaza_urun_id')
    def _onchange_magaza_urun_id(self):
        ariza_onchange_helper.ArizaOnchangeHelper.onchange_magaza_urun_id(self)

    def action_print_delivery(self):
        return ariza_print_service.ArizaPrintService.action_print_delivery(self)
    
    def action_teslim_al(self):
        """Mağaza ürünü teslim al işlemi - Tamir Alımlar transferi oluşturur"""
        self.ensure_one()
        return ariza_teslim_al_service.ArizaTeslimAlService.execute(self) 

    def action_teslim_al_musteri(self):
        """Müşteri ürünü için Teslim Al butonu - 2. SMS gönderir"""
        for record in self:
            ariza_state_service.ArizaStateService.teslim_al_musteri(record)

    @api.onchange('teslim_magazasi_id')
    def _onchange_teslim_magazasi(self):
        ariza_onchange_helper.ArizaOnchangeHelper.onchange_teslim_magazasi(self)

    @api.onchange('sorumlu_id')
    def _onchange_sorumlu_id(self):
        ariza_onchange_helper.ArizaOnchangeHelper.onchange_sorumlu_id(self)

    @api.depends('partner_id')
    def _get_musteri_faturalari(self):
        for record in self:
            record.musteri_faturalari = ariza_computed_helper.ArizaComputedHelper.get_musteri_faturalari(
                record.env, record.partner_id
            )

    @api.onchange('fatura_kalem_id')
    def _onchange_fatura_kalem_id(self):
        ariza_onchange_helper.ArizaOnchangeHelper.onchange_fatura_kalem_id(self)

    @api.depends('teknik_servis', 'tedarikci_id', 'tedarikci_adresi')
    def _compute_teknik_servis_adres(self):
        for rec in self:
            rec.teknik_servis_adres = ariza_computed_helper.ArizaComputedHelper.compute_teknik_servis_adres(rec)

    @api.depends('teknik_servis', 'tedarikci_id')
    def _compute_teknik_servis_telefon(self):
        for rec in self:
            rec.teknik_servis_telefon = ariza_computed_helper.ArizaComputedHelper.compute_teknik_servis_telefon(rec)

    def action_lock(self):
        for rec in self:
            ariza_state_service.ArizaStateService.lock(rec)

    def action_unlock(self):
        for rec in self:
            ariza_state_service.ArizaStateService.unlock(rec)

    def _clean_magaza_adi(self, magaza_adi):
        """Mağaza adından 'Perakende - ' önekini temizle - ArizaComputedHelper'a delegasyon"""
        return ariza_computed_helper.ArizaComputedHelper.clean_magaza_adi(magaza_adi)




    @api.depends('partner_id')
    def _compute_musteri_telefon(self):
        for rec in self:
            rec.musteri_telefon = ariza_computed_helper.ArizaComputedHelper.compute_musteri_telefon(rec)
    
    @api.depends('ariza_tipi', 'partner_id', 'analitik_hesap_id')
    def _compute_musteri_gosterim(self):
        """List görünümünde müşteri bilgisini gösterir"""
        for rec in self:
            rec.musteri_gosterim = ariza_computed_helper.ArizaComputedHelper.compute_musteri_gosterim(rec)
    
    
    @api.depends('magaza_urun_id')
    def _compute_magaza_urun_adi(self):
        """Mağaza ürünü için ürün adını hesapla"""
        for record in self:
            record.magaza_urun_adi = ariza_computed_helper.ArizaComputedHelper.compute_magaza_urun_adi(record)
    
    @api.depends('urun', 'magaza_urun_adi', 'ariza_tipi')
    def _compute_urun_gosterimi(self):
        """Birleşik ürün gösterimi - hem müşteri hem mağaza ürünü için"""
        for record in self:
            record.urun_gosterimi = ariza_computed_helper.ArizaComputedHelper.compute_urun_gosterimi(record)

    @api.model
    def _cron_update_kalan_sure(self):
        """Günlük cron - Kalan süre güncelleme"""
        ariza_cron_service.ArizaCronService.update_kalan_sure(self)

