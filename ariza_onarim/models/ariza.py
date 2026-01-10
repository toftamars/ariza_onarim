# -*- coding: utf-8 -*-
"""
Arıza Kayıt Modeli - Ana model dosyası
"""

# Standard library imports
import logging
import os
from datetime import datetime, timedelta

# Third-party imports
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

# Local imports
from .ariza_constants import (
    ArizaStates,
    StateManager,
    TeknikServis,
    ArizaTipi,
    IslemTipi,
    TransferMetodu,
    GarantiKapsam,
    TeslimAlan,
    LocationNames,
    PartnerNames,
    DefaultValues,
    MagicNumbers,
    SMSTemplates,
)
from .ariza_helpers import (
    location_helper,
    partner_helper,
    sequence_helper,
    sms_helper,
    transfer_helper,
)

_logger = logging.getLogger(__name__)

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'
    
    partner_id = fields.Many2one('res.partner', string='Partner')
    adres = fields.Text(string='Adres')
    telefon = fields.Char(string='Telefon')
    email = fields.Char(string='E-posta')
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    konum_kodu = fields.Char(
        string='Konum Kodu',
        compute='_compute_konum_kodu',
        store=True,
        help='Stok konumu kodu (örn: ADANA/Stok, UNIQ/Stok). Bu kod kaynak konum ve arızalı konum belirleme için kullanılır. Warehouse\'dan otomatik doldurulur.'
    )
    
    @api.depends('warehouse_id', 'warehouse_id.lot_stock_id')
    def _compute_konum_kodu(self):
        """
        Konum kodunu warehouse'dan otomatik hesaplar.
        Warehouse'un lot_stock_id'sinden konum adını alır.
        """
        for record in self:
            if record.warehouse_id and record.warehouse_id.lot_stock_id:
                # Warehouse'un stok konumunun adını al (örn: "ADANA/Stok")
                record.konum_kodu = record.warehouse_id.lot_stock_id.name
            else:
                record.konum_kodu = False

    @api.model
    def _setup_zuhal_addresses(self):
        """Zuhal Dış Ticaret A.Ş. carisine ait adresleri analitik hesaplarla eşleştir"""
        zuhal_partner = self.env['res.partner'].search(
            [('name', '=', PartnerNames.ZUHAL_DIS_TICARET)], limit=1
        )
        if not zuhal_partner:
            return
            
        # Zuhal'in adreslerini al
        zuhal_addresses = self.env['res.partner'].search([
            ('parent_id', '=', zuhal_partner.id),
            ('type', '=', 'delivery')
        ])
        
        for address in zuhal_addresses:
            # Bu adrese ait analitik hesap var mı kontrol et
            existing_analytic = self.search([
                ('partner_id', '=', address.id)
            ], limit=1)
            
            if not existing_analytic:
                # Yeni analitik hesap oluştur
                self.create({
                    'name': f"{address.name} - {address.street or ''}",
                    'partner_id': address.id,
                    'adres': self._format_address(address),
                    'telefon': address.phone or address.mobile,
                    'email': address.email,
                })
            else:
                # Mevcut analitik hesabı güncelle
                existing_analytic.write({
                    'adres': self._format_address(address),
                    'telefon': address.phone or address.mobile,
                    'email': address.email,
                })
    
    def _format_address(self, partner):
        """Partner adresini formatla"""
        address_parts = []
        if partner.street:
            address_parts.append(partner.street)
        if partner.street2:
            address_parts.append(partner.street2)
        if partner.city:
            address_parts.append(partner.city)
        if partner.state_id:
            address_parts.append(partner.state_id.name)
        if partner.zip:
            address_parts.append(partner.zip)
        if partner.country_id:
            address_parts.append(partner.country_id.name)
        
        return ', '.join(address_parts) if address_parts else ''

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
    
    @api.depends()
    def _compute_is_manager(self):
        """Kullanıcının normal yönetici grubunda olup olmadığını kontrol et (süper yöneticiler hariç)"""
        for rec in self:
            # Süper yönetici ise butonları görebilir (is_manager = False)
            if self.env.user.has_group('ariza_onarim.group_ariza_super_manager'):
                rec.is_manager = False
            # Sadece normal yönetici ise butonları göremez (is_manager = True)
            elif self.env.user.has_group('ariza_onarim.group_ariza_manager'):
                rec.is_manager = True
            # Yönetici değilse butonları görebilir (is_manager = False)
            else:
                rec.is_manager = False
    
    @api.depends('ariza_tipi', 'state')
    def _compute_teslim_al_visible(self):
        """Teslim Al butonunu görünür yap"""
        for rec in self:
            # Herkes görebilir, mağaza ürünü ve yönetici tamamlandı durumunda olmalı
            rec.teslim_al_visible = (
                rec.ariza_tipi == ArizaTipi.MAGAZA
                and rec.state == ArizaStates.YONETICI_TAMAMLANDI
            )
    
    # Mağaza ürünü için ürün adı
    magaza_urun_adi = fields.Char(string='Mağaza Ürün Adı', compute='_compute_magaza_urun_adi', store=True)

    @api.depends('state')
    def _compute_state_manager(self):
        """Yönetici için özel durum gösterimi - personel_onay durumunu onaylandı, teknik_onarim durumunu onarımda, onaylandi durumunu onarım tamamlandı olarak göster"""
        for record in self:
            if record.state == ArizaStates.PERSONEL_ONAY:
                record.state_manager = StateManager.ONAYLANDI
            elif record.state == ArizaStates.TEKNIK_ONARIM:
                record.state_manager = StateManager.ONARIMDA
            elif record.state == ArizaStates.ONAYLANDI:
                record.state_manager = StateManager.ONARIM_TAMAMLANDI
            elif record.state == ArizaStates.YONETICI_TAMAMLANDI:
                # Yönetici tamamladı durumu, yöneticinin görünümünde "onarım tamamlandı" olarak gösterilsin
                record.state_manager = StateManager.ONARIM_TAMAMLANDI
            else:
                record.state_manager = record.state

    @api.depends('onarim_ucreti', 'currency_id')
    def _compute_onarim_ucreti_tl(self):
        """Onarım ücretini para birimi formatında göster"""
        for record in self:
            if record.onarim_ucreti and record.currency_id:
                record.onarim_ucreti_tl = f"{record.onarim_ucreti:,.2f} {record.currency_id.symbol}"
            else:
                record.onarim_ucreti_tl = ""

    @api.depends('sorumlu_id', 'teknik_servis')
    def _compute_user_permissions(self):
        """Kullanıcının yetkilerini kontrol et"""
        for record in self:
            current_user = self.env.user
            
            # Onaylayabilen kullanıcılar - Sadece yönetici grubu
            record.can_approve = current_user.has_group('ariza_onarim.group_ariza_manager')
            
            # Teknik Servis = MAĞAZA seçildiğinde kullanıcılara da yetki ver
            if record.teknik_servis == TeknikServis.MAGAZA:
                # MAĞAZA seçildiğinde kullanıcılar Onarımı Başlat ve Onayla butonlarını kullanabilir
                record.can_start_repair = True
                record.can_approve = True
            else:
                # Onarımı başlatabilen kullanıcılar - Grup bazlı kontrol
                record.can_start_repair = (
                    current_user.has_group('ariza_onarim.group_ariza_manager') or
                    current_user.has_group('ariza_onarim.group_ariza_technician')
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Sorumlu kişinin analitik bilgisini al
            if not vals.get('analitik_hesap_id') and vals.get('sorumlu_id'):
                sorumlu = self.env['res.users'].browse(vals['sorumlu_id'])
                if sorumlu and sorumlu.employee_id and sorumlu.employee_id.magaza_id:
                    vals['analitik_hesap_id'] = sorumlu.employee_id.magaza_id.id
            
            # Arıza tipine göre ürün alanı kontrolü - Geçici olarak kaldırıldı
            # ariza_tipi = vals.get('ariza_tipi', 'musteri')
            # if ariza_tipi == 'musteri':
            #     # Müşteri ürünü için urun alanı zorunlu
            #     if not vals.get('urun'):
            #         raise ValidationError(_('Müşteri ürünü için "Ürün" alanı zorunludur.'))
            # elif ariza_tipi == 'magaza':
            #     # Mağaza ürünü için magaza_urun_id alanı zorunlu
            #     magaza_urun_id = vals.get('magaza_urun_id')
            #     # Debug log ekle
            #     _logger.info(f"Mağaza ürünü kayıt - magaza_urun_id: {magaza_urun_id}, vals: {vals}")
            #     if not magaza_urun_id:
            #         raise ValidationError(_('Mağaza ürünü için "Ürün" seçimi zorunludur.'))
            #     # magaza_urun_id seçilmişse urun ve model alanlarını doldur
            #     if magaza_urun_id:
            #         urun = self.env['product.product'].browse(magaza_urun_id)
            #         if urun:
            #         vals['urun'] = urun.name or ''
            #         vals['model'] = urun.default_code or ''
            # Varsayılan değerleri ayarla
            if not vals.get('name'):
                vals['name'] = sequence_helper.SequenceHelper.generate_ariza_number(
                    self.env
                )
            if not vals.get('state'):
                vals['state'] = ArizaStates.DRAFT
            if not vals.get('islem_tipi'):
                vals['islem_tipi'] = IslemTipi.ARIZA_KABUL
            
            # Mağaza ürünü ve teknik servis DTL BEYOĞLU/DTL OKMEYDANI ise hedef konum DTL/Stok
            if vals.get('ariza_tipi') == ArizaTipi.MAGAZA and vals.get('teknik_servis') in TeknikServis.DTL_SERVISLER:
                if not vals.get('hedef_konum_id'):
                    dtl_konum = location_helper.LocationHelper.get_dtl_stok_location(
                        self.env, vals.get('company_id') or self.env.company.id
                    )
                    if not dtl_konum:
                        # Şirket filtresi olmadan da ara (manuel girilmiş konum isimleri için)
                        dtl_konum = self.env['stock.location'].search([
                            ('complete_name', 'ilike', 'DTL/Stok')
                        ], limit=1) or self.env['stock.location'].search([
                            ('name', 'ilike', 'DTL'),
                            ('name', 'ilike', 'Stok'),
                        ], limit=1) or self.env['stock.location'].search([
                            ('complete_name', 'ilike', 'DTL')
                        ], limit=1)
                    if dtl_konum:
                        vals['hedef_konum_id'] = dtl_konum.id
            elif vals.get('ariza_tipi') == ArizaTipi.MAGAZA and vals.get('teknik_servis') == TeknikServis.ZUHAL_ARIZA_DEPO:
                if not vals.get('hedef_konum_id'):
                    ariza_konum = location_helper.LocationHelper.get_ariza_stok_location(
                        self.env, vals.get('company_id') or self.env.company.id
                    )
                    if not ariza_konum:
                        ariza_konum = self.env['stock.location'].search([
                            ('complete_name', 'ilike', 'Arıza/Stok')
                        ], limit=1) or self.env['stock.location'].search([
                            ('name', 'ilike', 'Arıza'),
                            ('name', 'ilike', 'Stok'),
                        ], limit=1)
                    if ariza_konum:
                        vals['hedef_konum_id'] = ariza_konum.id
            elif vals.get('ariza_tipi') == ArizaTipi.MAGAZA and vals.get('teknik_servis') == TeknikServis.ZUHAL_NEFESLI:
                if not vals.get('hedef_konum_id'):
                    nfsl_konum = location_helper.LocationHelper.get_nfsl_stok_location(
                        self.env, vals.get('company_id') or self.env.company.id
                    )
                    if not nfsl_konum:
                        nfsl_konum = self.env['stock.location'].search([
                            ('complete_name', 'ilike', 'NFSL/Stok')
                        ], limit=1) or self.env['stock.location'].search([
                            ('name', 'ilike', 'NFSL'),
                            ('name', 'ilike', 'Stok'),
                        ], limit=1)
                    if nfsl_konum:
                        vals['hedef_konum_id'] = nfsl_konum.id
            if not vals.get('ariza_tipi'):
                vals['ariza_tipi'] = ArizaTipi.MUSTERI
            if not vals.get('sorumlu_id'):
                vals['sorumlu_id'] = self.env.user.id
        
        records = super().create(vals_list)
        
        # Yeni oluşturulan kayıtlar için kargo firması ve barkod set et
        for record in records:
            
            # Müşteri ürünü için barkod oluştur (stock.picking yok)
            if record.ariza_tipi == ArizaTipi.MUSTERI and not record.barcode:
                record.barcode = self.env['ir.sequence'].next_by_code('ariza.kayit.barcode') or False
                if record.barcode:
                    _logger.info(f"Müşteri ürünü barkod oluşturuldu: {record.name} - Barkod: {record.barcode}")
        
        # Yeni oluşturulan kayıtlar için chatter mesajı ekle
        for record in records:
            try:
                # Chatter'a arıza tanımını içeren mesaj ekle
                ariza_tanimi = record.ariza_tanimi or "Arıza tanımı belirtilmemiş"
                chatter_mesaji = f"Arıza Tanımı: {ariza_tanimi}"
                record.message_post(body=chatter_mesaji, message_type='notification')
                
            except Exception as e:
                _logger.error(f"Chatter mesajı eklenemedi: {record.name} - {str(e)}")
        
        return records

    @api.model
    def _check_onarim_deadlines(self):
        """Günlük olarak onarım süreçlerini kontrol et ve hatırlatma gönder"""
        bugun = datetime.now().date()
        
        # Hatırlatma gönderilmesi gereken kayıtları bul
        hatirlatma_gereken_kayitlar = self.search([
            ('onarim_baslangic_tarihi', '!=', False),
            ('onarim_durumu', 'in', ['beklemede', 'devam_ediyor']),
            ('state', 'not in', ['tamamlandi', 'teslim_edildi', 'iptal']),
            '|',
            ('hatirlatma_gonderildi', '=', False),
            ('son_hatirlatma_tarihi', '<', bugun - timedelta(days=3))  # 3 günde bir hatırlat
        ])
        
        for kayit in hatirlatma_gereken_kayitlar:
            # Kalan süre kontrolü - Email gönderimi kaldırıldı
            if kayit.kalan_is_gunu <= MagicNumbers.HATIRLATMA_IS_GUNU:  # Belirlenen iş günü veya daha az kaldıysa
                kayit.hatirlatma_gonderildi = True
                kayit.son_hatirlatma_tarihi = fields.Date.today()
                _logger.info(f"Onarım hatırlatma işaretlendi: {kayit.name} - Kalan süre: {kayit.kalan_is_gunu} gün")

    def action_onayla_kullanici_bazli(self):
        """Kullanıcı bazlı onay sistemi - Onarım sürecini aktif hale getirir"""
        current_user = self.env.user
        
        # Onaylayabilen kullanıcılar - Sadece yönetici grubu
        if not current_user.has_group('ariza_onarim.group_ariza_manager'):
            raise UserError(_('Bu işlemi sadece yetkili kullanıcılar yapabilir.'))
        
        # Arıza kaydını onayla
        self.state = ArizaStates.ONAYLANDI
        self.message_post(body=_('Arıza kaydı onaylandı ve onarım süreci aktif hale getirildi.'), message_type='notification')
        _logger.info(f"Arıza kaydı onaylandı: {self.name} - Kullanıcı: {current_user.login}")

    def action_onarim_baslat(self):
        """Onarım sürecini başlat - Sadece teknik ekip"""
        current_user = self.env.user
        
        # Onarımı başlatabilen kullanıcılar - Grup bazlı kontrol
        if not (current_user.has_group('ariza_onarim.group_ariza_manager') or
                current_user.has_group('ariza_onarim.group_ariza_technician')):
            raise UserError(_('Bu işlemi sadece teknik ekip yapabilir.'))
        
        if self.state != ArizaStates.ONAYLANDI:
            raise UserError(_('Sadece onaylanmış arıza kayıtları için onarım başlatılabilir.'))
        
        # Onarım sürecini başlat
        self.onarim_baslangic_tarihi = fields.Date.today()
        self.onarim_durumu = 'devam_ediyor'
        self.message_post(body=_('Onarım süreci başlatıldı.'), message_type='notification')
        _logger.info(f"Onarım süreci başlatıldı: {self.name} - Kullanıcı: {current_user.login}")

    @api.depends('invoice_line_id')
    def _compute_fatura_tarihi(self):
        for record in self:
            if record.invoice_line_id:
                record.fatura_tarihi = record.invoice_line_id.move_id.invoice_date
            else:
                record.fatura_tarihi = False

    @api.depends('invoice_line_id', 'fatura_tarihi')
    def _compute_garanti_suresi(self):
        for record in self:
            if record.invoice_line_id and record.fatura_tarihi:
                # Fatura tarihinden itibaren garanti süresini hesapla
                # Varsayılan garanti süresi 2 yıl (24 ay)
                garanti_ay = MagicNumbers.DEFAULT_GARANTI_AY
                
                # Ürünün garanti süresi varsa onu kullan
                if record.invoice_line_id.product_id and hasattr(record.invoice_line_id.product_id, 'garanti_suresi'):
                    garanti_ay = record.invoice_line_id.product_id.garanti_suresi or MagicNumbers.GARANTI_AY_FALLBACK
                
                # Garanti bitiş tarihini hesapla
                garanti_bitis = record.fatura_tarihi + relativedelta(months=garanti_ay)
                record.garanti_bitis_tarihi = garanti_bitis
                
                # Garanti süresini metin olarak ayarla
                record.garanti_suresi = f"{garanti_ay} ay"
                
                # Kalan garanti süresini hesapla
                bugun = datetime.now().date()
                if garanti_bitis > bugun:
                    kalan_gun = (garanti_bitis - bugun).days
                    kalan_ay = kalan_gun // MagicNumbers.GUN_AY_CARPI
                    kalan_gun_kalan = kalan_gun % MagicNumbers.GUN_AY_CARPI
                    if kalan_ay > 0:
                        record.kalan_garanti = f"{kalan_ay} ay {kalan_gun_kalan} gün"
                    else:
                        record.kalan_garanti = f"{kalan_gun} gün"
                else:
                    record.kalan_garanti = "Garanti süresi dolmuş"
            else:
                record.garanti_suresi = False
                record.garanti_bitis_tarihi = False
                record.kalan_garanti = False

    @api.depends('tarih')
    def _compute_beklenen_tamamlanma_tarihi(self):
        """Belge oluşturulma tarihinden belirlenen iş günü sonrasını hesapla"""
        for record in self:
            # Başlangıç tarihi: Her zaman belge oluşturulma tarihi (tarih alanı)
            baslangic_tarihi = record.tarih or fields.Date.today()
            
            # Belirlenen iş günü sonrasını hesapla (hafta sonları hariç)
            is_gunu_sayisi = 0
            hedef_tarih = baslangic_tarihi
            
            while is_gunu_sayisi < MagicNumbers.ONARIM_IS_GUNU:
                hedef_tarih += timedelta(days=1)
                # Hafta sonu değilse iş günü say
                if hedef_tarih.weekday() < MagicNumbers.HAFTA_SONU_BASLANGIC:  # 0-4 = Pazartesi-Cuma
                    is_gunu_sayisi += 1
            
            record.beklenen_tamamlanma_tarihi = hedef_tarih

    @api.depends('beklenen_tamamlanma_tarihi')
    def _compute_kalan_is_gunu(self):
        """Bugünden itibaren kalan iş günü sayısını hesapla - Her gün otomatik azalır"""
        for record in self:
            if record.beklenen_tamamlanma_tarihi:
                bugun = datetime.now().date()
                hedef_tarih = record.beklenen_tamamlanma_tarihi
                
                if hedef_tarih <= bugun:
                    # Süre dolmuş
                    record.kalan_is_gunu = 0
                    if record.onarim_durumu != 'tamamlandi':
                        record.onarim_durumu = 'gecikti'
                else:
                    # Kalan iş günü sayısını hesapla (bugünün tarihine göre)
                    kalan_gun = 0
                    current_date = bugun
                    
                    while current_date < hedef_tarih:
                        current_date += timedelta(days=1)
                        if current_date.weekday() < MagicNumbers.HAFTA_SONU_BASLANGIC:  # Hafta sonu değilse
                            kalan_gun += 1
                    
                    record.kalan_is_gunu = kalan_gun
                    
                    # Onarım durumunu güncelle
                    if kalan_gun <= MagicNumbers.UYARI_IS_GUNU and record.onarim_durumu == 'beklemede':
                        record.onarim_durumu = 'devam_ediyor'
            else:
                record.kalan_is_gunu = 0

    @api.depends('kalan_is_gunu')
    def _compute_kalan_sure_gosterimi(self):
        """Kalan süreye göre özel gösterim metni oluştur"""
        for record in self:
            if record.kalan_is_gunu == 0:
                record.kalan_sure_gosterimi = "Süre Aşıldı"
            elif record.kalan_is_gunu <= MagicNumbers.KRITIK_IS_GUNU:
                record.kalan_sure_gosterimi = f"{record.kalan_is_gunu} gün"
            else:
                record.kalan_sure_gosterimi = f"{record.kalan_is_gunu} gün"

    def _update_hedef_konum(self):
        """
        Arıza tipi ve teknik servis seçimine göre hedef konumu günceller.
        Bu metod hem @api.onchange('ariza_tipi') hem de @api.onchange('teknik_servis')
        metodlarından çağrılır.
        """
        _logger.info(f"_update_hedef_konum çağrıldı - ariza_tipi: {self.ariza_tipi}, teknik_servis: {self.teknik_servis}")
        if not self.ariza_tipi or not self.teknik_servis:
            _logger.warning(f"_update_hedef_konum: Eksik bilgi - ariza_tipi: {self.ariza_tipi}, teknik_servis: {self.teknik_servis}")
            return
        
        # Müşteri ürünü için hedef konum ayarları
        if self.ariza_tipi == ArizaTipi.MUSTERI:
            if self.teknik_servis in TeknikServis.DTL_SERVISLER:
                # DTL seçildiğinde DTL/Stok konumu
                dtl_konum = location_helper.LocationHelper.get_dtl_stok_location(
                    self.env, self.company_id.id or self.env.company.id
                )
                if dtl_konum:
                    self.hedef_konum_id = dtl_konum
            elif self.teknik_servis == TeknikServis.ZUHAL_ARIZA_DEPO:
                # Zuhal Arıza Depo seçildiğinde Arıza/Stok konumu
                ariza_konum = location_helper.LocationHelper.get_ariza_stok_location(
                    self.env, self.company_id.id or self.env.company.id
                ) or self.env['stock.location'].search([
                    ('complete_name', 'ilike', 'Arıza/Stok')
                ], limit=1) or self.env['stock.location'].search([
                    ('name', 'ilike', 'Arıza'),
                    ('name', 'ilike', 'Stok'),
                ], limit=1)
                if ariza_konum:
                    self.hedef_konum_id = ariza_konum
            elif self.teknik_servis == TeknikServis.ZUHAL_NEFESLI:
                # Zuhal Nefesli seçildiğinde NFSL/Stok konumu
                nfsl_konum = location_helper.LocationHelper.get_nfsl_stok_location(
                    self.env, self.company_id.id or self.env.company.id
                ) or self.env['stock.location'].search([
                    ('complete_name', 'ilike', 'NFSL/Stok')
                ], limit=1) or self.env['stock.location'].search([
                    ('name', 'ilike', 'NFSL'),
                    ('name', 'ilike', 'Stok'),
                ], limit=1)
                if nfsl_konum:
                    self.hedef_konum_id = nfsl_konum
            elif self.teknik_servis == TeknikServis.MAGAZA:
                # Mağaza seçildiğinde hedef konum boş olmalı
                self.hedef_konum_id = False
        
        # Mağaza ürünü için hedef konum ayarları
        elif self.ariza_tipi == ArizaTipi.MAGAZA:
            if self.teknik_servis in TeknikServis.DTL_SERVISLER:
                # DTL BEYOĞLU veya DTL OKMEYDANI → DTL/Stok
                company_id = self.company_id.id or self.env.company.id
                dtl_konum = location_helper.LocationHelper.get_dtl_stok_location(
                    self.env, company_id
                )
                if not dtl_konum:
                    # Şirket filtresi olmadan da ara (manuel girilmiş konum isimleri için)
                    dtl_konum = self.env['stock.location'].search([
                        ('complete_name', 'ilike', 'DTL/Stok')
                    ], limit=1) or self.env['stock.location'].search([
                        ('name', 'ilike', 'DTL'),
                        ('name', 'ilike', 'Stok'),
                    ], limit=1) or self.env['stock.location'].search([
                        ('complete_name', 'ilike', 'DTL')
                    ], limit=1)
                if dtl_konum:
                    self.hedef_konum_id = dtl_konum
                    _logger.info(f"Hedef konum belirlendi (DTL): {dtl_konum.name}")
                else:
                    _logger.warning("DTL/Stok konumu bulunamadı")
            elif self.teknik_servis == TeknikServis.ZUHAL_ARIZA_DEPO:
                # ZUHAL ARIZA DEPO → Arıza/Stok
                ariza_konum = location_helper.LocationHelper.get_ariza_stok_location(
                    self.env, self.company_id.id or self.env.company.id
                ) or self.env['stock.location'].search([
                    ('complete_name', 'ilike', 'Arıza/Stok')
                ], limit=1) or self.env['stock.location'].search([
                    ('name', 'ilike', 'Arıza'),
                    ('name', 'ilike', 'Stok'),
                ], limit=1)
                if ariza_konum:
                    self.hedef_konum_id = ariza_konum
            elif self.teknik_servis == TeknikServis.ZUHAL_NEFESLI:
                # ZUHAL NEFESLİ → NFSL/Stok
                nfsl_konum = location_helper.LocationHelper.get_nfsl_stok_location(
                    self.env, self.company_id.id or self.env.company.id
                ) or self.env['stock.location'].search([
                    ('complete_name', 'ilike', 'NFSL/Stok')
                ], limit=1) or self.env['stock.location'].search([
                    ('name', 'ilike', 'NFSL'),
                    ('name', 'ilike', 'Stok'),
                ], limit=1)
                if nfsl_konum:
                    self.hedef_konum_id = nfsl_konum
            elif self.teknik_servis == TeknikServis.TEDARIKCI and self.tedarikci_id:
                # TEDARİKÇİ → tedarikçi konumu
                if self.tedarikci_id.property_stock_supplier:
                    self.hedef_konum_id = self.tedarikci_id.property_stock_supplier

    @api.onchange('ariza_tipi')
    def _onchange_ariza_tipi(self):
        if self.ariza_tipi == ArizaTipi.MUSTERI:
            self.partner_id = False
            self.urun = False
            self.model = False
            self.magaza_urun_id = False
            self.teslim_magazasi_id = False
            self.teslim_adresi = False
            self.transfer_id = False
            # Hedef konumu güncelle (ortak metod)
            self._update_hedef_konum()
        elif self.ariza_tipi == ArizaTipi.MAGAZA:
            self.partner_id = False
            self.urun = False
            self.model = False
            self.magaza_urun_id = False
            # Teknik servis temizlenmemeli, sadece kontrol edilmeli
            # self.teknik_servis = False  # Mağaza ürünü seçildiğinde teknik servis temizle
            self.teslim_magazasi_id = self.env.user.employee_id.magaza_id
            if self.teslim_magazasi_id and self.teslim_magazasi_id.name in [TeknikServis.DTL_OKMEYDANI, TeknikServis.DTL_BEYOGLU]:
                self.teslim_adresi = 'MAHMUT ŞEVKET PAŞA MAH. ŞAHİNKAYA SOK NO 31 OKMEYDANI'
            
            # Mağaza ürünü için kaynak konum belirleme (analitik hesap seçiliyse)
            if self.analitik_hesap_id:
                konum_kodu = None
                # Önce warehouse'dan direkt oku (computed field henüz hesaplanmamış olabilir)
                if self.analitik_hesap_id.warehouse_id and self.analitik_hesap_id.warehouse_id.lot_stock_id:
                    konum_kodu = self.analitik_hesap_id.warehouse_id.lot_stock_id.name
                # Eğer warehouse'dan yoksa, computed field'dan oku
                if not konum_kodu:
                    konum_kodu = self.analitik_hesap_id.konum_kodu
                # Eğer hala yoksa, dosyadan okumayı dene (fallback)
                if not konum_kodu:
                    dosya_yolu = os.path.join(
                        os.path.dirname(__file__), '..', 'Analitik Bilgileri.txt'
                    )
                    konum_kodu = location_helper.LocationHelper.parse_konum_kodu_from_file(
                        self.env, self.analitik_hesap_id.name, dosya_yolu
                    )

                if konum_kodu:
                    konum = location_helper.LocationHelper.get_location_by_name(
                        self.env, konum_kodu
                    )
                    if konum:
                        self.kaynak_konum_id = konum
                        _logger.info(f"Kaynak konum belirlendi: {konum_kodu} -> {konum.name}")
                    else:
                        _logger.warning(f"Konum bulunamadı: {konum_kodu}")
                else:
                    # Konum kodu bulunamadı - kullanıcıya uyarı göster
                    _logger.warning(
                        f"Konum kodu bulunamadı - Analitik Hesap: {self.analitik_hesap_id.name} "
                        f"(ID: {self.analitik_hesap_id.id}). Warehouse atanmış mı kontrol edin."
                    )
            
            # Mağaza ürünü için konumları güncelle
            if self.ariza_tipi == ArizaTipi.MAGAZA:
                self._onchange_magaza_konumlar()
        elif self.ariza_tipi == 'teknik':
            self.partner_id = False
            self.urun = False
            self.model = False
            self.magaza_urun_id = False
            self.teslim_magazasi_id = False
            self.teslim_adresi = False

    @api.onchange('teknik_servis')
    def _onchange_teknik_servis(self):
        # Arıza Tipi Mağaza Ürünü seçildiğinde MAĞAZA seçeneğini engelle
        if self.ariza_tipi == ArizaTipi.MAGAZA and self.teknik_servis == TeknikServis.MAGAZA:
            self.teknik_servis = False
            return {
                'warning': {
                    'title': 'Uyarı',
                    'message': 'Arıza Tipi Mağaza Ürünü seçildiğinde Teknik Servis olarak MAĞAZA seçilemez!'
                }
            }
        
        # İşlem tipi kontrolü - sadece MAĞAZA VE TEDARİKÇİ seçildiğinde ek seçenekler
        if self.teknik_servis not in [TeknikServis.MAGAZA, TeknikServis.TEDARIKCI] and self.islem_tipi not in [IslemTipi.ARIZA_KABUL]:
            self.islem_tipi = IslemTipi.ARIZA_KABUL

        # Mağaza ürünü için kaynak konum belirleme (analitik hesap seçiliyse)
        if self.ariza_tipi == ArizaTipi.MAGAZA and self.analitik_hesap_id:
            konum_kodu = None
            # Önce warehouse'dan direkt oku (computed field henüz hesaplanmamış olabilir)
            if self.analitik_hesap_id.warehouse_id and self.analitik_hesap_id.warehouse_id.lot_stock_id:
                konum_kodu = self.analitik_hesap_id.warehouse_id.lot_stock_id.name
            # Eğer warehouse'dan yoksa, computed field'dan oku
            if not konum_kodu:
                konum_kodu = self.analitik_hesap_id.konum_kodu
            # Eğer hala yoksa, dosyadan okumayı dene (fallback)
            if not konum_kodu:
                dosya_yolu = os.path.join(
                    os.path.dirname(__file__), '..', 'Analitik Bilgileri.txt'
                )
                konum_kodu = location_helper.LocationHelper.parse_konum_kodu_from_file(
                    self.env, self.analitik_hesap_id.name, dosya_yolu
                )

            if konum_kodu:
                konum = location_helper.LocationHelper.get_location_by_name(
                    self.env, konum_kodu
                )
                if konum:
                    self.kaynak_konum_id = konum
                    _logger.info(f"Kaynak konum belirlendi: {konum_kodu} -> {konum.name}")
                else:
                    _logger.warning(f"Konum bulunamadı: {konum_kodu}")
            else:
                # Konum kodu bulunamadı - kullanıcıya uyarı göster
                _logger.warning(
                    f"Konum kodu bulunamadı - Analitik Hesap: {self.analitik_hesap_id.name} "
                    f"(ID: {self.analitik_hesap_id.id}). Warehouse atanmış mı kontrol edin."
                )

        # DTL Beyoğlu adresini otomatik ekle
        if self.teknik_servis == 'dtl_beyoglu':
            self.tedarikci_adresi = 'Şahkulu, Nakkaş Çk. No:1 D:1, 34420 Beyoğlu/İstanbul'
        # Zuhal adresini otomatik ekle
        elif self.teknik_servis == 'zuhal':
            self.tedarikci_adresi = 'Halkalı Merkez, 34303 Küçükçekmece/İstanbul'
        # TEDARİKÇİ seçildiğinde tedarikçi adresini otomatik doldur
        elif self.teknik_servis == 'TEDARİKÇİ' and self.tedarikci_id:
            # Tedarikçi adresini kapsamlı şekilde oluştur
            adres_parcalari = []
            if self.tedarikci_id.street:
                adres_parcalari.append(self.tedarikci_id.street)
            if self.tedarikci_id.street2:
                adres_parcalari.append(self.tedarikci_id.street2)
            if self.tedarikci_id.city:
                adres_parcalari.append(self.tedarikci_id.city)
            if self.tedarikci_id.state_id:
                adres_parcalari.append(self.tedarikci_id.state_id.name)
            if self.tedarikci_id.zip:
                adres_parcalari.append(self.tedarikci_id.zip)
            if self.tedarikci_id.country_id:
                adres_parcalari.append(self.tedarikci_id.country_id.name)
            
            self.tedarikci_adresi = ', '.join(adres_parcalari) if adres_parcalari else ''

        # Mağaza ürünü için konumları güncelle
        if self.ariza_tipi == ArizaTipi.MAGAZA:
            self._onchange_magaza_konumlar()

    @api.onchange('ariza_tipi', 'analitik_hesap_id', 'teknik_servis')
    def _onchange_magaza_konumlar(self):
        """Mağaza ürünü için kaynak ve hedef konumları otomatik belirle"""
        # Sadece mağaza ürünü için çalış
        if self.ariza_tipi != ArizaTipi.MAGAZA:
            return
        
        # Kaynak konum belirleme (analitik hesap seçiliyse)
        if self.analitik_hesap_id:
            konum_kodu = None
            # Önce warehouse'dan direkt oku
            if self.analitik_hesap_id.warehouse_id and self.analitik_hesap_id.warehouse_id.lot_stock_id:
                konum_kodu = self.analitik_hesap_id.warehouse_id.lot_stock_id.name
            # Eğer warehouse'dan yoksa, computed field'dan oku
            if not konum_kodu:
                konum_kodu = self.analitik_hesap_id.konum_kodu
            # Eğer hala yoksa, dosyadan okumayı dene (fallback)
            if not konum_kodu:
                dosya_yolu = os.path.join(
                    os.path.dirname(__file__), '..', 'Analitik Bilgileri.txt'
                )
                konum_kodu = location_helper.LocationHelper.parse_konum_kodu_from_file(
                    self.env, self.analitik_hesap_id.name, dosya_yolu
                )

            if konum_kodu:
                konum = location_helper.LocationHelper.get_location_by_name(
                    self.env, konum_kodu
                )
                if konum:
                    self.kaynak_konum_id = konum

        # Hedef konum belirleme (teknik servis seçiliyse)
        if self.teknik_servis:
            self._update_hedef_konum()

    @api.onchange('analitik_hesap_id')
    def _onchange_analitik_hesap_id(self):
        # Önce adres bilgilerini temizle
        self.teslim_adresi = ''
        self.tedarikci_telefon = ''
        self.tedarikci_email = ''

        # Analitik hesaptan adres bilgilerini al
        if self.analitik_hesap_id:
            if self.analitik_hesap_id.adres:
                self.teslim_adresi = self.analitik_hesap_id.adres
            if self.analitik_hesap_id.telefon:
                self.tedarikci_telefon = self.analitik_hesap_id.telefon
            if self.analitik_hesap_id.email:
                self.tedarikci_email = self.analitik_hesap_id.email
        
        # Mağaza ürünü için konumları güncelle
        if self.ariza_tipi == ArizaTipi.MAGAZA:
            self._onchange_magaza_konumlar()

    @api.depends('analitik_hesap_id', 'analitik_hesap_id.adres', 'analitik_hesap_id.telefon', 'analitik_hesap_id.email', 'analitik_hesap_id.name')
    def _compute_analitik_hesap_bilgileri(self):
        """Analitik hesap bilgilerini computed field'lara aktar (form view gösterimi için)"""
        for record in self:
            if record.analitik_hesap_id:
                record.analitik_hesap_adres = record.analitik_hesap_id.adres or record.analitik_hesap_id.name or ''
                record.analitik_hesap_telefon = record.analitik_hesap_id.telefon or ''
                record.analitik_hesap_email = record.analitik_hesap_id.email or ''
            else:
                record.analitik_hesap_adres = ''
                record.analitik_hesap_telefon = ''
                record.analitik_hesap_email = ''

    @api.onchange('invoice_line_id')
    def _onchange_invoice_line_id(self):
        if self.invoice_line_id:
            product = self.invoice_line_id.product_id
            if product:
                if self.islem_tipi == IslemTipi.ARIZA_KABUL and self.ariza_tipi == ArizaTipi.MUSTERI and not self.siparis_yok:
                    self.urun = product.name
                    self.model = product.default_code or ''
                    # Marka bilgisini ürün şablonundan al
                    if hasattr(product, 'brand_id') and product.brand_id:
                        self.marka_id = product.brand_id.id
                        # Marka seçilince tedarikçi otomatik gelsin
                        if self.marka_id:
                            marka = self.env['product.brand'].browse(self.marka_id)
                            if marka and marka.partner_id:
                                self.tedarikci_id = marka.partner_id.id
                                self._onchange_tedarikci()
                    else:
                        self.marka_id = False
                        self.tedarikci_id = False
                        self.tedarikci_adresi = False
                        self.tedarikci_telefon = False
                        self.tedarikci_email = False
                else:
                    self.urun = product.name
                    self.model = product.default_code or ''
                    if hasattr(product, 'brand_id') and product.brand_id:
                        self.marka_id = product.brand_id.id
                        if self.marka_id:
                            marka = self.env['product.brand'].browse(self.marka_id)
                            if marka and marka.partner_id:
                                self.tedarikci_id = marka.partner_id.id
                                self._onchange_tedarikci()
                    else:
                        self.marka_id = False
                        self.tedarikci_id = False
                        self.tedarikci_adresi = False
                        self.tedarikci_telefon = False
                        self.tedarikci_email = False

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if not self.partner_id:
            self.invoice_line_id = False
            self.siparis_yok = False
            self.urun = False
            self.model = False

    @api.onchange('marka_id')
    def _onchange_marka_id(self):
        if self.marka_id:
            # Marka seçilince tedarikçi otomatik gelsin
            if self.marka_id.partner_id:
                self.tedarikci_id = self.marka_id.partner_id.id
                self._onchange_tedarikci()
        else:
            self.tedarikci_id = False
            self.tedarikci_adresi = False
            self.tedarikci_telefon = False
            self.tedarikci_email = False
            self.marka_urunleri_ids = False
            self.magaza_urun_id = False

    @api.onchange('tedarikci_id')
    def _onchange_tedarikci(self):
        if self.tedarikci_id:
            # Tedarikçi adresini kapsamlı şekilde oluştur
            adres_parcalari = []
            if self.tedarikci_id.street:
                adres_parcalari.append(self.tedarikci_id.street)
            if self.tedarikci_id.street2:
                adres_parcalari.append(self.tedarikci_id.street2)
            if self.tedarikci_id.city:
                adres_parcalari.append(self.tedarikci_id.city)
            if self.tedarikci_id.state_id:
                adres_parcalari.append(self.tedarikci_id.state_id.name)
            if self.tedarikci_id.zip:
                adres_parcalari.append(self.tedarikci_id.zip)
            if self.tedarikci_id.country_id:
                adres_parcalari.append(self.tedarikci_id.country_id.name)
            
            self.tedarikci_adresi = ', '.join(adres_parcalari) if adres_parcalari else ''
            self.tedarikci_telefon = self.tedarikci_id.phone
            self.tedarikci_email = self.tedarikci_id.email
            # Kontak (Teslimat Adresi) otomatik gelsin
            delivery_contact = self.tedarikci_id.child_ids.filtered(lambda c: c.type == 'delivery')
            self.contact_id = delivery_contact[0].id if delivery_contact else self.tedarikci_id.id
            # Tedarikçiye gönderim ise hedef konum tedarikçi adresi
            if self.teknik_servis == 'TEDARİKÇİ':
                if not self.tedarikci_id.property_stock_supplier:
                    raise UserError(_('Seçilen tedarikçinin stok konumu tanımlı değil! Lütfen tedarikçi kartında "Satıcı Konumu" alanını doldurun.'))
                self.hedef_konum_id = self.tedarikci_id.property_stock_supplier

    @api.onchange('islem_tipi')
    def _onchange_islem_tipi(self):
        if self.islem_tipi != IslemTipi.ARIZA_KABUL:
            self.garanti_kapsaminda_mi = False

    @api.onchange('ariza_tipi')
    def _onchange_ariza_tipi_teknik(self):
        if self.ariza_tipi == 'teknik' and self.analitik_hesap_id:
            # Analitik hesaptan kaynak konumu al
            if hasattr(self.analitik_hesap_id, 'konum_id') and self.analitik_hesap_id.konum_id:
                self.kaynak_konum_id = self.analitik_hesap_id.konum_id
            # Hedef konumu DTL/Stok olarak ayarla
            dtl_konum = self.env['stock.location'].search([
                ('name', '=', 'DTL/Stok'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            if dtl_konum:
                self.hedef_konum_id = dtl_konum

    @api.onchange('ariza_kabul_id')
    def _onchange_ariza_kabul_id(self):
        if self.ariza_kabul_id:
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
                setattr(self, field, getattr(self.ariza_kabul_id, field, False))

    def _get_default_driver_id(self):
        """
        Default sürücü ID'sini system parameter'dan alır.
        System parameter yoksa veya geçersizse constants'tan default değeri kullanır.
        
        Returns:
            int: Default driver partner ID
        """
        try:
            driver_id_str = (
                self.env['ir.config_parameter']
                .sudo()
                .get_param('ariza_onarim.default_driver_id')
            )
            if driver_id_str:
                driver_id = int(driver_id_str)
                # ID'nin geçerli olduğunu kontrol et
                driver_partner = self.env['res.partner'].browse(driver_id)
                if driver_partner.exists():
                    return driver_id
                else:
                    _logger.warning(
                        f"System parameter'daki sürücü ID ({driver_id}) "
                        f"geçersiz. Default değer kullanılıyor."
                    )
        except (ValueError, TypeError) as e:
            _logger.warning(
                f"System parameter'dan sürücü ID okunamadı: {str(e)}. "
                f"Default değer kullanılıyor."
            )
        except Exception as e:
            _logger.error(f"System parameter okuma hatası: {str(e)}. Default değer kullanılıyor.")
        
        # Fallback: Constants'tan default değer
        return DefaultValues.DEFAULT_DRIVER_ID

    def _create_stock_transfer(self, kaynak_konum=None, hedef_konum=None, force_internal=False, delivery_type=None, transfer_tipi=None):
        kaynak = kaynak_konum or self.kaynak_konum_id
        hedef = hedef_konum or self.hedef_konum_id
        
        if not self.analitik_hesap_id:
            raise UserError(_("Transfer oluşturulamadı: Analitik hesap seçili değil!"))
        if not kaynak or not hedef:
            raise UserError(_("Transfer oluşturulamadı: Kaynak veya hedef konum eksik!"))
        if not self.magaza_urun_id:
            raise UserError(_("Transfer oluşturulamadı: Ürün seçili değil!"))

        # Analitik hesap adını al ve "Perakende -" önekini temizle
        magaza_adi = ""
        if self.analitik_hesap_id and self.analitik_hesap_id.name:
            magaza_adi = self.analitik_hesap_id.name
            # "Perakende -" önekini temizle
            if magaza_adi.startswith("Perakende - "):
                magaza_adi = magaza_adi[MagicNumbers.PERAKENDE_PREFIX_LENGTH:]  # "Perakende - " önekini temizle

        # Depo bilgisini al
        warehouse = False
        if self.analitik_hesap_id and self.analitik_hesap_id.name:
            # Analitik hesap adından depo adını çıkar
            magaza_adi = self.analitik_hesap_id.name
            if magaza_adi.startswith("Perakende - "):
                magaza_adi = magaza_adi[12:]  # "Perakende - " önekini temizle
            
            # Özel durum: Temaworld için "Tema World" olarak ara
            depo_arama_adi = magaza_adi
            if magaza_adi.lower() in ['temaworld', 'tema world']:
                depo_arama_adi = 'Tema World'
            
            # Mağaza adına göre depo ara
            warehouse = self.env['stock.warehouse'].search([
                ('name', 'ilike', depo_arama_adi)
            ], limit=1)

        # Operasyon tipi seçimi - depo bilgisine göre
        picking_type = False
        
        # 1. transfer için depo bazlı 'Tamir Teslimatları' ara
        if transfer_tipi == 'ilk':
            if warehouse:
                # Depodan "Tamir Teslimatları" ara (Arıza: öneki olmayan)
                picking_type = self.env['stock.picking.type'].search([
                    ('name', '=', 'Tamir Teslimatları'),
                    ('name', 'not ilike', 'Arıza:'),
                    ('warehouse_id', '=', warehouse.id)
                ], limit=1)
            
            # Depo bulunamazsa, genel 'Tamir Teslimatları' ara (Arıza: öneki olmayan)
            if not picking_type:
                picking_type = self.env['stock.picking.type'].search([
                    ('name', '=', 'Tamir Teslimatları'),
                    ('name', 'not ilike', 'Arıza:')
                ], limit=1)
        
        # 2. transfer için depo bazlı 'Tamir Alımlar' ara
        elif transfer_tipi == 'ikinci':
            if warehouse:
                # Depodan "Tamir Alımlar" ara (Arıza: öneki olmayan)
                picking_type = self.env['stock.picking.type'].search([
                    ('name', '=', 'Tamir Alımlar'),
                    ('name', 'not ilike', 'Arıza:'),
                    ('warehouse_id', '=', warehouse.id)
                ], limit=1)
            
            # Depo bulunamazsa, genel 'Tamir Alımlar' ara (Arıza: öneki olmayan)
            if not picking_type:
                picking_type = self.env['stock.picking.type'].search([
                    ('name', '=', 'Tamir Alımlar'),
                    ('name', 'not ilike', 'Arıza:')
                ], limit=1)
        
        # Operasyon tipi bulunamazsa hata ver
        if not picking_type:
            raise UserError(_("Transfer oluşturulamadı: Uygun operasyon tipi bulunamadı!"))

        # Analitik hesap adından E-İrsaliye türünü belirle
        edespatch_number_sequence_id = False
        if self.analitik_hesap_id and self.analitik_hesap_id.name:
            # Analitik hesap adını temizle
            analitik_adi = self.analitik_hesap_id.name
            if analitik_adi.startswith("Perakende - "):
                analitik_adi = analitik_adi[12:]  # "Perakende - " önekini temizle
            
            # E-İrsaliye türünü bul (örnek: "ADANA - E-İrsaliye", "UNIQ - E-İrsaliye")
            # Önce tam eşleşme dene: "UNIQ - E-İrsaliye"
            edespatch_sequence = self.env['ir.sequence'].search([
                ('active', '=', True),
                ('company_id', '=', self.env.company.id),
                ('code', 'in', ['stock.edespatch', 'stock.ereceipt']),
                ('name', '=', f"{analitik_adi} - E-İrsaliye")
            ], limit=1)
            
            # Tam eşleşme bulunamazsa, ilike ile ara ama daha spesifik
            if not edespatch_sequence:
                # Önce analitik hesap adı ile başlayan ve "E-İrsaliye" içeren kayıtları ara
                all_sequences = self.env['ir.sequence'].search([
                    ('active', '=', True),
                    ('company_id', '=', self.env.company.id),
                    ('code', 'in', ['stock.edespatch', 'stock.ereceipt']),
                    ('name', 'ilike', 'E-İrsaliye')
                ])
                
                # Analitik hesap adı ile en yakın eşleşmeyi bul
                for seq in all_sequences:
                    # Eğer sequence adı analitik hesap adını içeriyorsa
                    if analitik_adi.upper() in seq.name.upper():
                        edespatch_sequence = seq
                        break
            
            if edespatch_sequence:
                edespatch_number_sequence_id = edespatch_sequence.id

        # Transfer oluştur - try-except ile güvenlik hatası yakalama
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': kaynak.id,
            'location_dest_id': hedef.id,
            'origin': self.name,
            'analytic_account_id': self.analitik_hesap_id.id if self.analitik_hesap_id else False,
        }
        
        # E-İrsaliye türü varsa ekle
        if edespatch_number_sequence_id:
            picking_vals['edespatch_number_sequence'] = edespatch_number_sequence_id
        # İkinci transferde güvenlik kısıtı nedeniyle note alanına yazma
        if transfer_tipi != 'ikinci':
            picking_vals['note'] = (
                f"Arıza Kaydı: {self.name}\nÜrün: {self.urun}\nModel: {self.model}\nTransfer Metodu: {self.transfer_metodu}"
            )
        
        # Adres mantığı:
        # İlk transfer: Gönderen = Mağaza analitik hesap adresi, Gönderi = Teknik servis/tedarikçi adresi
        # İkinci transfer: Gönderen = Teknik servis/tedarikçi adresi, Gönderi = Mağaza analitik hesap adresi
        
        # Analitik hesap adresini al (mağaza adresi)
        magaza_partner = False
        if self.analitik_hesap_id and self.analitik_hesap_id.partner_id:
            magaza_partner = self.analitik_hesap_id.partner_id
        
        # Teknik servis/tedarikçi partner'ını al
        teknik_servis_partner = False
        if self.teknik_servis == TeknikServis.TEDARIKCI and self.tedarikci_id:
            teknik_servis_partner = self.tedarikci_id
        else:
            # Partner bulma - Helper kullanımı (DTL, Zuhal için)
            teknik_servis_partner = partner_helper.PartnerHelper.get_partner_by_teknik_servis(
                self.env, self.teknik_servis
            )
        
        # Eğer mağaza ürünü, işlem tipi arıza kabul ve teknik servis TEDARİKÇİ ise contact_id kullan (sadece 1. transfer için)
        if transfer_tipi != 'ikinci' and self.islem_tipi == IslemTipi.ARIZA_KABUL and self.ariza_tipi == ArizaTipi.MAGAZA and self.teknik_servis == TeknikServis.TEDARIKCI and self.contact_id:
            teknik_servis_partner = self.contact_id
        
        # Transfer tipine göre partner_id ve adresleri ayarla
        if transfer_tipi == 'ilk':
            # İlk transfer: Gönderen = Mağaza, Gönderi = Teknik servis/tedarikçi
            if teknik_servis_partner:
                picking_vals['partner_id'] = teknik_servis_partner.id
        elif transfer_tipi == 'ikinci':
            # İkinci transfer: Gönderen = Teknik servis/tedarikçi, Gönderi = Mağaza
            if magaza_partner:
                picking_vals['partner_id'] = magaza_partner.id
        else:
            # Varsayılan: partner_id'yi teknik servis/tedarikçi olarak ayarla
            if teknik_servis_partner:
                picking_vals['partner_id'] = teknik_servis_partner.id
        
        # Nakliye bilgilerini ekle
        # Kargo şirketini bul (ücretsiz kargo)
        delivery_carrier = transfer_helper.TransferHelper.get_delivery_carrier(
            self.env
        )
        if delivery_carrier:
            picking_vals['carrier_id'] = delivery_carrier.id
            
        # Araç bilgisi ekle - basit yöntem
        if self.vehicle_id:
            picking_vals['vehicle_id'] = self.vehicle_id.id
        
        # Sürücü ataması - System parameter'dan alınan default driver ID kullanılıyor
        driver_id = self._get_default_driver_id()
        driver_partner = self.env['res.partner'].browse(driver_id)
        if not driver_partner.exists():
            driver_partner = False
            _logger.warning(f"Default sürücü (ID {driver_id}) bulunamadı: {self.name}")
        
        # 2. transferde note alanına yazma (güvenlik kısıtı nedeniyle atlanır)

        try:
            # Arıza modülünden oluşturulan transferler için context ekle (Matbu ayarı için)
            picking = self.env['stock.picking'].with_context(from_ariza_onarim=True).sudo().create(picking_vals)
        except Exception as e:
            # Güvenlik hatası alırsa, daha geniş yetki ile dene
            try:
                picking = self.env['stock.picking'].with_context(from_ariza_onarim=True, force_company=self.env.company.id).sudo().create(picking_vals)
            except Exception as e2:
                raise UserError(_(f"Transfer oluşturulamadı: Güvenlik kısıtlaması! Hata: {str(e2)}"))
        
        # Sürücü ataması - Standart Odoo davranışı (create sonrası)
        # driver_ids One2many ilişki olduğu için vehicle_id ile birlikte eklenmeli
        if driver_partner and picking:
            try:
                # driver_ids'e kayıt ekle (One2many için (0, 0, {}) formatı)
                # vehicle_id varsa kullan, yoksa driver_partner'ı vehicle_id olarak kullan (fallback)
                vehicle_id_val = False
                if hasattr(picking, 'vehicle_id') and picking.vehicle_id:
                    vehicle_id_val = picking.vehicle_id.id
                elif hasattr(driver_partner, 'vehicle_id') and driver_partner.vehicle_id:
                    vehicle_id_val = driver_partner.vehicle_id.id
                else:
                    # vehicle_id zorunluysa, driver_partner'ı vehicle_id olarak kullan (fallback)
                    vehicle_id_val = driver_partner.id
                
                # Önce driver_ids field'ının varlığını kontrol et
                if not hasattr(picking, 'driver_ids'):
                    _logger.error(f"driver_ids field'ı bulunamadı: {self.name} - Transfer: {picking.name}")
                    return picking
                
                # driver_ids One2many ise bu format kullanılmalı
                _logger.info(f"Sürücü ataması yapılıyor: {self.name} - Sürücü ID: {driver_partner.id} - Vehicle ID: {vehicle_id_val}")
                picking.sudo().write({
                    'driver_ids': [(0, 0, {
                        'driver_id': driver_partner.id,
                        'vehicle_id': vehicle_id_val,  # Otomatik ID ataması
                    })]
                })
                _logger.info(f"Sürücü ataması başarılı: {self.name} - Transfer: {picking.name}")
            except Exception as e:
                # Hata durumunda detaylı logla
                _logger.error(f"Sürücü ataması başarısız: {self.name} - Transfer: {picking.name if picking else 'Yok'} - Sürücü: {driver_partner.name if driver_partner else 'Bulunamadı'} - Hata: {str(e)} - Hata Tipi: {type(e).__name__}")
                # Hata mesajını chatter'a da ekle
                try:
                    picking.message_post(body=f"⚠️ Sürücü ataması yapılamadı: {str(e)}", message_type='notification')
                except Exception as chatter_error:
                    _logger.warning(f"Chatter mesajı eklenemedi (sürücü ataması hatası): {str(chatter_error)} - Transfer: {picking.name if picking else 'N/A'}")
        
        # Ürün hareketi ekle - try-except ile hata yakalama
        try:
            move_vals = {
                'name': self.urun or self.magaza_urun_id.name,
                'product_id': self.magaza_urun_id.id,
                'product_uom_qty': 1,
                'product_uom': self.magaza_urun_id.uom_id.id,
                'picking_id': picking.id,
                'location_id': kaynak.id,
                'location_dest_id': hedef.id,
                'company_id': self.env.company.id,
            }
            
            # Analitik hesap varsa ekle
            if self.analitik_hesap_id:
                move_vals['analytic_account_id'] = self.analitik_hesap_id.id
                
            self.env['stock.move'].sudo().create(move_vals)
        except Exception as e:
            # Eğer stock.move oluşturma hatası alırsa, picking'i sil ve hata ver
            try:
                picking.sudo().unlink()
                _logger.info(f"Başarısız transfer silindi: {picking.name if picking else 'N/A'}")
            except Exception as unlink_error:
                _logger.error(f"Başarısız transfer silinemedi: {picking.name if picking else 'N/A'} - {str(unlink_error)}")
            raise UserError(_(f"Transfer oluşturulamadı: {str(e)}"))

        # Chatter'a mesaj ekle (2. transfer için picking linki vermeyelim)
        transfer_url = f"/web#id={picking.id}&model=stock.picking&view_type=form"
        transfer_no_html = f'<a href="{transfer_url}">{picking.name}</a>'
        durum = dict(self._fields['state'].selection).get(self.state, self.state)
        sms_bilgi = 'Aktif' if self.sms_gonderildi else 'Deaktif'
        self.message_post(
            body=f"<b>Yeni transfer oluşturuldu!</b><br/>"
                 f"Transfer No: {transfer_no_html}<br/>"
                 f"Kaynak: {kaynak.display_name}<br/>"
                 f"Hedef: {hedef.display_name}<br/>"
                 f"Tarih: {fields.Date.today()}<br/>"
                 f"Durum: {durum}<br/>"
                 f"SMS Gönderildi: {sms_bilgi}",
            message_type='notification'
        )
        return picking

    def _send_sms_to_customer(self, message):
        # Sadece müşteri ürünü işlemlerinde SMS gönder
        if self.ariza_tipi != ArizaTipi.MUSTERI:
            return
            
        # SMS gönderme - Helper kullanımı - sudo() ile herkes SMS gönderebilsin
        # self.sudo().env ile sudo environment kullan
        sms_sent = sms_helper.SMSHelper.send_sms(
            self.sudo().env, self.partner_id, message, self.name
        )
        if sms_sent:
            self.sms_gonderildi = True  # SMS gönderildi flag'ini set et
            self.message_post(body=f"SMS başarıyla gönderildi: {message}", message_type='notification')
            

    # NOT: _create_delivery_order fonksiyonu kaldırıldı
    # Bu fonksiyon sale modülüne bağımlıydı ve hiçbir yerde kullanılmıyordu
    # Eğer gelecekte gerekirse, sale modülü bağımlılığı eklenmeli ve
    # demo verilere referans yerine gerçek ürün ID'si kullanılmalıdır

    def action_personel_onayla(self):
        """Personel onaylama işlemi - Hem ilk transfer hem de 2. transfer için çalışır"""
        for record in self:
            # İlk transfer için (draft durumundan)
            if record.state == ArizaStates.DRAFT:
                record.state = ArizaStates.PERSONEL_ONAY
                
                # Personel onayı sonrası otomatik transfer oluştur (mağaza ürünleri için)
                if record.ariza_tipi == ArizaTipi.MAGAZA and not record.transfer_id:
                    # Mağaza ürünü ve teknik servis tedarikçi ise transferi tedarikçiye oluştur
                    if record.teknik_servis == TeknikServis.TEDARIKCI:
                        if not record.tedarikci_id:
                            raise UserError('Tedarikçi seçimi zorunludur!')
                        # Tedarikçi stok konumu yoksa varsayılan konum kullan
                        hedef_konum = record.tedarikci_id.property_stock_supplier
                        if not hedef_konum:
                            # Varsayılan tedarikçi konumu bul
                            hedef_konum = record.env['stock.location'].search([
                                ('usage', '=', 'supplier'),
                                ('company_id', '=', record.company_id.id)
                            ], limit=1)
                            if not hedef_konum:
                                raise UserError('Tedarikçi stok konumu bulunamadı!')
                        picking = record._create_stock_transfer(hedef_konum=hedef_konum, transfer_tipi='ilk')
                        if picking:
                            record.transfer_id = picking.id
                            # Transfer oluşturulduğunda transfer'e yönlendir
                            return {
                                'type': 'ir.actions.act_window',
                                'name': 'Transfer Belgesi',
                                'res_model': 'stock.picking',
                                'res_id': picking.id,
                                'view_mode': 'form',
                                'context': {'hide_note': True},
                                'target': 'current',
                            }
                    # Diğer teknik servisler için normal transfer oluştur
                    elif record.teknik_servis != TeknikServis.MAGAZA:
                        picking = record._create_stock_transfer(transfer_tipi='ilk')
                        if picking:
                            record.transfer_id = picking.id
                            # Transfer oluşturulduğunda transfer'e yönlendir
                            return {
                                'type': 'ir.actions.act_window',
                                'name': 'Transfer Belgesi',
                                'res_model': 'stock.picking',
                                'res_id': picking.id,
                                'view_mode': 'form',
                                'context': {'hide_note': True},
                                'target': 'current',
                            }
                
                # Personel onayı sonrası SMS ve E-posta gönder (İlk SMS)
                if record.islem_tipi == IslemTipi.ARIZA_KABUL and record.ariza_tipi == ArizaTipi.MUSTERI and not record.ilk_sms_gonderildi:
                    message = SMSTemplates.ILK_SMS.format(
                        musteri_adi=record.partner_id.name or '',
                        urun=record.urun or '',
                        kayit_no=record.name or ''
                    )
                    # sudo() ile herkes SMS gönderebilsin
                    record.sudo()._send_sms_to_customer(message)
                    record.sudo().ilk_sms_gonderildi = True
                    record.sudo().sms_gonderildi = True  # SMS gönderildi flag'ini de set et
                
                
                # Arıza kayıtları görünümüne dön
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Arıza Kayıtları',
                    'res_model': 'ariza.kayit',
                    'view_mode': 'tree,form',
                    'target': 'current',
                }
            
            # 2. transfer için (onaylandi durumundan)
            elif record.state == ArizaStates.ONAYLANDI:
                # 2. transfer oluştur - Kaynak ve hedef konumları yer değiştir
                # Mevcut transfer_id'yi kullanmadan, doğrudan konumları belirle
                if record.kaynak_konum_id and record.hedef_konum_id:
                    # 2. transfer: Kaynak ve hedef yer değiştirir
                    picking = record._create_stock_transfer(
                        kaynak_konum=record.hedef_konum_id,  # İlk transferin hedefi (teknik servis)
                        hedef_konum=record.kaynak_konum_id,  # İlk transferin kaynağı (mağaza)
                        transfer_tipi='ikinci'
                    )
                    
                    if picking:
                        record.transfer_sayisi = record.transfer_sayisi + 1
                        # Güvenlik kısıtı nedeniyle picking formuna yönlendirme yapma, arıza kaydında kal
                        return {
                            'type': 'ir.actions.act_window',
                            'name': 'Arıza Kaydı',
                            'res_model': 'ariza.kayit',
                            'res_id': record.id,
                            'view_mode': 'form',
                            'target': 'current',
                        }
                    else:
                        raise UserError(_("2. transfer oluşturulamadı! Lütfen kaynak ve hedef konumları kontrol edin."))
                else:
                    raise UserError(_('Kaynak ve hedef konumları eksik! Lütfen konumları kontrol edin.'))
                
                # Tamamla işlemi sonrası SMS ve E-posta gönder (İkinci SMS)
                # NOT: Bu kod artık kullanılmıyor, 2. SMS "Hazır" butonu ile gönderiliyor
                # Ancak eski kod uyumluluğu için şablon kullanımına güncellendi
                if record.islem_tipi == IslemTipi.ARIZA_KABUL and record.ariza_tipi == ArizaTipi.MUSTERI and not record.ikinci_sms_gonderildi:
                    magaza_adi = record.magaza_urun_id.name if record.magaza_urun_id else ''
                    temiz_magaza_adi = record._clean_magaza_adi(magaza_adi) if magaza_adi else ''
                    message = SMSTemplates.IKINCI_SMS.format(
                        musteri_adi=record.partner_id.name or '',
                        urun=record.urun or '',
                        magaza_adi=temiz_magaza_adi or '',
                        kayit_no=record.name or ''
                    )
                    record._send_sms_to_customer(message)
                    record.ikinci_sms_gonderildi = True
                

    def action_kabul_et(self):
        """Kabul etme işlemi - Sadece yöneticiler için, PERSONEL_ONAY'dan KABUL_EDILDI'ye geçiş"""
        current_user = self.env.user
        
        # Sadece yöneticiler kullanabilir
        if not current_user.has_group('ariza_onarim.group_ariza_manager'):
            raise UserError(_('Bu işlemi sadece yetkili kullanıcılar yapabilir.'))
        
        for record in self:
            if record.state == ArizaStates.PERSONEL_ONAY:
                record.state = ArizaStates.KABUL_EDILDI
                # Kabul edildi bildirimi
                record.message_post(
                    body=f"Arıza kaydı kabul edildi. Kabul eden: {current_user.name}",
                    subject="Arıza Kaydı Kabul Edildi",
                    message_type='notification'
                )
                _logger.info(f"Arıza kaydı kabul edildi: {record.name} - Kullanıcı: {current_user.login}")
            else:
                raise UserError(_('Sadece personel onayı aşamasındaki kayıtlar kabul edilebilir.'))

    def action_teknik_onarim_baslat(self):
        """Teknik ekip onarım başlatma işlemi"""
        for record in self:
            if record.state == ArizaStates.KABUL_EDILDI:
                record.state = ArizaStates.TEKNIK_ONARIM
                # Teknik onarım başlatma bildirimi
                record.message_post(
                    body=f"Teknik onarım süreci başlatıldı. Sorumlu: {record.sorumlu_id.name}",
                    subject="Teknik Onarım Başlatıldı",
                    message_type='notification'
                )
            elif record.state == ArizaStates.PERSONEL_ONAY:
                # Geriye dönük uyumluluk için (eski kayıtlar için)
                raise UserError(_('Önce "Kabul Et" butonuna basmanız gerekiyor.'))
            else:
                raise UserError(_('Sadece kabul edilmiş kayıtlar için onarım başlatılabilir.'))

    def action_onayla(self):
        """Final onaylama işlemi - Sadece teknik_onarim durumundan çalışır"""
        for record in self:
            if record.state != ArizaStates.TEKNIK_ONARIM:
                raise UserError('Sadece teknik onarım aşamasındaki kayıtlar onaylanabilir!')
            
            # Yönetici onarımı bitirdiğinde onarım bilgilerini doldurabilmesi için wizard aç
            return {
                'name': 'Onarım Bilgilerini Doldur',
                'type': 'ir.actions.act_window',
                'res_model': 'ariza.onarim.bilgi.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_ariza_id': self.id,
                    'default_musteri_adi': self.partner_id.name if self.partner_id else '',
                    'default_urun': self.urun,
                    'default_teslim_magazasi_id': self.teslim_magazasi_id.id if self.teslim_magazasi_id else False,
                    'default_onarim_bilgisi': self.onarim_bilgisi or '',
                    'default_garanti_kapsaminda_mi': self.garanti_kapsaminda_mi or GarantiKapsam.HAYIR,
                    'default_ucret_bilgisi': self.ucret_bilgisi or '',
                    'default_onarim_ucreti': self.onarim_ucreti or 0.0,
                }
            }

    def action_iptal(self):
        """Arıza kaydını iptal et"""
        # Transfer bitene döndüyse iptal edilemez
        if self.transfer_id and self.transfer_id.state == 'done':
            raise UserError(_('Transferi bitene dönen arıza kayıtları iptal edilemez!'))
        
        # İptal durumuna geç
        self.state = ArizaStates.IPTAL
        
        # İptal mesajı gönder
        self.message_post(
            body=_('Arıza kaydı iptal edildi.'),
            subject="Arıza Kaydı İptal Edildi",
            message_type='notification'
        )
        
        # Log kaydı
        _logger.info(f"Arıza kaydı iptal edildi: {self.name} - Kullanıcı: {self.env.user.login}")
        
        return True

    def action_kullanici_tamamla(self):
        """Kullanıcı tamamlama işlemi - Sadece tamamlandi durumundan çalışır"""
        for record in self:
            # Müşteri ürünü için Hazır butonuna basılmış mı kontrol et
            if record.ariza_tipi == ArizaTipi.MUSTERI and not record.hazir_basildi:
                raise UserError(
                    _("Teslim Et işlemi için önce 'Hazır' butonuna basmanız gerekmektedir!")
                )
            
            if record.state != ArizaStates.TAMAMLANDI:
                raise UserError('Sadece tamamlanmış kayıtlar teslim edilebilir!')
            
            # Teslim bilgilerini girmek için wizard aç
            return {
                'name': 'Teslim Alan Bilgisi',
                'type': 'ir.actions.act_window',
                'res_model': 'ariza.teslim.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_ariza_id': self.id,
                    'default_musteri_adi': self.partner_id.name if self.partner_id else '',
                    'default_urun': self.urun,
                }
            }


    


    def action_print(self):
        if self.transfer_metodu in [TransferMetodu.UCRETSIZ_KARGO, TransferMetodu.UCRETLI_KARGO] and self.transfer_id:
            # Önce "Kargo Çıktısı - A4" raporunu ara (Reporting Studio ile oluşturulmuş)
            kargo_a4_report = self.env['ir.actions.report'].search([
                ('model', '=', 'stock.picking'),
                ('report_name', '=', 'stock_picking.x_kargo_ciktisi_listesi_A4')
            ], limit=1)
            
            if kargo_a4_report:
                return kargo_a4_report.report_action(self.transfer_id)
            else:
                # Fallback: Standart kargo raporu
                return self.env.ref('stock.action_report_delivery').report_action(self.transfer_id)
        # Teknik servis adres bilgisi
        teknik_servis_adres = self.teknik_servis_adres
        ctx = dict(self.env.context)
        ctx['teknik_servis_adres'] = teknik_servis_adres
        return self.env.ref('ariza_onarim.action_report_ariza_kayit').with_context(ctx).report_action(self)

    def action_print_invoice(self):
        """
        Fatura kalemine ait faturayı açar (form view).
        Kullanıcı fatura formundan yazdırabilir.
        
        Returns:
            dict: Fatura form view action'ı
        """
        if not self.invoice_line_id:
            raise UserError(_('Fatura kalemi seçilmemiş!'))
        
        invoice = self.invoice_line_id.move_id
        if not invoice:
            raise UserError(_('Fatura kalemine ait fatura bulunamadı!'))
        
        # Fatura formunu aç - kullanıcı oradan yazdırabilir
        return {
            'type': 'ir.actions.act_window',
            'name': f'Fatura - {invoice.name}',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.onchange('magaza_urun_id')
    def _onchange_magaza_urun_id(self):
        if self.magaza_urun_id:
            self.urun = self.magaza_urun_id.name or ''
            self.model = self.magaza_urun_id.default_code or ''
            # Ürün seçilince marka otomatik gelsin
            if hasattr(self.magaza_urun_id, 'brand_id') and self.magaza_urun_id.brand_id:
                self.marka_id = self.magaza_urun_id.brand_id.id
                # Marka seçilince tedarikçi otomatik gelsin
                if self.marka_id:
                    marka = self.env['product.brand'].browse(self.marka_id)
                    if marka and marka.partner_id:
                        self.tedarikci_id = marka.partner_id.id
                        self._onchange_tedarikci()
            else:
                self.marka_id = False
                self.tedarikci_id = False
                self.tedarikci_adresi = False
                self.tedarikci_telefon = False
                self.tedarikci_email = False

    def action_print_delivery(self):
        if self.transfer_id:
            return self.env.ref('stock.action_report_delivery').report_action(self.transfer_id)
    
    def action_teslim_al(self):
        """Mağaza ürünü teslim al işlemi - Tamir Alımlar transferi oluşturur"""
        self.ensure_one()
        
        if self.ariza_tipi != ArizaTipi.MAGAZA:
            raise UserError('Bu işlem sadece mağaza ürünü işlemleri için kullanılabilir!')
        
        if self.state != ArizaStates.YONETICI_TAMAMLANDI:
            raise UserError('Bu işlem sadece yönetici tamamlandı durumundaki kayıtlar için kullanılabilir!')
        
        # İlk transferi bul
        ilk_transfer = self.env['stock.picking'].search([
            ('origin', '=', self.name),
            ('state', '=', 'done')
        ], order='create_date asc', limit=1)
        
        if not ilk_transfer:
            raise UserError('İlk transfer bulunamadı! Lütfen önce ilk transferin tamamlandığından emin olun.')
        
        # İlk transferin konumlarını al ve tam tersini yap
        # İlk transfer: Kaynak → Hedef
        # İkinci transfer: Hedef → Kaynak (tam tersi)
        kaynak_konum = ilk_transfer.location_dest_id  # İlk transferin hedefi, ikinci transferin kaynağı
        hedef_konum = ilk_transfer.location_id  # İlk transferin kaynağı, ikinci transferin hedefi
        
        if not kaynak_konum or not hedef_konum:
            raise UserError('İlk transferin konum bilgileri eksik! Lütfen ilk transferi kontrol edin.')
        
        # Tamir Alımlar transferi oluştur - İlk transferdeki gibi analitik hesap adından warehouse bul
        picking_type = False
        
        # Analitik hesap adını al ve "Perakende -" önekini temizle
        magaza_adi = ""
        if self.analitik_hesap_id and self.analitik_hesap_id.name:
            magaza_adi = self.analitik_hesap_id.name
            # "Perakende -" önekini temizle
            if magaza_adi.startswith("Perakende - "):
                magaza_adi = magaza_adi[MagicNumbers.PERAKENDE_PREFIX_LENGTH:]  # "Perakende - " önekini temizle

        # Depo bilgisini al - İlk transferdeki gibi
        warehouse = False
        if self.analitik_hesap_id and self.analitik_hesap_id.name:
            # Analitik hesap adından depo adını çıkar
            magaza_adi = self.analitik_hesap_id.name
            if magaza_adi.startswith("Perakende - "):
                magaza_adi = magaza_adi[12:]  # "Perakende - " önekini temizle
            
            # Özel durum: Temaworld için "Tema World" olarak ara
            depo_arama_adi = magaza_adi
            if magaza_adi.lower() in ['temaworld', 'tema world']:
                depo_arama_adi = 'Tema World'
            
            # Mağaza adına göre depo ara
            warehouse = self.env['stock.warehouse'].search([
                ('name', 'ilike', depo_arama_adi)
            ], limit=1)

        # Operasyon tipi seçimi - İlk transferdeki gibi depo bazlı 'Tamir Alımlar' ara
        if warehouse:
            # Depodan "Tamir Alımlar" ara (Arıza: öneki olmayan)
            picking_type = self.env['stock.picking.type'].search([
                ('name', '=', 'Tamir Alımlar'),
                ('name', 'not ilike', 'Arıza:'),
                ('warehouse_id', '=', warehouse.id)
            ], limit=1)
        
        # Depo bulunamazsa, genel 'Tamir Alımlar' ara (Arıza: öneki olmayan)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('name', '=', 'Tamir Alımlar'),
                ('name', 'not ilike', 'Arıza:')
            ], limit=1)
        
        if not picking_type:
            warehouse_name = warehouse.name if warehouse else 'Bilinmeyen'
            raise UserError(f'"{warehouse_name}: Tamir Alımlar" picking type bulunamadı! Lütfen sistem ayarlarını kontrol edin.')
        
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': kaynak_konum.id,  # İlk transferin hedefi
            'location_dest_id': hedef_konum.id,  # İlk transferin kaynağı
            'origin': self.name,
            'analytic_account_id': self.analitik_hesap_id.id if self.analitik_hesap_id else False,
            'scheduled_date': fields.Datetime.now(),
            'date': fields.Datetime.now(),
        }
        
        # Güvenlik kısıtı nedeniyle note alanına yazma
        
        # Teknik servise göre partner_id ayarla
        if self.teknik_servis == TeknikServis.TEDARIKCI and self.tedarikci_id:
            picking_vals['partner_id'] = self.tedarikci_id.id
        elif self.teknik_servis == TeknikServis.DTL_BEYOGLU:
            dtl_partner = self.env['res.partner'].search([('name', 'ilike', PartnerNames.DTL_ELEKTRONIK)], limit=1)
            if dtl_partner:
                picking_vals['partner_id'] = dtl_partner.id
        elif self.teknik_servis == TeknikServis.DTL_OKMEYDANI:
            dtl_partner = self.env['res.partner'].search([('name', 'ilike', PartnerNames.DTL_ELEKTRONIK)], limit=1)
            if dtl_partner:
                dtl_okmeydani = self.env['res.partner'].search([
                    ('parent_id', '=', dtl_partner.id),
                    ('name', 'ilike', TeknikServis.DTL_OKMEYDANI)
                ], limit=1)
                if dtl_okmeydani:
                    picking_vals['partner_id'] = dtl_okmeydani.id
                else:
                    picking_vals['partner_id'] = dtl_partner.id
        elif self.teknik_servis == TeknikServis.ZUHAL_ARIZA_DEPO:
            zuhal_partner = self.env['res.partner'].search([('name', 'ilike', PartnerNames.ZUHAL_DIS_TICARET)], limit=1)
            if zuhal_partner:
                zuhal_ariza = self.env['res.partner'].search([
                    ('parent_id', '=', zuhal_partner.id),
                    ('name', 'ilike', 'Arıza Depo')
                ], limit=1)
                if zuhal_ariza:
                    picking_vals['partner_id'] = zuhal_ariza.id
                else:
                    picking_vals['partner_id'] = zuhal_partner.id
        elif self.teknik_servis == TeknikServis.ZUHAL_NEFESLI:
            zuhal_partner = self.env['res.partner'].search([('name', 'ilike', PartnerNames.ZUHAL_DIS_TICARET)], limit=1)
            if zuhal_partner:
                zuhal_nefesli = self.env['res.partner'].search([
                    ('parent_id', '=', zuhal_partner.id),
                    ('name', 'ilike', 'Nefesli Arıza')
                ], limit=1)
                if zuhal_nefesli:
                    picking_vals['partner_id'] = zuhal_nefesli.id
                else:
                    picking_vals['partner_id'] = zuhal_partner.id
        
        # Sürücü ataması - System parameter'dan alınan default driver ID kullanılıyor
        driver_id = self._get_default_driver_id()
        driver_partner = self.env['res.partner'].browse(driver_id)
        if not driver_partner.exists():
            driver_partner = False
            _logger.warning(f"Default sürücü (ID {driver_id}) bulunamadı: {self.name}")
        
        # Tamir Alımlar transferini oluştur
        tamir_alim_transfer = self.env['stock.picking'].sudo().create(picking_vals)
        
        # Sürücü ataması - Standart Odoo davranışı (create sonrası)
        # driver_ids One2many ilişki olduğu için vehicle_id ile birlikte eklenmeli
        if driver_partner and tamir_alim_transfer:
            try:
                # driver_ids'e kayıt ekle (One2many için (0, 0, {}) formatı)
                # vehicle_id varsa kullan, yoksa driver_partner'ı vehicle_id olarak kullan (fallback)
                vehicle_id_val = False
                if hasattr(tamir_alim_transfer, 'vehicle_id') and tamir_alim_transfer.vehicle_id:
                    vehicle_id_val = tamir_alim_transfer.vehicle_id.id
                elif hasattr(driver_partner, 'vehicle_id') and driver_partner.vehicle_id:
                    vehicle_id_val = driver_partner.vehicle_id.id
                else:
                    # vehicle_id zorunluysa, driver_partner'ı vehicle_id olarak kullan (fallback)
                    vehicle_id_val = driver_partner.id
                
                # Önce driver_ids field'ının varlığını kontrol et
                if not hasattr(tamir_alim_transfer, 'driver_ids'):
                    _logger.error(f"driver_ids field'ı bulunamadı: {self.name} - Transfer: {tamir_alim_transfer.name}")
                    return tamir_alim_transfer
                
                # driver_ids One2many ise bu format kullanılmalı
                _logger.info(f"Sürücü ataması yapılıyor (Teslim Al): {self.name} - Sürücü ID: {driver_partner.id} - Vehicle ID: {vehicle_id_val}")
                tamir_alim_transfer.sudo().write({
                    'driver_ids': [(0, 0, {
                        'driver_id': driver_partner.id,
                        'vehicle_id': vehicle_id_val,  # Otomatik ID ataması
                    })]
                })
                _logger.info(f"Sürücü ataması başarılı (Teslim Al): {self.name} - Transfer: {tamir_alim_transfer.name}")
            except Exception as e:
                # Hata durumunda detaylı logla
                _logger.error(f"Sürücü ataması başarısız (Teslim Al): {self.name} - Transfer: {tamir_alim_transfer.name if tamir_alim_transfer else 'Yok'} - Sürücü: {driver_partner.name if driver_partner else 'Bulunamadı'} - Hata: {str(e)} - Hata Tipi: {type(e).__name__}")
                # Hata mesajını chatter'a da ekle
                try:
                    tamir_alim_transfer.message_post(body=f"⚠️ Sürücü ataması yapılamadı: {str(e)}", message_type='notification')
                except Exception as chatter_error:
                    _logger.warning(f"Chatter mesajı eklenemedi (teslim al sürücü ataması hatası): {str(chatter_error)} - Transfer: {tamir_alim_transfer.name if tamir_alim_transfer else 'N/A'}")
        
        # Transfer satırını oluştur - stock.move
        move_vals = {
            'name': f"{self.magaza_urun_id.name if self.magaza_urun_id else 'Bilinmeyen Ürün'} - {self.name}",
            'product_id': self.magaza_urun_id.id if self.magaza_urun_id else False,
            'product_uom_qty': 1.0,
            'product_uom': self.magaza_urun_id.uom_id.id if self.magaza_urun_id and self.magaza_urun_id.uom_id else False,
            'picking_id': tamir_alim_transfer.id,
            'location_id': kaynak_konum.id,
            'location_dest_id': hedef_konum.id,
        }
        
        if move_vals['product_id'] and move_vals['product_uom']:
            move = self.env['stock.move'].sudo().create(move_vals)
            
            # Hareket satırını oluştur - stock.move.line
            move_line_vals = {
                'move_id': move.id,
                'product_id': self.magaza_urun_id.id if self.magaza_urun_id else False,
                'product_uom_id': self.magaza_urun_id.uom_id.id if self.magaza_urun_id and self.magaza_urun_id.uom_id else False,
                'qty_done': 1.0,
                'location_id': kaynak_konum.id,
                'location_dest_id': hedef_konum.id,
                'picking_id': tamir_alim_transfer.id,
            }
            
            if move_line_vals['product_id'] and move_line_vals['product_uom_id']:
                self.env['stock.move.line'].sudo().create(move_line_vals)
            else:
                raise UserError(f"Hareket satırı oluşturulamadı: Ürün veya birim bilgisi eksik! Ürün: {self.magaza_urun_id.name if self.magaza_urun_id else 'Seçili değil'}")
        else:
            raise UserError(f"Transfer satırı oluşturulamadı: Ürün veya birim bilgisi eksik! Ürün: {self.magaza_urun_id.name if self.magaza_urun_id else 'Seçili değil'}")
        
        # Durumu tamamlandı olarak güncelle
        self.state = ArizaStates.TAMAMLANDI
        
        # Teslim bilgilerini güncelle
        self.teslim_alan = self.env.user.name
        self.teslim_notu = f"Ürün {fields.Datetime.now().strftime('%d.%m.%Y %H:%M')} tarihinde teslim alındı. Tamir Alımlar transferi oluşturuldu."
        
        # Mesaj gönder
        transfer_bilgisi = f"""
        <p><strong>Yeni transfer oluşturuldu!</strong></p>
        <p><strong>Transfer No:</strong> <a href="/web#id={tamir_alim_transfer.id}&model=stock.picking&view_type=form">{tamir_alim_transfer.name}</a></p>
        <p><strong>Kaynak:</strong> {kaynak_konum.name}</p>
        <p><strong>Hedef:</strong> {hedef_konum.name}</p>
        <p><strong>Tarih:</strong> {fields.Datetime.now().strftime('%Y-%m-%d')}</p>
        <p><strong>Durum:</strong> {tamir_alim_transfer.state}</p>
        <p><strong>SMS Gönderildi:</strong> Deaktif</p>
        """
        
        self.message_post(
            body=transfer_bilgisi,
            subject="Mağaza Ürünü Teslim Alındı - Tamir Alımlar Transferi Oluşturuldu",
            message_type='notification'
        )
        
        # Tamir Alımlar transferine yönlendir
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': tamir_alim_transfer.id,
            'view_mode': 'form',
            'context': {'hide_note': True},
            'target': 'current',
        } 

    def action_teslim_al_musteri(self):
        """Müşteri ürünü için Teslim Al butonu - 2. SMS gönderir"""
        # Hazır butonuna basıldı flag'ini set et
        self.hazir_basildi = True
        for record in self:
            if record.ariza_tipi != ArizaTipi.MUSTERI:
                raise UserError(_('Bu işlem sadece müşteri ürünü için kullanılabilir.'))
            
            if record.state != ArizaStates.TAMAMLANDI:
                raise UserError(_('Bu işlem sadece tamamlandı durumundaki kayıtlar için kullanılabilir.'))
            
            # 2. SMS gönderimi - Müşteriye teslim edilmeye hazır bilgisi
            if record.partner_id and (record.partner_id.mobile or record.partner_id.phone) and not record.ikinci_sms_gonderildi:
                # Mağaza adını temizle
                magaza_adi = record.teslim_magazasi_id.name if record.teslim_magazasi_id else ''
                temiz_magaza_adi = record._clean_magaza_adi(magaza_adi) if magaza_adi else ''
                
                message = SMSTemplates.IKINCI_SMS.format(
                    musteri_adi=record.partner_id.name or '',
                    urun=record.urun or '',
                    magaza_adi=temiz_magaza_adi or '',
                    kayit_no=record.name or ''
                )
                
                record._send_sms_to_customer(message)
                record.ikinci_sms_gonderildi = True
                
                # Chatter'a mesaj ekle
                record.message_post(
                    body=f"Teslim Al butonuna basıldı. Müşteriye 2. SMS gönderildi: {message}",
                    subject="Teslim Al - 2. SMS Gönderildi",
                    message_type='notification'
                )
            elif record.ikinci_sms_gonderildi:
                raise UserError(_('2. SMS zaten gönderilmiş. Tekrar gönderilemez.'))
            else:
                raise UserError(_('SMS gönderilemedi: Müşteri veya telefon bilgisi eksik.'))

    @api.onchange('teslim_magazasi_id')
    def _onchange_teslim_magazasi(self):
        if self.teslim_magazasi_id and self.teslim_magazasi_id.name in ['DTL OKMEYDANI', 'DTL BEYOĞLU']:
            self.teslim_adresi = 'MAHMUT ŞEVKET PAŞA MAH. ŞAHİNKAYA SOK NO 31 OKMEYDANI'
        else:
            self.teslim_adresi = False

    @api.onchange('sorumlu_id')
    def _onchange_sorumlu_id(self):
        """Sorumlu değiştiğinde analitik hesabı güncelle"""
        if self.sorumlu_id and self.sorumlu_id.employee_id and self.sorumlu_id.employee_id.magaza_id:
            self.analitik_hesap_id = self.sorumlu_id.employee_id.magaza_id.id

    @api.depends('partner_id')
    def _get_musteri_faturalari(self):
        for record in self:
            if record.partner_id:
                # Müşteriye ait gelen faturaları bul
                faturalar = self.env['account.move'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('move_type', '=', 'in_invoice'),
                    ('state', '=', 'posted'),
                    ('invoice_line_ids.product_id.type', '=', 'product')  # Sadece stok ürünleri
                ])
                record.musteri_faturalari = faturalar
            else:
                record.musteri_faturalari = False

    @api.onchange('transfer_metodu')
    def _onchange_transfer_metodu(self):
        """Transfer metodu değiştiğinde"""
        pass

    @api.onchange('fatura_kalem_id')
    def _onchange_fatura_kalem_id(self):
        if self.fatura_kalem_id:
            self.urun = self.fatura_kalem_id.product_id.name
            self.model = self.fatura_kalem_id.product_id.default_code
            # Ürünün marka bilgisini al
            if self.fatura_kalem_id.product_id.brand_id:
                self.marka_id = self.fatura_kalem_id.product_id.brand_id.id
            else:
                self.marka_id = False

    @api.depends('teknik_servis', 'tedarikci_id', 'tedarikci_adresi')
    def _compute_teknik_servis_adres(self):
        for rec in self:
            if rec.teknik_servis == 'TEDARİKÇİ' and rec.tedarikci_id:
                # Önce tedarikci_adresi alanını kontrol et, yoksa partner'ın adres bilgilerini kullan
                if rec.tedarikci_adresi:
                    rec.teknik_servis_adres = rec.tedarikci_adresi
                else:
                    # Partner'ın adres bilgilerini birleştir
                    adres_parcalari = []
                    if rec.tedarikci_id.street:
                        adres_parcalari.append(rec.tedarikci_id.street)
                    if rec.tedarikci_id.street2:
                        adres_parcalari.append(rec.tedarikci_id.street2)
                    if rec.tedarikci_id.city:
                        adres_parcalari.append(rec.tedarikci_id.city)
                    if rec.tedarikci_id.state_id:
                        adres_parcalari.append(rec.tedarikci_id.state_id.name)
                    if rec.tedarikci_id.zip:
                        adres_parcalari.append(rec.tedarikci_id.zip)
                    if rec.tedarikci_id.country_id:
                        adres_parcalari.append(rec.tedarikci_id.country_id.name)
                    
                    rec.teknik_servis_adres = ', '.join(adres_parcalari) if adres_parcalari else ''
            elif rec.teknik_servis == TeknikServis.ZUHAL_ARIZA_DEPO:
                rec.teknik_servis_adres = 'Halkalı merkez mh. Dereboyu cd. No:8/B'
            elif rec.teknik_servis == TeknikServis.DTL_BEYOGLU:
                rec.teknik_servis_adres = 'Şahkulu mh. Nakkas çıkmazı No: 1/1 No:10-46 / 47'
            elif rec.teknik_servis == TeknikServis.DTL_OKMEYDANI:
                rec.teknik_servis_adres = 'MAHMUT ŞEVKET PAŞA MAH. ŞAHİNKAYA SOK NO 31 OKMEYDANI'
            elif rec.teknik_servis == TeknikServis.ZUHAL_NEFESLI:
                rec.teknik_servis_adres = 'Şahkulu, Galip Dede Cd. No:33, 34421 Beyoğlu/İstanbul'
            elif rec.teknik_servis == TeknikServis.PROHAN_ELK:
                rec.teknik_servis_adres = 'ÜÇGEN MAH. 107 SK NO: 7/1, Antalya, 07040'
            elif rec.teknik_servis == TeknikServis.NGAUDIO:
                rec.teknik_servis_adres = 'Orta mahalle kuzu sokak no22 A, ADAPAZARI, Sakarya, 54100'
            elif rec.teknik_servis == TeknikServis.MATT_GUITAR:
                rec.teknik_servis_adres = 'HASANPASA MAH. ALIBEY SOK. 21/A, KADIKÖY, İstanbul, 34000'
            elif rec.teknik_servis == TeknikServis.ERK_ENSTRUMAN:
                rec.teknik_servis_adres = 'KOCATEPE MAH İNKLAP SOK ÖZSOY APT NO:31/1, ÇANKAYA, Ankara, 06000'
            else:
                rec.teknik_servis_adres = ''

    @api.depends('teknik_servis', 'tedarikci_id')
    def _compute_teknik_servis_telefon(self):
        for rec in self:
            if rec.teknik_servis == TeknikServis.TEDARIKCI and rec.tedarikci_id:
                rec.teknik_servis_telefon = rec.tedarikci_id.phone or rec.tedarikci_id.mobile or ''
            elif rec.teknik_servis == TeknikServis.ZUHAL_ARIZA_DEPO:
                rec.teknik_servis_telefon = '0212 555 55 55'
            elif rec.teknik_servis == TeknikServis.DTL_BEYOGLU:
                rec.teknik_servis_telefon = '0212 555 55 56'
            elif rec.teknik_servis == TeknikServis.DTL_OKMEYDANI:
                rec.teknik_servis_telefon = '0212 555 55 57'
            elif rec.teknik_servis == TeknikServis.ZUHAL_NEFESLI:
                rec.teknik_servis_telefon = '0212 555 55 58'
            else:
                rec.teknik_servis_telefon = ''

    def action_lock(self):
        for rec in self:
            rec.state = ArizaStates.KILITLI

    def action_unlock(self):
        for rec in self:
            rec.state = ArizaStates.DRAFT

    def _clean_magaza_adi(self, magaza_adi):
        """Mağaza adından 'Perakende - ' önekini temizle"""
        if magaza_adi and magaza_adi.startswith("Perakende - "):
            return magaza_adi[12:]  # "Perakende - " uzunluğu 12 karakter
        return magaza_adi




    @api.depends('partner_id')
    def _compute_musteri_telefon(self):
        for rec in self:
            rec.musteri_telefon = rec.partner_id.phone or rec.partner_id.mobile or ''
    
    @api.depends('ariza_tipi', 'partner_id', 'analitik_hesap_id')
    def _compute_musteri_gosterim(self):
        """List görünümünde müşteri bilgisini gösterir"""
        for rec in self:
            if rec.ariza_tipi == ArizaTipi.MUSTERI and rec.partner_id:
                rec.musteri_gosterim = rec.partner_id.name
            elif rec.ariza_tipi == ArizaTipi.MAGAZA:
                # Mağaza ürünü için analitik hesap adından mağaza adını al
                if rec.analitik_hesap_id and rec.analitik_hesap_id.name:
                    magaza_adi = rec.analitik_hesap_id.name
                    # "Perakende - " önekini temizle
                    if magaza_adi.startswith("Perakende - "):
                        magaza_adi = magaza_adi[MagicNumbers.PERAKENDE_PREFIX_LENGTH:]
                    rec.musteri_gosterim = f"{magaza_adi} Mağaza Ürünü"
                else:
                    rec.musteri_gosterim = "Mağaza Ürünü"
            else:
                rec.musteri_gosterim = ''
    
    
    @api.depends('magaza_urun_id')
    def _compute_magaza_urun_adi(self):
        """Mağaza ürünü için ürün adını hesapla"""
        for record in self:
            if record.magaza_urun_id:
                urun_adi = record.magaza_urun_id.name or ''
                urun_kodu = record.magaza_urun_id.default_code or ''
                if urun_kodu:
                    record.magaza_urun_adi = f"[{urun_kodu}] {urun_adi}"
                else:
                    record.magaza_urun_adi = urun_adi
            else:
                record.magaza_urun_adi = ''

    @api.model
    def _cron_update_kalan_sure(self):
        """
        Günlük cron job - Kalan iş günü ve süre gösterimini günceller
        Bu metod her gün çalıştırılarak kalan süre bilgilerini güncel tutar
        """
        # Henüz tamamlanmamış kayıtları al (beklenen tamamlanma tarihi olan veya olmayan)
        records = self.search([
            ('state', 'not in', ['teslim_edildi'])
        ])
        
        if records:
            # Önce beklenen tamamlanma tarihini güncelle (onarım başlangıç tarihi olmayanlar için)
            records.invalidate_cache(['beklenen_tamamlanma_tarihi'])
            records._compute_beklenen_tamamlanma_tarihi()
            
            # Sonra kalan süreleri güncelle
            records.invalidate_cache(['kalan_is_gunu', 'kalan_sure_gosterimi'])
            records._compute_kalan_is_gunu()
            records._compute_kalan_sure_gosterimi()
            _logger.info(f"Kalan süre güncellendi: {len(records)} kayıt")



class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        # Önce normal transfer doğrulama işlemini yap
        result = super().button_validate()
        
        # Sadece arıza kayıtlarıyla ilişkili transferler için özel işlem yap
        # Origin field'ı arıza kayıt numarası formatında mı kontrol et (örn: "ARZ-2024-001")
        for picking in self:
            if picking.origin and picking.state == 'done':
                # Sadece arıza kayıt numarası formatındaki origin'ler için kontrol et
                # Arıza kayıt numaraları genellikle "ARZ-" ile başlar veya belirli bir pattern'e sahiptir
                ariza = self.env['ariza.kayit'].search([('name', '=', picking.origin)], limit=1)
                if ariza:
                    # Transfer sayısını artır
                    ariza.transfer_sayisi += 1
                    
                    # Sadece arıza kayıtlarından gelen transferler için arıza kaydına dön
                    # Diğer transferler için normal davranışı sürdür
                    if len(self) == 1:  # Tek bir transfer doğrulanıyorsa
                        return {
                            'type': 'ir.actions.act_window',
                            'res_model': 'ariza.kayit',
                            'res_id': ariza.id,
                            'view_mode': 'form',
                            'target': 'current',
                        }
        
        # Normal davranışı sürdür (modül dışı transferler için)
        return result 


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'
    
    vehicle_id = fields.Many2one('res.partner', string='Araç No', domain="[('is_driver','=',True)]")

