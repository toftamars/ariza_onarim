from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import os
import logging

_logger = logging.getLogger(__name__)

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'
    
    partner_id = fields.Many2one('res.partner', string='Partner')
    adres = fields.Text(string='Adres')
    telefon = fields.Char(string='Telefon')
    email = fields.Char(string='E-posta')

    @api.model
    def _setup_zuhal_addresses(self):
        """Zuhal Dış Ticaret A.Ş. carisine ait adresleri analitik hesaplarla eşleştir"""
        zuhal_partner = self.env['res.partner'].search([('name', '=', 'Zuhal Dış Ticaret A.Ş.')], limit=1)
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

    name = fields.Char(string='Arıza No', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    transfer_id = fields.Many2one('stock.picking', string='Transfer', readonly=True)
    islem_tipi = fields.Selection([
        ('kabul', 'Arıza Kabul'),
    ], string='İşlem Tipi', required=True, tracking=True)
    ariza_tipi = fields.Selection([
        ('musteri', 'Müşteri Ürünü'),
        ('magaza', 'Mağaza Ürünü')
    ], string='Arıza Tipi', required=True, tracking=True)
    teknik_servis = fields.Selection([
        ('DTL BEYOĞLU', 'DTL BEYOĞLU'),
        ('DTL OKMEYDANI', 'DTL OKMEYDANI'),
        ('ZUHAL ARIZA DEPO', 'ZUHAL ARIZA DEPO'),
        ('MAĞAZA', 'MAĞAZA'),
        ('ZUHAL NEFESLİ', 'ZUHAL NEFESLİ'),
        ('TEDARİKÇİ', 'TEDARİKÇİ')
    ], string='Teknik Servis')
    transfer_metodu = fields.Selection([
        ('arac', 'Araç'),
        ('ucretsiz_kargo', 'Ücretsiz Kargo'),
        ('ucretli_kargo', 'Ücretli Kargo'),
        ('magaza', 'Mağaza'),
    ], string='Transfer Metodu', tracking=True, default='arac')
    partner_id = fields.Many2one('res.partner', string='Müşteri', tracking=True)
    analitik_hesap_id = fields.Many2one('account.analytic.account', string='Analitik Hesap', tracking=True, required=True)
    kaynak_konum_id = fields.Many2one('stock.location', string='Kaynak Konum', tracking=True, domain="[('company_id', '=', company_id)]")
    hedef_konum_id = fields.Many2one('stock.location', string='Hedef Konum', tracking=True, domain="[('company_id', '=', company_id)]")
    tedarikci_id = fields.Many2one('res.partner', string='Tedarikçi', tracking=True)
    marka_id = fields.Many2one('product.brand', string='Marka', tracking=True)
    marka_manu = fields.Char(string='Marka (Manuel)', tracking=True)
    tedarikci_adresi = fields.Text(string='Teslim Adresi', tracking=True)
    tedarikci_telefon = fields.Char(string='Tedarikçi Telefon', tracking=True)
    tedarikci_email = fields.Char(string='Tedarikçi E-posta', tracking=True)
    sorumlu_id = fields.Many2one('res.users', string='Sorumlu', default=lambda self: self.env.user, tracking=True)
    tarih = fields.Date(string='Tarih', default=fields.Date.context_today, tracking=True)
    state = fields.Selection([
        ('draft', 'Taslak'),
        ('personel_onay', 'Personel Onayı'),
        ('teknik_onarim', 'Teknik Onarım'),
        ('onaylandi', 'Onaylandı'),
        ('tamamlandi', 'Tamamlandı'),
        ('teslim_edildi', 'Teslim Edildi'),
        ('kilitli', 'Kilitli'),
        ('iptal', 'İptal'),
    ], string='Durum', default='draft', tracking=True)
    siparis_yok = fields.Boolean(string='Sipariş Yok', default=False)
    invoice_line_id = fields.Many2one('account.move.line', string='Fatura Kalemi', 
        domain="[('move_id.partner_id', '=', partner_id), ('product_id.type', '=', 'product')]",
        tracking=True)
    fatura_tarihi = fields.Date(string='Fatura Tarihi', compute='_compute_fatura_tarihi', store=True)
    urun = fields.Char(string='Ürün', required=True)
    model = fields.Char(string='Model', required=True)
    garanti_suresi = fields.Char(string='Garanti Süresi', compute='_compute_garanti_suresi', store=True, tracking=True)
    garanti_bitis_tarihi = fields.Date(string='Garanti Bitiş Tarihi', compute='_compute_garanti_suresi', store=True)
    kalan_garanti = fields.Char(string='Kalan Garanti', compute='_compute_garanti_suresi', store=True)
    garanti_kapsaminda_mi = fields.Selection([
        ('evet', 'Evet'),
        ('hayir', 'Hayır'),
    ], string='Garanti Kapsamında mı?', tracking=True)
    ariza_tanimi = fields.Text(string='Arıza Tanımı', tracking=True)
    notlar = fields.Text(string='Notlar')
    transfer_irsaliye = fields.Char(string='Transfer İrsaliye No')
    company_id = fields.Many2one('res.company', string='Şirket', default=lambda self: self.env.company)
    onarim_ucreti = fields.Float(string='Onarım Ücreti', tracking=True)
    yapilan_islemler = fields.Text(string='Yapılan İşlemler', tracking=True)
    marka_urunleri_ids = fields.Many2many(
        'product.product',
        string='Marka Ürünleri',
        tracking=True
    )
    ariza_kabul_id = fields.Many2one('ariza.kayit', string='Arıza Kabul No', domain="[('islem_tipi', '=', 'kabul')]", tracking=True)
    onarim_bilgisi = fields.Text(string='Onarım Bilgisi', tracking=True)
    ucret_bilgisi = fields.Char(string='Ücret Bilgisi', tracking=True)
    magaza_urun_id = fields.Many2one(
        'product.product',
        string='Ürün',
        tracking=True
    )
    sms_gonderildi = fields.Boolean(string='SMS Gönderildi', default=False, tracking=True)
    teslim_magazasi_id = fields.Many2one('account.analytic.account', string='Teslim Mağazası', tracking=True)
    teslim_adresi = fields.Char(string='Teslim Adresi', tracking=True)
    musteri_faturalari = fields.Many2many('account.move', string='Müşteri Faturaları')
    teknik_servis_adres = fields.Char(string='Teknik Servis Adresi', compute='_compute_teknik_servis_adres', store=False)
    teslim_alan = fields.Char(string='Teslim Alan')
    teslim_alan_tc = fields.Char(string='Teslim Alan TC')
    teslim_alan_telefon = fields.Char(string='Teslim Alan Telefon')
    teslim_alan_imza = fields.Binary(string='Teslim Alan İmza')
    teslim_notu = fields.Text(string='Teslim Notu', tracking=True)
    contact_id = fields.Many2one('res.partner', string='Kontak (Teslimat Adresi)', tracking=True)
    vehicle_id = fields.Many2one('res.partner', string='Sürücü', domain="[('is_driver','=',True)]", tracking=True)
    
    # Onarım Süreci Takibi
    onarim_baslangic_tarihi = fields.Date(string='Onarım Başlangıç Tarihi', tracking=True)
    beklenen_tamamlanma_tarihi = fields.Date(string='Beklenen Tamamlanma Tarihi', compute='_compute_beklenen_tamamlanma_tarihi', store=True)
    kalan_is_gunu = fields.Integer(string='Kalan İş Günü', compute='_compute_kalan_is_gunu', store=True)
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
    state_manager = fields.Selection([
        ('draft', 'Taslak'),
        ('onaylandi', 'Onaylandı'),
        ('onarimda', 'Onarımda'),
        ('onarim_tamamlandi', 'Onarım Tamamlandı'),
        ('tamamlandi', 'Tamamlandı'),
        ('teslim_edildi', 'Teslim Edildi'),
        ('kilitli', 'Kilitli'),
        ('iptal', 'İptal'),
    ], string='Durum (Yönetici)', compute='_compute_state_manager', store=False)
    
    # Transfer sayısı takibi
    transfer_sayisi = fields.Integer(string='Transfer Sayısı', default=0, tracking=True)

    @api.depends('state')
    def _compute_state_manager(self):
        """Yönetici için özel durum gösterimi - personel_onay durumunu onaylandı, teknik_onarim durumunu onarımda, onaylandi durumunu onarım tamamlandı olarak göster"""
        for record in self:
            if record.state == 'personel_onay':
                record.state_manager = 'onaylandi'
            elif record.state == 'teknik_onarim':
                record.state_manager = 'onarimda'
            elif record.state == 'onaylandi':
                record.state_manager = 'onarim_tamamlandi'
            else:
                record.state_manager = record.state

    @api.depends('sorumlu_id')
    def _compute_user_permissions(self):
        """Kullanıcının yetkilerini kontrol et"""
        for record in self:
            current_user = self.env.user
            
            # Onaylayabilen kullanıcılar (personel + yönetici)
            approve_users = ['admin', 'alper.tofta@zuhalmuzik.com', 'personel1', 'personel2']  # Personel kullanıcıları
            record.can_approve = (current_user.login in approve_users or 
                                current_user.has_group('base.group_system') or
                                current_user.has_group('ariza_onarim.group_ariza_manager'))
            
            # Onarımı başlatabilen kullanıcılar (sadece yönetici)
            repair_users = ['admin', 'alper.tofta@zuhalmuzik.com']  # Yönetici kullanıcıları
            record.can_start_repair = (current_user.login in repair_users or 
                                     current_user.has_group('base.group_system') or
                                     current_user.has_group('ariza_onarim.group_ariza_technician'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Sorumlu kişinin analitik bilgisini al
            if not vals.get('analitik_hesap_id') and vals.get('sorumlu_id'):
                sorumlu = self.env['res.users'].browse(vals['sorumlu_id'])
                if sorumlu and sorumlu.employee_id and sorumlu.employee_id.magaza_id:
                    vals['analitik_hesap_id'] = sorumlu.employee_id.magaza_id.id
            # Varsayılan değerleri ayarla
            if not vals.get('name'):
                try:
                    vals['name'] = self.env['ir.sequence'].next_by_code('ariza.kayit')
                except:
                    # Sequence bulunamazsa manuel numara oluştur
                    import datetime
                    current_year = datetime.datetime.now().year
                    last_record = self.search([('name', '!=', False)], order='id desc', limit=1)
                    if last_record and last_record.name != 'New':
                        try:
                            last_number = int(last_record.name.split('/')[-1])
                            new_number = last_number + 1
                        except:
                            new_number = 1
                    else:
                        new_number = 1
                    vals['name'] = f"ARZ/{current_year}/{new_number:05d}"
            if not vals.get('state'):
                vals['state'] = 'draft'
            if not vals.get('islem_tipi'):
                vals['islem_tipi'] = 'kabul'
            if not vals.get('ariza_tipi'):
                vals['ariza_tipi'] = 'musteri'
            if not vals.get('sorumlu_id'):
                vals['sorumlu_id'] = self.env.user.id
        
        records = super().create(vals_list)
        
        # Yeni oluşturulan kayıtlar için e-posta bildirimi gönder
        for record in records:
            try:
                record._send_new_ariza_notification()
            except Exception as e:
                _logger.error(f"E-posta gönderimi başarısız: {record.name} - {str(e)}")
        
        return records

    def _send_new_ariza_notification(self):
        """Yeni arıza kaydı oluşturulduğunda e-posta bildirimi gönder"""
        try:
            # E-posta şablonunu bul
            template = self.env.ref('ariza_onarim.email_template_yeni_ariza_bildirimi')
            if template:
                # E-postayı gönder
                template.send_mail(self.id, force_send=True)
                _logger.info(f"Yeni arıza kaydı bildirimi gönderildi: {self.name}")
            else:
                _logger.error(f"E-posta şablonu bulunamadı: ariza_onarim.email_template_yeni_ariza_bildirimi")
        except Exception as e:
            _logger.error(f"E-posta bildirimi gönderilemedi: {str(e)}")
            # Alternatif olarak basit e-posta gönder
            self._send_simple_notification()
    
    def _send_simple_notification(self):
        """Basit e-posta bildirimi gönder"""
        try:
            from odoo.tools.misc import format_date
            
            subject = f"Yeni Arıza Kaydı - {self.name}"
            body = f"""
            <h2>Yeni Arıza Kaydı Oluşturuldu</h2>
            <p><strong>Arıza No:</strong> {self.name}</p>
            <p><strong>Tarih:</strong> {format_date(self.env, self.tarih) if self.tarih else 'Belirtilmemiş'}</p>
            <p><strong>Müşteri:</strong> {self.partner_id.name if self.partner_id else 'Belirtilmemiş'}</p>
            <p><strong>Ürün:</strong> {self.urun if self.urun else 'Belirtilmemiş'}</p>
            <p><strong>Model:</strong> {self.model if self.model else 'Belirtilmemiş'}</p>
            <p><strong>Teknik Servis:</strong> {self.teknik_servis if self.teknik_servis else 'Belirtilmemiş'}</p>
            <p><strong>Sorumlu:</strong> {self.sorumlu_id.name if self.sorumlu_id else 'Belirtilmemiş'}</p>
            <p><strong>Durum:</strong> {dict(self._fields['state'].selection).get(self.state, self.state)}</p>
            """
            
            # E-posta gönder
            self.env['mail.mail'].create({
                'subject': subject,
                'email_from': self.env.user.email_formatted,
                'email_to': 'alper.tofta@zuhalmuzik.com',
                'body_html': body,
                'auto_delete': True,
            }).send()
            
            _logger.info(f"Basit e-posta bildirimi gönderildi: {self.name}")
        except Exception as e:
            _logger.error(f"Basit e-posta gönderilemedi: {str(e)}")

    def _send_onarim_hatirlatma(self):
        """Onarım süreci hatırlatma e-postası gönder"""
        try:
            # E-posta şablonunu bul
            template = self.env.ref('ariza_onarim.email_template_onarim_hatirlatma')
            if template:
                # E-postayı gönder
                template.send_mail(self.id, force_send=True)
                self.hatirlatma_gonderildi = True
                self.son_hatirlatma_tarihi = fields.Date.today()
                _logger.info(f"Onarım hatırlatma e-postası gönderildi: {self.name}")
        except Exception as e:
            _logger.error(f"Onarım hatırlatma e-postası gönderilemedi: {str(e)}")

    @api.model
    def _check_onarim_deadlines(self):
        """Günlük olarak onarım süreçlerini kontrol et ve hatırlatma gönder"""
        from datetime import datetime, timedelta
        
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
            # Kalan süre kontrolü
            if kayit.kalan_is_gunu <= 3:  # 3 iş günü veya daha az kaldıysa
                kayit._send_onarim_hatirlatma()
                _logger.info(f"Onarım hatırlatma gönderildi: {kayit.name} - Kalan süre: {kayit.kalan_is_gunu} gün")

    def action_onayla_kullanici_bazli(self):
        """Kullanıcı bazlı onay sistemi - Onarım sürecini aktif hale getirir"""
        current_user = self.env.user
        
        # Onaylayabilen kullanıcılar (personel + teknik ekip)
        approve_users = ['admin', 'alper.tofta@zuhalmuzik.com', 'personel1', 'personel2']
        
        if current_user.login not in approve_users and not current_user.has_group('base.group_system'):
            raise UserError(_('Bu işlemi sadece yetkili kullanıcılar yapabilir.'))
        
        # Arıza kaydını onayla
        self.state = 'onaylandi'
        self.message_post(body=_('Arıza kaydı onaylandı ve onarım süreci aktif hale getirildi.'))
        _logger.info(f"Arıza kaydı onaylandı: {self.name} - Kullanıcı: {current_user.login}")

    def action_onarim_baslat(self):
        """Onarım sürecini başlat - Sadece teknik ekip"""
        current_user = self.env.user
        
        # Onarımı başlatabilen kullanıcılar (sadece teknik ekip)
        repair_users = ['admin', 'alper.tofta@zuhalmuzik.com']
        
        if current_user.login not in repair_users and not current_user.has_group('base.group_system'):
            raise UserError(_('Bu işlemi sadece teknik ekip yapabilir.'))
        
        if self.state != 'onaylandi':
            raise UserError(_('Sadece onaylanmış arıza kayıtları için onarım başlatılabilir.'))
        
        # Onarım sürecini başlat
        self.onarim_baslangic_tarihi = fields.Date.today()
        self.onarim_durumu = 'devam_ediyor'
        self.message_post(body=_('Onarım süreci başlatıldı.'))
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
                garanti_ay = 24
                
                # Ürünün garanti süresi varsa onu kullan
                if record.invoice_line_id.product_id and hasattr(record.invoice_line_id.product_id, 'garanti_suresi'):
                    garanti_ay = record.invoice_line_id.product_id.garanti_suresi or 24
                
                # Garanti bitiş tarihini hesapla
                from dateutil.relativedelta import relativedelta
                garanti_bitis = record.fatura_tarihi + relativedelta(months=garanti_ay)
                record.garanti_bitis_tarihi = garanti_bitis
                
                # Garanti süresini metin olarak ayarla
                record.garanti_suresi = f"{garanti_ay} ay"
                
                # Kalan garanti süresini hesapla
                from datetime import datetime
                bugun = datetime.now().date()
                if garanti_bitis > bugun:
                    kalan_gun = (garanti_bitis - bugun).days
                    kalan_ay = kalan_gun // 30
                    kalan_gun_kalan = kalan_gun % 30
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

    @api.depends('onarim_baslangic_tarihi')
    def _compute_beklenen_tamamlanma_tarihi(self):
        """Onarım başlangıç tarihinden 20 iş günü sonrasını hesapla"""
        for record in self:
            if record.onarim_baslangic_tarihi:
                # 20 iş günü sonrasını hesapla (hafta sonları hariç)
                from datetime import datetime, timedelta
                from dateutil.relativedelta import relativedelta
                
                baslangic = record.onarim_baslangic_tarihi
                is_gunu_sayisi = 0
                hedef_tarih = baslangic
                
                while is_gunu_sayisi < 20:
                    hedef_tarih += timedelta(days=1)
                    # Hafta sonu değilse iş günü say
                    if hedef_tarih.weekday() < 5:  # 0-4 = Pazartesi-Cuma
                        is_gunu_sayisi += 1
                
                record.beklenen_tamamlanma_tarihi = hedef_tarih
            else:
                record.beklenen_tamamlanma_tarihi = False

    @api.depends('onarim_baslangic_tarihi', 'beklenen_tamamlanma_tarihi')
    def _compute_kalan_is_gunu(self):
        """Bugünden itibaren kalan iş günü sayısını hesapla"""
        for record in self:
            if record.beklenen_tamamlanma_tarihi:
                from datetime import datetime, timedelta
                
                bugun = datetime.now().date()
                hedef_tarih = record.beklenen_tamamlanma_tarihi
                
                if hedef_tarih <= bugun:
                    # Süre dolmuş
                    record.kalan_is_gunu = 0
                    if record.onarim_durumu != 'tamamlandi':
                        record.onarim_durumu = 'gecikti'
                else:
                    # Kalan iş günü sayısını hesapla
                    kalan_gun = 0
                    current_date = bugun
                    
                    while current_date < hedef_tarih:
                        current_date += timedelta(days=1)
                        if current_date.weekday() < 5:  # Hafta sonu değilse
                            kalan_gun += 1
                    
                    record.kalan_is_gunu = kalan_gun
                    
                    # Onarım durumunu güncelle
                    if kalan_gun <= 5 and record.onarim_durumu == 'beklemede':
                        record.onarim_durumu = 'devam_ediyor'
            else:
                record.kalan_is_gunu = 0

    @api.onchange('ariza_tipi')
    def _onchange_ariza_tipi(self):
        if self.ariza_tipi == 'musteri':
            self.partner_id = False
            self.urun = False
            self.model = False
            self.teslim_magazasi_id = False
            self.teslim_adresi = False
            self.transfer_id = False
        elif self.ariza_tipi == 'magaza':
            self.partner_id = False
            self.urun = False
            self.model = False
            self.teslim_magazasi_id = self.env.user.employee_id.magaza_id
            if self.teslim_magazasi_id and self.teslim_magazasi_id.name in ['DTL OKMEYDANI', 'DTL BEYOĞLU']:
                self.teslim_adresi = 'MAHMUT ŞEVKET PAŞA MAH. ŞAHİNKAYA SOK NO 31 OKMEYDANI'
        elif self.ariza_tipi == 'teknik':
            self.partner_id = False
            self.urun = False
            self.model = False
            self.teslim_magazasi_id = False
            self.teslim_adresi = False

    @api.onchange('teknik_servis')
    def _onchange_teknik_servis(self):
        if not self.analitik_hesap_id:
            return

        # Analitik hesaba ait stok konumunu bul
        dosya_yolu = os.path.join(os.path.dirname(__file__), '..', 'Analitik Bilgileri.txt')
        hesap_adi = self.analitik_hesap_id.name.strip().lower()
        konum_kodu = None
        try:
            with open(dosya_yolu, 'r', encoding='utf-8') as f:
                for satir in f:
                    if hesap_adi in satir.lower():
                        parcalar = satir.strip().split('\t')
                        if len(parcalar) == 2:
                            konum_kodu = parcalar[1]
                            break
        except Exception as e:
            pass

        if konum_kodu:
            konum = self.env['stock.location'].search([
                ('name', '=', konum_kodu),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            if konum:
                self.kaynak_konum_id = konum

        # DTL Beyoğlu adresini otomatik ekle
        if self.teknik_servis == 'dtl_beyoglu':
            self.tedarikci_adresi = 'Şahkulu, Nakkaş Çk. No:1 D:1, 34420 Beyoğlu/İstanbul'
        # Zuhal adresini otomatik ekle
        elif self.teknik_servis == 'zuhal':
            self.tedarikci_adresi = 'Halkalı Merkez, 34303 Küçükçekmece/İstanbul'

        # Müşteri ürünü işlemleri için hedef konum ayarları
        if self.ariza_tipi == 'musteri':
            if self.teknik_servis == 'magaza' and konum_kodu:
                # Mağaza seçildiğinde [KOD]/arızalı konumu
                arizali_konum = self.env['stock.location'].search([
                    ('name', '=', f"{konum_kodu.split('/')[0]}/arızalı"),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if arizali_konum:
                    self.hedef_konum_id = arizali_konum
            elif self.teknik_servis in ['dtl_beyoglu', 'dtl_okmeydani']:
                # DTL seçildiğinde dtl/stok konumu
                dtl_konum = self.env['stock.location'].search([
                    ('name', '=', 'dtl/stok'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if dtl_konum:
                    self.hedef_konum_id = dtl_konum
            elif self.teknik_servis == 'zuhal':
                # Zuhal seçildiğinde arıza/stok konumu
                ariza_konum = self.env['stock.location'].search([
                    ('name', '=', 'arıza/stok'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if ariza_konum:
                    self.hedef_konum_id = ariza_konum
        # Mağaza ürünü ve teknik servis tedarikçi ise hedef konum tedarikçi konumu
        elif self.ariza_tipi == 'magaza' and self.teknik_servis == 'TEDARİKÇİ' and self.tedarikci_id:
            if self.tedarikci_id.property_stock_supplier:
                self.hedef_konum_id = self.tedarikci_id.property_stock_supplier

    @api.onchange('analitik_hesap_id')
    def _onchange_analitik_hesap_id(self):
        if self.analitik_hesap_id and self.ariza_tipi in ['magaza', 'teknik']:
            # Dosya yolu
            dosya_yolu = os.path.join(os.path.dirname(__file__), '..', 'Analitik Bilgileri.txt')
            hesap_adi = self.analitik_hesap_id.name.strip().lower()
            konum_kodu = None
            try:
                with open(dosya_yolu, 'r', encoding='utf-8') as f:
                    for satir in f:
                        if hesap_adi in satir.lower():
                            parcalar = satir.strip().split('\t')
                            if len(parcalar) == 2:
                                konum_kodu = parcalar[1]
                                break
            except Exception as e:
                pass  # Hata yönetimi eklenebilir

            if konum_kodu:
                konum = self.env['stock.location'].search([
                    ('name', '=', konum_kodu),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if konum:
                    self.kaynak_konum_id = konum

            # Tedarikçiye gönderim ise hedef konum tedarikçi adresi
            if self.teknik_servis == 'TEDARİKÇİ' and self.tedarikci_id:
                if self.tedarikci_id.property_stock_supplier:
                    self.hedef_konum_id = self.tedarikci_id.property_stock_supplier
            # Teknik servis ise hedef konum DTL/Stok
            elif self.teknik_servis in ['DTL BEYOĞLU', 'DTL OKMEYDANI']:
                dtl_konum = self.env['stock.location'].search([
                    ('name', '=', 'DTL/Stok'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if dtl_konum:
                    self.hedef_konum_id = dtl_konum

        # Analitik hesaptan adres bilgilerini al
        if self.analitik_hesap_id:
            if self.analitik_hesap_id.adres:
                self.teslim_adresi = self.analitik_hesap_id.adres
            if self.analitik_hesap_id.telefon:
                self.tedarikci_telefon = self.analitik_hesap_id.telefon
            if self.analitik_hesap_id.email:
                self.tedarikci_email = self.analitik_hesap_id.email

    @api.onchange('invoice_line_id')
    def _onchange_invoice_line_id(self):
        if self.invoice_line_id:
            product = self.invoice_line_id.product_id
            if product:
                if self.islem_tipi == 'kabul' and self.ariza_tipi == 'musteri' and not self.siparis_yok:
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
            self.tedarikci_adresi = self.tedarikci_id.street
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
        if self.islem_tipi != 'teslim':
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
                'partner_id', 'analitik_hesap_id', 'kaynak_konum_id', 'hedef_konum_id', 'tedarikci_id',
                'marka_id', 'tedarikci_adresi', 'tedarikci_telefon', 'tedarikci_email', 'urun', 'model',
                'fatura_tarihi', 'notlar', 'onarim_ucreti', 'yapilan_islemler', 'ariza_tanimi',
                'garanti_suresi', 'garanti_bitis_tarihi', 'kalan_garanti', 'transfer_metodu',
                'magaza_urun_id', 'marka_urunleri_ids', 'teknik_servis', 'onarim_bilgisi', 'ucret_bilgisi', 'garanti_kapsaminda_mi', 'ariza_tipi',
                'invoice_line_id', 'siparis_yok'
            ]
            for field in fields_to_copy:
                setattr(self, field, getattr(self.ariza_kabul_id, field, False))

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
                magaza_adi = magaza_adi[12:]  # "Perakende - " uzunluğu 12 karakter

        # Depo bilgisini al
        warehouse = False
        if self.analitik_hesap_id and self.analitik_hesap_id.name:
            # Analitik hesap adından depo adını çıkar
            magaza_adi = self.analitik_hesap_id.name
            if magaza_adi.startswith("Perakende - "):
                magaza_adi = magaza_adi[12:]  # "Perakende - " önekini temizle
            
            # Mağaza adına göre depo ara
            warehouse = self.env['stock.warehouse'].search([
                ('name', 'ilike', magaza_adi)
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

        # Transfer oluştur
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': kaynak.id,
            'location_dest_id': hedef.id,
            'origin': self.name,
            'note': f"Arıza Kaydı: {self.name}\nÜrün: {self.urun}\nModel: {self.model}\nTransfer Metodu: {self.transfer_metodu}",
            'analytic_account_id': self.analitik_hesap_id.id if self.analitik_hesap_id else False,
            'delivery_type': 'matbu',  # Her zaman matbu
        }
        
        # 2. transferde note alanına ilk transferin teslim_adresi bilgisini ekle
        if transfer_tipi == 'ikinci' and self.teslim_adresi:
            picking_vals['note'] += f"\nAlım Yapılan: {self.teslim_adresi}"
        
        # Eğer mağaza ürünü, işlem tipi kabul ve teknik servis TEDARİKÇİ ise partner_id'yi contact_id olarak ayarla (sadece 1. transfer için)
        if transfer_tipi != 'ikinci' and self.islem_tipi == 'kabul' and self.ariza_tipi == 'magaza' and self.teknik_servis == 'TEDARİKÇİ' and self.contact_id:
            picking_vals['partner_id'] = self.contact_id.id

        picking = self.env['stock.picking'].create(picking_vals)
        
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
                
            self.env['stock.move'].create(move_vals)
        except Exception as e:
            # Eğer stock.move oluşturma hatası alırsa, picking'i sil ve hata ver
            picking.unlink()
            raise UserError(_(f"Transfer oluşturulamadı: {str(e)}"))

        # Chatter'a mesaj ekle
        transfer_url = f"/web#id={picking.id}&model=stock.picking&view_type=form"
        durum = dict(self._fields['state'].selection).get(self.state, self.state)
        sms_bilgi = 'Aktif' if self.sms_gonderildi else 'Deaktif'
        self.message_post(
            body=f"<b>Yeni transfer oluşturuldu!</b><br/>"
                 f"Transfer No: <a href='{transfer_url}'>{picking.name}</a><br/>"
                 f"Kaynak: {kaynak.display_name}<br/>"
                 f"Hedef: {hedef.display_name}<br/>"
                 f"Tarih: {fields.Date.today()}<br/>"
                 f"Durum: {durum}<br/>"
                 f"SMS Gönderildi: {sms_bilgi}"
        )
        return picking

    def _send_sms_to_customer(self, message):
        # Sadece müşteri ürünü işlemlerinde SMS gönder
        if self.ariza_tipi != 'musteri':
            return
        if self.partner_id and self.partner_id.phone:
            try:
                sms_obj = self.env['sms.sms'].create({
                    'partner_id': self.partner_id.id,
                    'number': self.partner_id.phone,
                    'body': message,
                    'state': 'outgoing',
                })
                sms_obj.send()
            except Exception as e:
                # SMS yetkisi yoksa sadece sessizce geç, hata verme
                pass
        # SMS ile birlikte mail de gönder
        if self.partner_id and self.partner_id.email:
            subject = "Arıza Kaydınız Hakkında Bilgilendirme"
            self._send_email_to_customer(subject, message)

    def _send_email_to_customer(self, subject, body):
        if not self.partner_id or not self.partner_id.email:
            return
        template = self.env.ref('ariza_onarim.email_template_ariza_bilgilendirme', raise_if_not_found=False)
        if template:
            template.with_context(
                email_to=self.partner_id.email,
                email_subject=subject,
                email_body=body
            ).send_mail(self.id, force_send=True)
        else:
            # Template bulunamazsa manuel mail gönder
            self.env['mail.mail'].create({
                'subject': subject,
                'body_html': body,
                'email_to': self.partner_id.email,
                'auto_delete': True,
            }).send()

    def _create_delivery_order(self):
        if not self.partner_id or not self.analitik_hesap_id:
            return False

        # Kargo şirketini bul
        delivery_carrier = self.env['delivery.carrier'].search([
            ('delivery_type', '=', 'fixed'),
            ('fixed_price', '=', 0.0)
        ], limit=1)

        if not delivery_carrier:
            raise UserError(_("Ücretsiz kargo seçeneği bulunamadı."))

        # Satış siparişi oluştur
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'analytic_account_id': self.analitik_hesap_id.id,
            'carrier_id': delivery_carrier.id,
            'order_line': [(0, 0, {
                'name': f"Arıza Kaydı: {self.name}",
                'product_id': self.env.ref('product.product_product_4').id,  # Kargo ürünü
                'product_uom_qty': 1,
                'price_unit': 0.0,
            })],
        })

        # Satış siparişini onayla
        sale_order.action_confirm()

        # Teslimat siparişi oluştur
        picking = sale_order.picking_ids.filtered(lambda p: p.picking_type_code == 'outgoing')
        if picking:
            picking.write({
                'origin': self.name,
                'note': f"Arıza Kaydı: {self.name}\nÜrün: {self.urun}\nModel: {self.model}"
            })
            return picking
        return False

    def action_personel_onayla(self):
        """Personel onaylama işlemi"""
        for record in self:
            if record.state == 'draft':
                record.state = 'personel_onay'
                
                # Personel onayı sonrası otomatik transfer oluştur (mağaza ürünleri için)
                if record.ariza_tipi == 'magaza' and not record.transfer_id:
                    # Mağaza ürünü ve teknik servis tedarikçi ise transferi tedarikçiye oluştur
                    if record.teknik_servis == 'TEDARİKÇİ':
                        if not record.tedarikci_id or not record.tedarikci_id.property_stock_supplier:
                            raise UserError('Tedarikçi veya tedarikçi stok konumu eksik!')
                        picking = record._create_stock_transfer(hedef_konum=record.tedarikci_id.property_stock_supplier, transfer_tipi='ilk')
                        if picking:
                            record.transfer_id = picking.id
                            # Transfer oluşturulduğunda transfer'e yönlendir
                            return {
                                'type': 'ir.actions.act_window',
                                'name': 'Transfer Belgesi',
                                'res_model': 'stock.picking',
                                'res_id': picking.id,
                                'view_mode': 'form',
                                'target': 'current',
                            }
                    # Diğer teknik servisler için normal transfer oluştur
                    elif record.teknik_servis != 'MAĞAZA':
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
                                'target': 'current',
                            }
                
                # Personel onayı sonrası SMS gönder
                if record.islem_tipi == 'kabul' and record.ariza_tipi == 'musteri' and not record.sms_gonderildi:
                    message = f"Sayın {record.partner_id.name}., {record.urun} ürününüz teslim alındı, Ürününüz onarım sürecine alınmıştır. B021"
                    record._send_sms_to_customer(message)
                    record.sms_gonderildi = True
                
                # Personel onayında e-posta gönder
                mail_to = 'alper.tofta@zuhalmuzik.com'
                subject = f"Arıza Kaydı Personel Onayı: {record.name}"
                body = f"""
Arıza Kaydı Personel Onaylandı.<br/>
<b>Arıza No:</b> {record.name}<br/>
<b>Müşteri:</b> {record.partner_id.name if record.partner_id else '-'}<br/>
<b>Ürün:</b> {record.urun}<br/>
<b>Model:</b> {record.model}<br/>
<b>Arıza Tanımı:</b> {record.ariza_tanimi or '-'}<br/>
<b>Tarih:</b> {record.tarih or '-'}<br/>
<b>Teknik Servis:</b> {record.teknik_servis or '-'}<br/>
<b>Teknik Servis Adresi:</b> {record.teknik_servis_adres or '-'}<br/>
"""
                record.env['mail.mail'].create({
                    'subject': subject,
                    'body_html': body,
                    'email_to': mail_to,
                }).send()

    def action_teknik_onarim_baslat(self):
        """Teknik ekip onarım başlatma işlemi"""
        for record in self:
            if record.state == 'personel_onay':
                record.state = 'teknik_onarim'
                # Teknik onarım başlatma bildirimi
                record.message_post(
                    body=f"Teknik onarım süreci başlatıldı. Sorumlu: {record.sorumlu_id.name}",
                    subject="Teknik Onarım Başlatıldı"
                )

    def action_onayla(self):
        """Final onaylama işlemi - Sadece teknik_onarim durumundan çalışır"""
        for record in self:
            if record.state != 'teknik_onarim':
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
                    'default_onarim_bilgisi': self.onarim_bilgisi or '',
                    'default_garanti_kapsaminda_mi': self.garanti_kapsaminda_mi or 'hayir',
                    'default_ucret_bilgisi': self.ucret_bilgisi or '',
                    'default_onarim_ucreti': self.onarim_ucreti or 0.0,
                }
            }

    def action_print(self):
        if self.transfer_metodu in ['ucretsiz_kargo', 'ucretli_kargo'] and self.transfer_id:
            return self.env.ref('stock.action_report_delivery').report_action(self.transfer_id)
        # Teknik servis adres bilgisi
        teknik_servis_adres = self.teknik_servis_adres
        ctx = dict(self.env.context)
        ctx['teknik_servis_adres'] = teknik_servis_adres
        return self.env.ref('ariza_onarim.action_report_ariza_kayit').with_context(ctx).report_action(self)

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
                rec.teknik_servis_adres = rec.tedarikci_adresi or rec.tedarikci_id.street or ''
            elif rec.teknik_servis == 'ZUHAL ARIZA DEPO':
                rec.teknik_servis_adres = 'Halkalı merkez mh. Dereboyu cd. No:8/B'
            elif rec.teknik_servis == 'DTL BEYOĞLU':
                rec.teknik_servis_adres = 'Şahkulu mh. Nakkas çıkmazı No: 1/1 No:10-46 / 47'
            elif rec.teknik_servis == 'DTL OKMEYDANI':
                rec.teknik_servis_adres = 'MAHMUT ŞEVKET PAŞA MAH. ŞAHİNKAYA SOK NO 31 OKMEYDANI'
            elif rec.teknik_servis == 'ZUHAL NEFESLİ':
                rec.teknik_servis_adres = 'Şahkulu, Galip Dede Cd. No:33, 34421 Beyoğlu/İstanbul'
            else:
                rec.teknik_servis_adres = ''

    def action_lock(self):
        for rec in self:
            rec.state = 'kilitli'

    def action_unlock(self):
        for rec in self:
            rec.state = 'draft'

    def _clean_magaza_adi(self, magaza_adi):
        """Mağaza adından 'Perakende - ' önekini temizle"""
        if magaza_adi and magaza_adi.startswith("Perakende - "):
            return magaza_adi[12:]  # "Perakende - " uzunluğu 12 karakter
        return magaza_adi

    def action_tamamla(self):
        # Yönetici henüz "Onarımı Tamamla" yapmamışsa uyarı ver
        if self.state != 'onaylandi':
            raise UserError(_('Bu işlemi yapabilmek için önce yöneticinin "Onarımı Tamamla" işlemini yapması gerekiyor!'))
        
        # İlk transfer doğrulandıktan sonra tamamla butonu olsun
        if self.transfer_id:
            # 2. transfer oluştur - İlk transferin tam tersi
            mevcut_kaynak = self.transfer_id.location_id
            mevcut_hedef = self.transfer_id.location_dest_id
            
            # 2. transfer: Teknik servisten mağazaya geri dönüş
            yeni_transfer = self._create_stock_transfer(
                kaynak_konum=mevcut_hedef,  # Teknik servis (1. transferin hedefi)
                hedef_konum=mevcut_kaynak,  # Mağaza (1. transferin kaynağı)
                transfer_tipi='ikinci'      # 2. transfer olduğunu belirt
            )
            
            if yeni_transfer:
                # 2. transfer oluşturuldu
                # Arıza kaydını güncelle
                self.write({
                    'transfer_sayisi': self.transfer_sayisi + 1,
                })
                
                # SMS ve Email gönderimi
                if self.partner_id and (self.ariza_tipi == 'musteri' or self.ariza_tipi == 'magaza'):
                    if self.partner_id.phone:
                        # SMS gönderimi
                        if self.ariza_tipi == 'musteri':
                            sms_mesaji = f"Sayın {self.partner_id.name}., {self.urun} ürününüz teslim edilmeye hazırdır. Ürününüzü mağazamızdan teslim alabilirsiniz. B021"
                        else: # self.ariza_tipi == 'magaza'
                            sms_mesaji = f"Sayın {self.partner_id.name}., {self.urun} ürününüz teslim edilmiştir. B021"
                        
                        self._send_sms_to_customer(sms_mesaji)
                    
                    if self.partner_id.email:
                        # Email gönderimi
                        if self.ariza_tipi == 'musteri':
                            subject = f"Ürününüz Teslim Edilmeye Hazır: {self.name}"
                            body = f"""
                            Sayın {self.partner_id.name},
                            
                            {self.urun} ürününüz teslim edilmeye hazırdır. 
                            Ürününüzü mağazamızdan teslim alabilirsiniz.
                            
                            Arıza No: {self.name}
                            
                            Saygılarımızla,
                            B021
                            """
                        else: # self.ariza_tipi == 'magaza'
                            subject = f"Ürününüz Teslim Edildi: {self.name}"
                            body = f"""
                            Sayın {self.partner_id.name},
                            
                            {self.urun} ürününüz teslim edilmiştir.
                            
                            Arıza No: {self.name}
                            
                            Saygılarımızla,
                            B021
                            """
                        
                        self._send_email_to_customer(subject, body)
                
                # 2. transfer oluşturulduğunda transfer'e yönlendir (ilk transferdeki gibi)
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Transfer Belgesi',
                    'res_model': 'stock.picking',
                    'res_id': yeni_transfer.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            else:
                raise UserError(_("Transfer oluşturulamadı! Lütfen kaynak ve hedef konumları kontrol edin."))
        else:
            raise UserError(_('Transfer bulunamadı! Lütfen önce transfer oluşturun.'))

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        res = super().button_validate()
        # Origin alanı üzerinden arıza kaydını bul
        for picking in self:
            if picking.origin:
                ariza = self.env['ariza.kayit'].search([('name', '=', picking.origin)], limit=1)
                if ariza:
                    # Transfer sayısını artır
                    ariza.transfer_sayisi += 1
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'ariza.kayit',
                        'res_id': ariza.id,
                        'view_mode': 'form',
                        'target': 'current',
                    }
        return res 

