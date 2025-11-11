# -*- coding: utf-8 -*-
"""
Arıza Kayıt Tamamla Wizard - Arıza kaydı tamamlama wizard'ı (Eski - Kullanılmıyor)
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..models.ariza_constants import SMSTemplates

class ArizaKayitTamamlaWizard(models.TransientModel):
    _name = 'ariza.kayit.tamamla.wizard'
    _description = 'Arıza Kaydı Tamamlama Sihirbazı'

    ariza_id = fields.Many2one('ariza.kayit', string='Arıza Kaydı', required=True)
    onay_mesaji = fields.Text(string='Onay Mesajı', readonly=True)

    def action_tamamla(self):
        ariza = self.ariza_id
        
        # 2. transfer oluştur - İlk transferin tam tersi
        if ariza.transfer_id:
            mevcut_kaynak = ariza.transfer_id.location_id
            mevcut_hedef = ariza.transfer_id.location_dest_id
            
            # 2. transfer: Teknik servisten mağazaya geri dönüş
            yeni_transfer = ariza._create_stock_transfer(
                kaynak_konum=mevcut_hedef,  # Teknik servis (1. transferin hedefi)
                hedef_konum=mevcut_kaynak,  # Mağaza (1. transferin kaynağı)
                transfer_tipi='ikinci'      # 2. transfer olduğunu belirt
            )
            
            if yeni_transfer:
                # 2. transfer oluşturuldu
                # Arıza kaydını güncelle
                ariza.write({
                    'transfer_sayisi': ariza.transfer_sayisi + 1,
                })
                
                # SMS gönderimi (Email gönderimi kaldırıldı)
                if ariza.partner_id and (ariza.ariza_tipi == 'musteri' or ariza.ariza_tipi == 'magaza'):
                    if ariza.partner_id.mobile or ariza.partner_id.phone:
                        # SMS gönderimi
                        # NOT: Bu wizard artık kullanılmıyor, ancak eski kod uyumluluğu için şablon kullanımına güncellendi
                        if ariza.ariza_tipi == 'musteri':
                            # Mağaza adı yoksa boş string kullan
                            sms_mesaji = SMSTemplates.IKINCI_SMS.format(
                                musteri_adi=ariza.partner_id.name or '',
                                urun=ariza.urun or '',
                                magaza_adi='',  # Bu wizard'da mağaza adı yok
                                kayit_no=ariza.name or ''
                            )
                            if ariza.garanti_kapsaminda_mi == 'evet':
                                sms_mesaji += SMSTemplates.GARANTI_EKLENTISI
                        else: # ariza.ariza_tipi == 'magaza'
                            # Mağaza ürünü için SMS gönderilmez, ancak eski kod uyumluluğu için şablon kullanıldı
                            sms_mesaji = f"Sayın {ariza.partner_id.name}., {ariza.urun} ürününüz teslim edilmiştir. Kayıt No: {ariza.name} B021"
                        
                        ariza._send_sms_to_customer(sms_mesaji)
                    
                    # Email gönderimi kaldırıldı - Mail gönderilmesin
                        
                
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
        
        return {'type': 'ir.actions.act_window_close'} 