# -*- coding: utf-8 -*-
"""
Onarım Bilgi Wizard - Onarım bilgileri girişi için wizard
"""

import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..models.ariza_constants import SMSTemplates, TeslimAlan, EmailAddresses, GarantiKapsam
from ..models.ariza_helpers import ariza_transfer_service
from ..models.ariza_helpers.chatter_helper import ChatterHelper as Chatter

_logger = logging.getLogger(__name__)

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
    onarim_bilgisi = fields.Text(string='Onarım Bilgisi', required=False)
    garanti_kapsaminda_mi = fields.Selection([
        ('evet', 'Evet'),
        ('hayir', 'Hayır'),
        ('urun_degisimi', 'Ürün Değişimi'),
    ], string='Garanti Kapsamında mı?', required=False)
    ucret_bilgisi = fields.Char(string='Ücret Bilgisi')
    onarim_ucreti = fields.Monetary(string='Onarım Ücreti', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Para Birimi', default=lambda self: self.env.company.currency_id)
    
    # Onarım Dışı Alanları (Sadece Mağaza Ürünü için)
    onarim_mumkun_degil = fields.Boolean(string='Onarımı Mümkün Değil', default=False)
    onarim_mumkun_degil_aciklama = fields.Text(string='Açıklama')
    


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
            

        return res

    def _send_degisim_email(self, ariza):
        """Ürün Değişimi bildirimini mağaza e-postasına ve destek birimine gönderir.

        Destek birimi her durumda alıcıdır; mağaza e-postası boşsa bildirim
        yalnızca destek birimine gider ve chatter'a uyarı düşülür.
        E-posta gönderimi başarısız olsa bile arıza akışını bloklamaz.
        """
        recipients = [e.strip() for e in (ariza.analitik_hesap_email or '').split(',') if e.strip()]
        if EmailAddresses.DESTEK not in recipients:
            recipients.append(EmailAddresses.DESTEK)

        template = self.env.ref('ariza_onarim.email_template_ariza_degisim', raise_if_not_found=False)
        if not template:
            _logger.warning("Ürün Değişimi e-posta şablonu bulunamadı: ariza_onarim.email_template_ariza_degisim")
            return

        try:
            template.send_mail(ariza.id, force_send=True, email_values={'email_to': ','.join(recipients)})
            Chatter.yaz(ariza, f"Ürün Değişimi e-postası gönderildi: {Chatter.metin(', '.join(recipients))}")
            if not ariza.analitik_hesap_email:
                Chatter.uyari(ariza, "Mağazanın e-posta adresi tanımlı değil; bildirim yalnızca destek birimine gitti.")
        except Exception:
            _logger.exception("Ürün Değişimi e-postası gönderilemedi (kayıt: %s)", ariza.name)
            Chatter.uyari(ariza, "Ürün Değişimi e-postası gönderilemedi (giden e-posta sunucusunu kontrol edin).")

    def _temizle_magaza_adi(self, magaza_adi):
        """Mağaza adından 'Perakende' ifadesini kaldır"""
        if magaza_adi:
            # "Perakende" ifadesini kaldır
            temiz_adi = magaza_adi.replace('Perakende ', '').replace(' Perakende', '')
            return temiz_adi
        return magaza_adi

    def _yolda_donus_kur(self, ariza):
        """Yolda akışı: servisten mağazaya dönüş çıkışını açar ve otomatik
        doğrular. Hata onarım kaydını engellemez. Returns: uyarı metni veya None
        (chatter'a çağıran yazar ki onarım mesajından sonra gelsin)."""
        try:
            with self.env.cr.savepoint():
                ariza_transfer_service.ArizaTransferService.create_donus_yolda(ariza)
        except UserError as e:
            _logger.warning("[YOLDA] %s dönüş transferi kurulamadı: %s", ariza.name, e)
            neden = e.args[0] if e.args else ''
        except Exception:
            _logger.exception("[YOLDA] %s dönüş transferi kurulamadı", ariza.name)
            neden = 'beklenmeyen hata'
        else:
            return self._yolda_donus_cikis_dogrula(ariza)
        return (
            f"Dönüş transferi kurulamadı ({Chatter.metin(neden)}); "
            "ürün \"Teslim Al\" ile tek adımda dönecek."
        )

    def _yolda_donus_cikis_dogrula(self, ariza):
        """Yolda akışı: servis onarımı tamamlayınca dönüş çıkışı otomatik
        doğrulanır (ürün yola çıkar). Doğrulanamazsa onarım kaydı engellenmez;
        çıkış açık kalır ve servis elle doğrular. Returns: uyarı metni veya None."""
        picking = ariza.sudo().yolda_donus_out_id
        if not picking or picking.state in ('done', 'cancel'):
            return None
        try:
            with self.env.cr.savepoint():
                if picking.state == 'draft':
                    picking.action_confirm()
                if picking.state != 'assigned':
                    picking.action_assign()
                if picking.state != 'assigned' or not picking.move_line_ids:
                    raise UserError(_('ürün servis stoğunda ayrılamadı'))
                for satir in picking.move_line_ids:
                    satir.qty_done = satir.product_uom_qty
                picking.with_context(
                    skip_immediate=True, skip_backorder=True, skip_sms=True,
                    ariza_otomatik=True,
                ).button_validate()
                if picking.state != 'done':
                    raise UserError(_('transfer doğrulanamadı'))
        except UserError as e:
            _logger.warning("[YOLDA] %s dönüş çıkışı otomatik doğrulanamadı: %s", ariza.name, e)
            neden = e.args[0] if e.args else ''
        except Exception:
            _logger.exception("[YOLDA] %s dönüş çıkışı otomatik doğrulanamadı", ariza.name)
            neden = 'beklenmeyen hata'
        else:
            return None
        return (
            f"Dönüş çıkışı {Chatter.link(picking)} otomatik doğrulanamadı "
            f"({Chatter.metin(neden)}); servis transferi açıp doğrulamalı."
        )

    def _onarim_mesaji_magaza(self, ariza, uyari):
        """Mağaza ürünü: onarım + dönüş tek satır; varsa uyarı ayrı satır."""
        donus_out = ariza.sudo().yolda_donus_out_id
        donus_in = ariza.sudo().yolda_donus_in_id
        if donus_out and donus_out.state == 'done':
            metin = (
                f"Onarım tamamlandı. Ürün mağazaya yola çıktı: {Chatter.link(donus_out)} "
                f"→ mağazaya varış {Chatter.link(donus_in)} (\"Teslim Al\" ile)"
            )
        elif donus_out:
            metin = (
                f"Onarım tamamlandı. Dönüş çıkışı {Chatter.link(donus_out)} servisin "
                f"doğrulamasını bekliyor → mağazaya varış {Chatter.link(donus_in)}"
            )
        else:
            metin = "Onarım tamamlandı. Mağaza \"Teslim Al\" ile ürünü teslim alır."
        Chatter.yaz(ariza, metin)
        if uyari:
            Chatter.uyari(ariza, uyari)

    def action_onarim_bilgilerini_kaydet(self):
        """Onarım bilgilerini kaydet ve durumu güncelle"""
        ariza = self.ariza_id
        
        # Onarım Dışı kontrolü (Sadece Mağaza Ürünü için)
        if self.ariza_tipi == 'magaza' and self.onarim_mumkun_degil:
            # Açıklama zorunlu
            if not self.onarim_mumkun_degil_aciklama:
                raise UserError(_('Onarımı mümkün değil seçeneği işaretlendiğinde açıklama girmeniz zorunludur.'))
            
            # Onarım dışı bilgilerini kaydet
            ariza.onarim_disi_aciklama = self.onarim_mumkun_degil_aciklama
            ariza.state = 'onarim_disi'
            
            Chatter.yaz(ariza, f"Onarım dışı: {Chatter.metin(self.onarim_mumkun_degil_aciklama)}")

            return {'type': 'ir.actions.act_window_close'}
        
        # Normal onarım akışı - Validasyonlar
        if not self.onarim_mumkun_degil:
            if not self.onarim_bilgisi:
                raise UserError(_('Onarım bilgisi girmeniz zorunludur.'))
            if self.ariza_tipi == 'musteri' and not self.garanti_kapsaminda_mi:
                raise UserError(_('Garanti kapsamı seçmeniz zorunludur.'))
        
        # Normal onarım akışı devam ediyor
        # Onarım bilgilerini güncelle
        ariza.onarim_bilgisi = self.onarim_bilgisi
        ariza.garanti_kapsaminda_mi = self.garanti_kapsaminda_mi
        ariza.ucret_bilgisi = self.ucret_bilgisi
        
        # Garanti kapsamında olan durumlarda onarım ücreti sıfırla
        if self.garanti_kapsaminda_mi in ['evet', 'urun_degisimi']:
            ariza.onarim_ucreti = 0.0
        else:
            ariza.onarim_ucreti = self.onarim_ucreti

        # Ürün Değişimi seçildiyse mağaza e-postasına otomatik bildirim gönder
        if self.garanti_kapsaminda_mi == 'urun_degisimi':
            self._send_degisim_email(ariza)
        
        # Teslim mağazasını güncelle (müşteri ürünü için)
        if self.ariza_tipi == 'musteri':
            if self.adresime_gonderilsin and self.musteri_adresi_id:
                # Adrese gönderim seçildi
                ariza.teslim_magazasi_id = False
                ariza.contact_id = self.musteri_adresi_id.id  # Teslimat adresini contact_id'ye kaydet
                ariza.teslim_adresi = self.musteri_adresi_id.street or ''
            elif self.teslim_magazasi_id:
                # Mağazadan teslim seçildi
                ariza.teslim_magazasi_id = self.teslim_magazasi_id.id
        
        # Durumu güncelle - Mağaza ürünü için yönetici tamamlandı, müşteri ürünü için normal akış
        if self.ariza_tipi == 'magaza':
            ariza.state = 'yonetici_tamamlandi'
            uyari = self._yolda_donus_kur(ariza) if ariza.yolda_akisi else None
            self._onarim_mesaji_magaza(ariza, uyari)
        elif self.ariza_tipi == 'musteri' and self.adresime_gonderilsin and self.musteri_adresi_id:
            ariza.state = 'teslim_edildi'
            # Adrese gönderim için teslim bilgilerini güncelle
            ariza.teslim_alan = TeslimAlan.ADRESE_GONDERIM
            ariza.contact_id = self.musteri_adresi_id.id  # Teslimat adresini contact_id'ye kaydet
            ariza.teslim_adresi = self.musteri_adresi_id.street or ''
            Chatter.yaz(ariza, "Onarım tamamlandı. Ürün müşteri adresine gönderilecek.")

            # Aras iade kargo transferi oluştur (barkod kaynağı; validate'te barkod oluşur)
            ariza.create_musteri_iade_transfer()

            # Adrese gönderim için SMS gönder (Üçüncü SMS)
            has_phone = ariza.partner_id and (
                (ariza.partner_id.mobile or ariza.partner_id.phone) or
                (ariza.sms_farkli_noya_gonder and ariza.sms_farkli_telefon and ariza.sms_farkli_telefon.strip())
            )
            if has_phone and not ariza.ucuncu_sms_gonderildi:
                from datetime import datetime
                teslim_tarihi = datetime.now().strftime("%d.%m.%Y %H:%M")
                
                message = SMSTemplates.ADRESE_GONDERIM_SMS.format(
                    musteri_adi=ariza.partner_id.name or '',
                    urun=ariza.urun or '',
                    teslim_tarihi=teslim_tarihi,
                    kayit_no=ariza.name or ''
                )
                
                if ariza.garanti_kapsaminda_mi == GarantiKapsam.URUN_DEGISIMI:
                    message += SMSTemplates.GARANTI_EKLENTISI
                
                ariza._send_sms_to_customer(message)
                ariza.ucuncu_sms_gonderildi = True
        else:
            ariza.state = 'tamamlandi'
            Chatter.yaz(ariza, "Onarım tamamlandı.")
            # Mağazadan teslim + kargo metodu: teknik servisten mağazaya DÖNÜŞ
            # kargosu (gidişin tam tersi transfer, YENİ Aras barkodu — gidiş
            # barkodu tekrar kullanılırsa kargoda karışıklık olur)
            if (ariza.ariza_tipi == 'musteri'
                    and ariza.transfer_metodu in ('ucretsiz_kargo', 'ucretli_kargo')):
                try:
                    ariza.create_donus_kargo_transfer()
                except Exception as e:
                    Chatter.uyari(ariza, (
                        f"Dönüş kargo transferi oluşturulamadı ({Chatter.metin(str(e))}); "
                        "transferi elle oluşturun."
                    ))

        # SMS gönderimi - Müşteri ürünü için 2. SMS kaldırıldı (Yönetici Onarımı Tamamla ve SMS Gönder butonu için)
        # Diğer SMS akışları (ilk SMS, üçüncü SMS) korunuyor
        

        
        # Mağaza ürünü işlemleri için 2. transfer artık kullanıcı "Teslim AL" butonuna bastığında oluşacak
        
        donus_out = ariza.sudo().yolda_donus_out_id
        if ariza.ariza_tipi == 'magaza' and donus_out and donus_out.state not in ('done', 'cancel'):
            # Yolda dönüşü: servis çıkışı doğrulasın diye dönüş çıkışı açılır
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'res_id': donus_out.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {'type': 'ir.actions.act_window_close'}
