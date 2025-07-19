from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ArizaKayitTamamlaWizard(models.TransientModel):
    _name = 'ariza.kayit.tamamla.wizard'
    _description = 'Arıza Kaydı Tamamlama Sihirbazı'

    ariza_id = fields.Many2one('ariza.kayit', string='Arıza Kaydı', required=True)
    onay_mesaji = fields.Text(string='Onay Mesajı', readonly=True)

    def action_tamamla(self):
        ariza = self.ariza_id
        
        # SMS ve Email gönderimi
        if ariza.partner_id and ariza.ariza_tipi == 'musteri':
            if ariza.partner_id.phone:
                # SMS gönderimi
                if ariza.ariza_tipi == 'musteri':
                    # Müşteri ürünü için teslim alındı SMS'i
                    sms_mesaji = f"Sayın {ariza.partner_id.name}., {ariza.urun} ürününüz teslim edilmeye hazırdır. Ürününüzü mağazamızdan teslim alabilirsiniz. B021"
                else:
                    # Mağaza ürünü için teslim edildi SMS'i
                    sms_mesaji = f"Sayın {ariza.partner_id.name}., {ariza.urun} ürününüz teslim edilmiştir. B021"
                
                ariza._send_sms_to_customer(sms_mesaji)
            
            if ariza.partner_id.email:
                # Email gönderimi
                if ariza.ariza_tipi == 'musteri':
                    # Müşteri ürünü için teslim alındı email'i
                    subject = f"Ürününüz Teslim Edilmeye Hazır: {ariza.name}"
                    body = f"""
                    Sayın {ariza.partner_id.name},
                    
                    {ariza.urun} ürününüz teslim edilmeye hazırdır. 
                    Ürününüzü mağazamızdan teslim alabilirsiniz.
                    
                    Arıza No: {ariza.name}
                    
                    Saygılarımızla,
                    B021
                    """
                else:
                    # Mağaza ürünü için teslim edildi email'i
                    subject = f"Ürününüz Teslim Edildi: {ariza.name}"
                    body = f"""
                    Sayın {ariza.partner_id.name},
                    
                    {ariza.urun} ürününüz teslim edilmiştir.
                    
                    Arıza No: {ariza.name}
                    
                    Saygılarımızla,
                    B021
                    """
                
                ariza._send_email_to_customer(subject, body)
        
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
                # 2. transfer oluşturuldu, arıza kaydını güncelle
                ariza.write({
                    'transfer_id': yeni_transfer.id,  # 2. transferi arıza kaydına bağla
                    'state': 'teslim_edildi',  # Durumu teslim edildi olarak güncelle
                    'transfer_sayisi': ariza.transfer_sayisi + 1  # Transfer sayısını artır
                })
                
                # 2. transfer'e yönlendir
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'stock.picking',
                    'res_id': yeni_transfer.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            else:
                raise UserError(_("Transfer oluşturulamadı! Lütfen kaynak ve hedef konumları kontrol edin."))
        
        return {'type': 'ir.actions.act_window_close'} 