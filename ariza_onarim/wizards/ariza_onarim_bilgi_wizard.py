from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ArizaOnarimBilgiWizard(models.TransientModel):
    _name = 'ariza.onarim.bilgi.wizard'
    _description = 'Onarım Bilgilerini Doldurma Sihirbazı'

    ariza_id = fields.Many2one('ariza.kayit', string='Arıza Kaydı', required=True)
    partner_id = fields.Many2one('res.partner', string='Müşteri', readonly=True)
    musteri_adi = fields.Char(string='Müşteri Adı', readonly=True)
    urun = fields.Char(string='Ürün', readonly=True)
    ariza_tipi = fields.Selection([
        ('musteri', 'Müşteri Ürünü'),
        ('magaza', 'Mağaza Ürünü')
    ], string='Arıza Tipi', readonly=True)
    teslim_magazasi_id = fields.Many2one('account.analytic.account', string='Teslim Mağazası')
    adresime_gonderilsin = fields.Boolean(string='Adresime Gönderilsin', default=False)
    musteri_adresi_id = fields.Many2one('res.partner', string='Teslimat Adresi', 
                                       domain="[('type', 'in', ['delivery', 'contact'])]",
                                       attrs="{'invisible': [('adresime_gonderilsin', '=', False)], 'required': [('adresime_gonderilsin', '=', True)]}",
                                       context="{'default_type': 'delivery'}")
    onarim_bilgisi = fields.Text(string='Onarım Bilgisi', required=True)
    garanti_kapsaminda_mi = fields.Selection([
        ('evet', 'Evet'),
        ('hayir', 'Hayır'),
        ('urun_degisimi', 'Ürün Değişimi'),
    ], string='Garanti Kapsamında mı?', required=True)
    ucret_bilgisi = fields.Char(string='Ücret Bilgisi')
    onarim_ucreti = fields.Monetary(string='Onarım Ücreti', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Para Birimi', default=lambda self: self.env.company.currency_id)
    
    # 2. transfer bilgileri (Mağaza ürünü için)
    ikinci_transfer_kaynak = fields.Char(string='2. Transfer Kaynak', readonly=True)
    ikinci_transfer_hedef = fields.Char(string='2. Transfer Hedef', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self._context.get('active_id'):
            ariza = self.env['ariza.kayit'].browse(self._context['active_id'])
            res.update({
                'ariza_id': ariza.id,
                'partner_id': ariza.partner_id.id if ariza.partner_id else False,
                'musteri_adi': ariza.partner_id.name if ariza.partner_id else '',
                'urun': ariza.urun if ariza.urun else '',
                'ariza_tipi': ariza.ariza_tipi,
                'teslim_magazasi_id': ariza.teslim_magazasi_id.id if ariza.teslim_magazasi_id else False,
            })
            
            # Mağaza ürünü için 2. transfer bilgilerini hesapla
            if ariza.ariza_tipi == 'magaza':
                # 1. transferin bilgilerini al
                birinci_transfer = self.env['stock.picking'].search([
                    ('origin', '=', ariza.name),
                    ('picking_type_code', '=', 'outgoing')  # İlk transfer çıkış transferi
                ], limit=1)
                
                if birinci_transfer:
                    # 2. transfer kaynağı = 1. transfer hedefi
                    ikinci_kaynak = birinci_transfer.location_dest_id.complete_name if birinci_transfer.location_dest_id else 'Teknik Servis'
                    
                    # 2. transfer hedefi = 1. transfer kaynağı
                    ikinci_hedef = birinci_transfer.location_id.complete_name if birinci_transfer.location_id else 'Mağaza'
                else:
                    # 1. transfer bulunamazsa varsayılan değerler
                    ikinci_kaynak = ariza.teknik_servis if ariza.teknik_servis else 'Teknik Servis'
                    ikinci_hedef = ariza.teslim_magazasi_id.name if ariza.teslim_magazasi_id else 'Mağaza'
                
                res.update({
                    'ikinci_transfer_kaynak': ikinci_kaynak,
                    'ikinci_transfer_hedef': ikinci_hedef,
                })
        return res

    def _temizle_magaza_adi(self, magaza_adi):
        """Mağaza adından 'Perakende' ifadesini kaldır"""
        if magaza_adi:
            # "Perakende" ifadesini kaldır
            temiz_adi = magaza_adi.replace('Perakende ', '').replace(' Perakende', '')
            return temiz_adi
        return magaza_adi

    def action_onarim_bilgilerini_kaydet(self):
        """Onarım bilgilerini kaydet ve durumu güncelle"""
        ariza = self.ariza_id
        
        # Onarım bilgilerini güncelle
        ariza.onarim_bilgisi = self.onarim_bilgisi
        ariza.garanti_kapsaminda_mi = self.garanti_kapsaminda_mi
        ariza.ucret_bilgisi = self.ucret_bilgisi
        
        # Garanti kapsamında olan durumlarda onarım ücreti sıfırla
        if self.garanti_kapsaminda_mi in ['evet', 'urun_degisimi']:
            ariza.onarim_ucreti = 0.0
        else:
            ariza.onarim_ucreti = self.onarim_ucreti
        
        # Teslim mağazasını güncelle (müşteri ürünü için)
        if self.ariza_tipi == 'musteri':
            if self.adresime_gonderilsin and self.musteri_adresi_id:
                # Adrese gönderim seçildi
                ariza.teslim_magazasi_id = False
                ariza.teslim_adresi = self.musteri_adresi_id.street or ''
            elif self.teslim_magazasi_id:
                # Mağazadan teslim seçildi
                ariza.teslim_magazasi_id = self.teslim_magazasi_id.id
        
        # Durumu güncelle - Adrese gönderim seçildiyse direkt teslim edildi durumuna geç
        if self.ariza_tipi == 'musteri' and self.adresime_gonderilsin and self.musteri_adresi_id:
            ariza.state = 'teslim_edildi'
            # Adrese gönderim için teslim bilgilerini güncelle
            ariza.teslim_alan = 'Adrese Gönderim'
            ariza.teslim_adresi = self.musteri_adresi_id.street or ''
        else:
            ariza.state = 'tamamlandi'
        
        # SMS gönderimi - Müşteriye onarım tamamlandı bilgisi (İkinci SMS)
        if ariza.partner_id and ariza.partner_id.phone and not ariza.ikinci_sms_gonderildi:
            if ariza.ariza_tipi == 'musteri':
                # Müşteri ürünü için onarım tamamlandı SMS'i
                if self.adresime_gonderilsin and self.musteri_adresi_id:
                    # Adrese gönderim
                    sms_mesaji = f"Sayın {ariza.partner_id.name}. {ariza.name}, {ariza.urun} ürününüzün onarımı tamamlanmıştır. Ürününüz adresinize gönderilecektir. B021"
                else:
                    # Mağazadan teslim
                    magaza_adi = self.teslim_magazasi_id.name if self.teslim_magazasi_id else ''
                    temiz_magaza_adi = self._temizle_magaza_adi(magaza_adi)
                    sms_mesaji = f"Sayın {ariza.partner_id.name}. {ariza.name}, {ariza.urun} ürününüzün onarımı tamamlanmıştır. Ürününüzü {temiz_magaza_adi} mağazamızdan 3 (üç) iş günü sonra teslim alabilirsiniz. B021"
            else:
                # Mağaza ürünü için onarım tamamlandı SMS'i
                sms_mesaji = f"Sayın {ariza.partner_id.name}. {ariza.name}, {ariza.urun} ürününüzün onarımı tamamlanmıştır. B021"
            
            # Ürün Değişimi bilgisini ekle
            if self.garanti_kapsaminda_mi == 'urun_degisimi':
                sms_mesaji += " Ürününüzün değişimi sağlanmıştır."
            
            ariza._send_sms_to_customer(sms_mesaji)
            # Müşteriye e-posta gönder
            if ariza.partner_id and ariza.partner_id.email:
                ariza._send_email_to_customer("Ürününüz Teslim Edilmeye Hazır", sms_mesaji)
            ariza.ikinci_sms_gonderildi = True
        

        
        # Mağaza ürünü işlemleri için 2. transfer oluştur (Teknik Servis → Mağaza)
        if ariza.ariza_tipi == 'magaza':
            # 2. transfer için gerekli bilgileri hazırla
            picking_vals = {
                'picking_type_id': self.env['stock.picking.type'].search([
                    ('code', '=', 'incoming'),
                    ('warehouse_id', '=', ariza.teslim_magazasi_id.warehouse_id.id) if ariza.teslim_magazasi_id and ariza.teslim_magazasi_id.warehouse_id else []
                ], limit=1).id,
                'location_id': ariza.teknik_servis_location_id.id if ariza.teknik_servis_location_id else False,
                'location_dest_id': ariza.teslim_magazasi_id.location_id.id if ariza.teslim_magazasi_id and ariza.teslim_magazasi_id.location_id else False,
                'origin': ariza.name,
                'scheduled_date': fields.Datetime.now(),
                'date': fields.Datetime.now(),
                'delivery_type': 'matbu',
            }
            
            # Teknik servise göre partner_id ayarla (2. transfer için)
            if ariza.teknik_servis == 'TEDARİKÇİ' and ariza.tedarikci_id:
                picking_vals['partner_id'] = ariza.tedarikci_id.id
            elif ariza.teknik_servis == 'DTL BEYOĞLU':
                dtl_partner = self.env['res.partner'].search([('name', 'ilike', 'Dtl Elektronik Servis Hiz. Tic. Ltd Şti')], limit=1)
                if dtl_partner:
                    picking_vals['partner_id'] = dtl_partner.id
            elif ariza.teknik_servis == 'DTL OKMEYDANI':
                dtl_partner = self.env['res.partner'].search([('name', 'ilike', 'Dtl Elektronik Servis Hiz. Tic. Ltd Şti')], limit=1)
                if dtl_partner:
                    dtl_okmeydani = self.env['res.partner'].search([
                        ('parent_id', '=', dtl_partner.id),
                        ('name', 'ilike', 'DTL OKMEYDANI')
                    ], limit=1)
                    if dtl_okmeydani:
                        picking_vals['partner_id'] = dtl_okmeydani.id
                    else:
                        picking_vals['partner_id'] = dtl_partner.id
            elif ariza.teknik_servis == 'ZUHAL ARIZA DEPO':
                zuhal_partner = self.env['res.partner'].search([('name', 'ilike', 'Zuhal Dış Ticaret A.Ş.')], limit=1)
                if zuhal_partner:
                    zuhal_ariza = self.env['res.partner'].search([
                        ('parent_id', '=', zuhal_partner.id),
                        ('name', 'ilike', 'Arıza Depo')
                    ], limit=1)
                    if zuhal_ariza:
                        picking_vals['partner_id'] = zuhal_ariza.id
                    else:
                        picking_vals['partner_id'] = zuhal_partner.id
            elif ariza.teknik_servis == 'ZUHAL NEFESLİ':
                zuhal_partner = self.env['res.partner'].search([('name', 'ilike', 'Zuhal Dış Ticaret A.Ş.')], limit=1)
                if zuhal_partner:
                    zuhal_nefesli = self.env['res.partner'].search([
                        ('parent_id', '=', zuhal_partner.id),
                        ('name', 'ilike', 'Nefesli Arıza')
                    ], limit=1)
                    if zuhal_nefesli:
                        picking_vals['partner_id'] = zuhal_nefesli.id
                    else:
                        picking_vals['partner_id'] = zuhal_partner.id
            
            # 2. transferi oluştur
            if picking_vals['location_id'] and picking_vals['location_dest_id']:
                ikinci_transfer = self.env['stock.picking'].create(picking_vals)
                
                # Transfer satırını oluştur
                move_vals = {
                    'name': f"{ariza.urun} - {ariza.name}",
                    'product_id': ariza.magaza_urun_id.id if ariza.magaza_urun_id else False,
                    'product_uom_qty': 1.0,
                    'product_uom': ariza.magaza_urun_id.uom_id.id if ariza.magaza_urun_id else False,
                    'picking_id': ikinci_transfer.id,
                    'location_id': picking_vals['location_id'],
                    'location_dest_id': picking_vals['location_dest_id'],
                }
                
                if move_vals['product_id'] and move_vals['product_uom']:
                    self.env['stock.move'].create(move_vals)
                
                # 2. transfere yönlendir
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'stock.picking',
                    'res_id': ikinci_transfer.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
        
        # Mesaj gönder
        if ariza.ariza_tipi == 'musteri' and self.adresime_gonderilsin and self.musteri_adresi_id:
            ariza.message_post(
                body=f"Onarım süreci tamamlandı. Onarım bilgileri kaydedildi. Adrese gönderim seçildi. Müşteriye SMS gönderildi. Durum otomatik olarak 'Teslim Edildi' olarak güncellendi.",
                subject="Onarım Tamamlandı - Adrese Gönderim"
            )
        elif ariza.ariza_tipi == 'magaza':
            ariza.message_post(
                body=f"Onarım süreci tamamlandı. Onarım bilgileri kaydedildi. Müşteriye SMS gönderildi. 2. transfer (Teknik Servis → Mağaza) otomatik oluşturuldu.",
                subject="Onarım Tamamlandı - 2. Transfer Oluşturuldu"
            )
        else:
            ariza.message_post(
                body=f"Onarım süreci tamamlandı. Onarım bilgileri kaydedildi. Müşteriye SMS gönderildi. Kullanıcı Teslim Et butonuna basarak geri gönderim transferini oluşturabilir.",
                subject="Onarım Tamamlandı"
            )
        
        return {'type': 'ir.actions.act_window_close'} 