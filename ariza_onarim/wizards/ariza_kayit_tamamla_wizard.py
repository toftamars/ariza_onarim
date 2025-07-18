from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ArizaKayitTamamlaWizard(models.TransientModel):
    _name = 'ariza.kayit.tamamla.wizard'
    _description = 'Arıza Kaydı Tamamlama Sihirbazı'

    ariza_id = fields.Many2one('ariza.kayit', string='Arıza Kaydı', required=True)
    onay_mesaji = fields.Text(string='Onay Mesajı', readonly=True)

    def action_tamamla(self):
        ariza = self.ariza_id
        
        # SMS gönderimi - Hem müşteri hem mağaza ürünleri için
        if ariza.partner_id and ariza.partner_id.phone:
            if ariza.ariza_tipi == 'musteri':
                # Müşteri ürünü için teslim alındı SMS'i
                magaza_adi = ariza._clean_magaza_adi(ariza.teslim_magazasi_id.name) if ariza.teslim_magazasi_id else ''
                sms_mesaji = f"Sayın {ariza.partner_id.name}. {ariza.name}, {ariza.urun} ürününüz teslim edilmeye hazırdır. Ürününüzü - {magaza_adi} mağazamızdan teslim alabilirsiniz. B021"
            else:
                # Mağaza ürünü için teslim edildi SMS'i
                sms_mesaji = f"Sayın {ariza.partner_id.name}. {ariza.name}, {ariza.urun} ürününüz teslim edilmiştir. B021"
            
            ariza._send_sms_to_customer(sms_mesaji)
        
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
                # 2. transfer oluşturuldu, ama transfer_id'yi değiştirme
                # Yeni transferin detaylarını logla
                self.env['ir.logging'].create({
                    'name': 'ariza_onarim',
                    'type': 'server',
                    'level': 'info',
                    'dbname': self._cr.dbname,
                    'message': f"Yeni transfer oluşturuldu! Arıza No: {ariza.name} - Transfer ID: {yeni_transfer.id} - Kaynak: {mevcut_hedef.name} - Hedef: {mevcut_kaynak.name}",
                    'path': __file__,
                    'func': 'action_tamamla',
                    'line': 0,
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