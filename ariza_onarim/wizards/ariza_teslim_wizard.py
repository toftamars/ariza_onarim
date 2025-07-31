from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ArizaTeslimWizard(models.TransientModel):
    _name = 'ariza.teslim.wizard'
    _description = 'Teslim Alan Bilgisi Girme Sihirbazı'

    ariza_id = fields.Many2one('ariza.kayit', string='Arıza Kaydı', required=True)
    musteri_adi = fields.Char(string='Müşteri Adı', readonly=True)
    urun = fields.Char(string='Ürün', readonly=True)
    teslim_alan = fields.Char(string='Teslim Alan Kişi', required=True)
    
    # 2. transfer için alanlar
    is_ikinci_transfer = fields.Boolean(string='2. Transfer mi?', default=False)
    ikinci_transfer_kaynak = fields.Many2one('stock.location', string='2. Transfer Kaynak', domain="[('company_id', '=', company_id)]")
    ikinci_transfer_hedef = fields.Many2one('stock.location', string='2. Transfer Hedef', domain="[('company_id', '=', company_id)]")
    company_id = fields.Many2one('res.company', string='Şirket', default=lambda self: self.env.company)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self._context.get('active_id'):
            ariza = self.env['ariza.kayit'].browse(self._context['active_id'])
            res.update({
                'ariza_id': ariza.id,
                'musteri_adi': ariza.partner_id.name if ariza.partner_id else '',
                'urun': ariza.urun if ariza.urun else '',
            })
            
            # 2. transfer için konumları hesapla
            if self._context.get('default_is_ikinci_transfer'):
                res['is_ikinci_transfer'] = True
                
                # 1. transferin bilgilerini al
                birinci_transfer = self.env['stock.picking'].search([
                    ('origin', '=', ariza.name),
                    ('picking_type_code', '=', 'outgoing')  # İlk transfer çıkış transferi
                ], limit=1)
                
                if birinci_transfer:
                    # 2. transfer kaynağı = 1. transfer hedefi
                    res['ikinci_transfer_kaynak'] = birinci_transfer.location_dest_id.id if birinci_transfer.location_dest_id else False
                    
                    # 2. transfer hedefi = 1. transfer kaynağı
                    res['ikinci_transfer_hedef'] = birinci_transfer.location_id.id if birinci_transfer.location_id else False
        return res

    def action_teslim_et(self):
        """Teslim işlemini gerçekleştir"""
        ariza = self.ariza_id
        
        # 2. transfer için konumları kontrol et
        if self.is_ikinci_transfer:
            if not self.ikinci_transfer_kaynak or not self.ikinci_transfer_hedef:
                raise UserError('2. transfer için kaynak ve hedef konumları seçmelisiniz!')
            
            # 2. transfer oluştur
            picking_vals = {
                'picking_type_id': self.env['stock.picking.type'].search([
                    ('code', '=', 'outgoing')  # Tamir Teslimatları
                ], limit=1).id,
                'location_id': self.ikinci_transfer_kaynak.id,
                'location_dest_id': self.ikinci_transfer_hedef.id,
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
            ikinci_transfer = self.env['stock.picking'].create(picking_vals)
            
            # Transfer satırını oluştur
            move_vals = {
                'name': f"{ariza.urun} - {ariza.name}",
                'product_id': ariza.magaza_urun_id.id if ariza.magaza_urun_id else False,
                'product_uom_qty': 1.0,
                'product_uom': ariza.magaza_urun_id.uom_id.id if ariza.magaza_urun_id else False,
                'picking_id': ikinci_transfer.id,
                'location_id': self.ikinci_transfer_kaynak.id,
                'location_dest_id': self.ikinci_transfer_hedef.id,
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
        
        # Normal teslim işlemi (Müşteri ürünü için)
        # Teslim bilgilerini güncelle
        ariza.teslim_alan = self.teslim_alan
        
        # Durumu teslim edildi yap
        ariza.state = 'teslim_edildi'
        
        # Teslim edildi SMS'i gönder (Üçüncü SMS)
        if ariza.ariza_tipi == 'musteri' and ariza.partner_id and ariza.partner_id.phone and not ariza.ucuncu_sms_gonderildi:
            # Mağaza adını temizle
            magaza_adi = ariza.teslim_magazasi_id.name if ariza.teslim_magazasi_id else ''
            temiz_magaza_adi = ariza._clean_magaza_adi(magaza_adi)
            
            # Tarih ve saat bilgisini al
            from datetime import datetime
            teslim_tarihi = datetime.now().strftime("%d.%m.%Y %H:%M")
            
            # Teslim edilen kişi bilgisini al
            teslim_edilen_kisi = self.teslim_alan if self.teslim_alan else "müşteriye"
            
            message = f"Sayın {ariza.partner_id.name}. {ariza.urun} ürününüz {temiz_magaza_adi} mağazamızdan {teslim_tarihi} tarihinde {teslim_edilen_kisi} kişisine teslim edilmiştir. Kayıt No: {ariza.name} B021"
            if ariza.garanti_kapsaminda_mi in ['evet', 'urun_degisimi']:
                message += " Ürününüzün değişimi sağlanmıştır."
            ariza._send_sms_to_customer(message)
            # Müşteriye e-posta gönder
            if ariza.partner_id and ariza.partner_id.email:
                ariza._send_email_to_customer("Ürününüz Teslim Edildi", message)
            ariza.ucuncu_sms_gonderildi = True
        
        # Teslim edildi e-posta gönder
        mail_to = 'alper.tofta@zuhalmuzik.com'
        subject = f"Ürün Teslim Edildi: {ariza.name}"
        body = f"""
Ürün Teslim Edildi.<br/>
<b>Arıza No:</b> {ariza.name}<br/>
<b>Müşteri:</b> {ariza.partner_id.name if ariza.partner_id else '-'}<br/>
<b>Ürün:</b> {ariza.urun}<br/>
<b>Model:</b> {ariza.model}<br/>
<b>Arıza Tanımı:</b> {ariza.ariza_tanimi or '-'}<br/>
<b>Tarih:</b> {ariza.tarih or '-'}<br/>
<b>Teknik Servis:</b> {ariza.teknik_servis or '-'}<br/>
<b>Teknik Servis Adresi:</b> {ariza.teknik_servis_adres or '-'}<br/>
<b>Teslim Alan:</b> {self.teslim_alan}<br/>
"""
        ariza.env['mail.mail'].create({
            'subject': subject,
            'body_html': body,
            'email_to': mail_to,
        }).send()
        
        # Chatter'a mesaj ekle
        ariza.message_post(
            body=f"Ürün teslim edildi. Teslim alan: {self.teslim_alan}. SMS gönderildi.",
            subject="Ürün Teslim Edildi"
        )
        
        return {'type': 'ir.actions.act_window_close'} 