# -*- coding: utf-8 -*-
"""
Arıza State Service - State geçişleri ve action mantığı

action_personel_onayla, action_kabul_et, action_teknik_onarim_baslat,
action_onayla, action_iptal, action_kullanici_tamamla mantığı.
"""

import logging
from odoo import _
from odoo.exceptions import UserError

from ..ariza_constants import ArizaStates, ArizaTipi, IslemTipi, SMSTemplates, TeknikServis, GarantiKapsam
from . import ariza_computed_helper

_logger = logging.getLogger(__name__)


class ArizaStateService:
    """Arıza kaydı state geçişleri ve action işlemleri"""

    @staticmethod
    def personel_onayla(record):
        """Personel onaylama - DRAFT->PERSONEL_ONAY veya ONAYLANDI->2.transfer"""
        if record.state == ArizaStates.DRAFT:
            return ArizaStateService._personel_onayla_draft(record)
        elif record.state == ArizaStates.ONAYLANDI:
            return ArizaStateService._personel_onayla_onaylandi(record)
        return None

    @staticmethod
    def _personel_onayla_draft(record):
        """DRAFT -> PERSONEL_ONAY: transfer oluştur, SMS gönder"""
        record.state = ArizaStates.PERSONEL_ONAY

        if record.ariza_tipi == ArizaTipi.MAGAZA and not record.transfer_id:
            if record.teknik_servis == TeknikServis.TEDARIKCI:
                if not record.tedarikci_id:
                    raise UserError('Tedarikçi seçimi zorunludur!')
                hedef_konum = record.tedarikci_id.property_stock_supplier
                if not hedef_konum:
                    hedef_konum = record.env['stock.location'].search([
                        ('usage', '=', 'supplier'),
                        ('company_id', '=', record.company_id.id)
                    ], limit=1)
                    if not hedef_konum:
                        raise UserError('Tedarikçi stok konumu bulunamadı!')
                picking = record._create_stock_transfer(hedef_konum=hedef_konum, transfer_tipi='ilk')
                if picking:
                    record.transfer_id = picking.id
                    return {
                        'type': 'ir.actions.act_window',
                        'name': 'Transfer Belgesi',
                        'res_model': 'stock.picking',
                        'res_id': picking.id,
                        'view_mode': 'form',
                        'context': {'hide_note': True},
                        'target': 'current',
                    }
            elif record.teknik_servis != TeknikServis.MAGAZA:
                picking = record._create_stock_transfer(transfer_tipi='ilk')
                if picking:
                    record.transfer_id = picking.id
                    return {
                        'type': 'ir.actions.act_window',
                        'name': 'Transfer Belgesi',
                        'res_model': 'stock.picking',
                        'res_id': picking.id,
                        'view_mode': 'form',
                        'context': {'hide_note': True},
                        'target': 'current',
                    }

        if record.islem_tipi == IslemTipi.ARIZA_KABUL and record.ariza_tipi == ArizaTipi.MUSTERI and not record.ilk_sms_gonderildi:
            message = SMSTemplates.ILK_SMS.format(
                musteri_adi=record.partner_id.name or '',
                urun=record.urun or '',
                kayit_no=record.name or ''
            )
            record.sudo()._send_sms_to_customer(message)
            record.sudo().ilk_sms_gonderildi = True
            record.sudo().sms_gonderildi = True

        return {
            'type': 'ir.actions.act_window',
            'name': 'Arıza Kayıtları',
            'res_model': 'ariza.kayit',
            'view_mode': 'tree,form',
            'target': 'current',
        }

    @staticmethod
    def _personel_onayla_onaylandi(record):
        """ONAYLANDI -> 2. transfer oluştur"""
        if not record.kaynak_konum_id or not record.hedef_konum_id:
            raise UserError(_('Kaynak ve hedef konumları eksik! Lütfen konumları kontrol edin.'))
        picking = record._create_stock_transfer(
            kaynak_konum=record.hedef_konum_id,
            hedef_konum=record.kaynak_konum_id,
            transfer_tipi='ikinci'
        )
        if not picking:
            raise UserError(_("2. transfer oluşturulamadı! Lütfen kaynak ve hedef konumları kontrol edin."))
        record.transfer_sayisi = record.transfer_sayisi + 1
        return {
            'type': 'ir.actions.act_window',
            'name': 'Arıza Kaydı',
            'res_model': 'ariza.kayit',
            'res_id': record.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @staticmethod
    def kabul_et(record):
        """PERSONEL_ONAY -> KABUL_EDILDI"""
        current_user = record.env.user
        if record.teknik_servis != TeknikServis.MAGAZA:
            if not current_user.has_group('ariza_onarim.group_ariza_manager'):
                raise UserError(_('Bu işlemi sadece yetkili kullanıcılar yapabilir.'))
        if record.state != ArizaStates.PERSONEL_ONAY:
            raise UserError(_('Sadece personel onayı aşamasındaki kayıtlar kabul edilebilir.'))
        record.state = ArizaStates.KABUL_EDILDI
        record.message_post(
            body=f"Arıza kaydı kabul edildi. Kabul eden: {current_user.name}",
            subject="Arıza Kaydı Kabul Edildi",
            message_type='notification'
        )
        _logger.info(f"Arıza kaydı kabul edildi: {record.name} - Kullanıcı: {current_user.login}")

    @staticmethod
    def teknik_onarim_baslat(record):
        """KABUL_EDILDI -> TEKNIK_ONARIM"""
        if record.state == ArizaStates.KABUL_EDILDI:
            record.state = ArizaStates.TEKNIK_ONARIM
            record.message_post(
                body=f"Teknik onarım süreci başlatıldı. Sorumlu: {record.sorumlu_id.name}",
                subject="Teknik Onarım Başlatıldı",
                message_type='notification'
            )
        elif record.state == ArizaStates.PERSONEL_ONAY:
            raise UserError(_('Önce "Kabul Et" butonuna basmanız gerekiyor.'))
        else:
            raise UserError(_('Sadece kabul edilmiş kayıtlar için onarım başlatılabilir.'))

    @staticmethod
    def onayla(record):
        """TEKNIK_ONARIM -> wizard aç (onaylandi'ye geçiş wizard içinde)"""
        if record.state != ArizaStates.TEKNIK_ONARIM:
            raise UserError('Sadece teknik onarım aşamasındaki kayıtlar onaylanabilir!')
        return {
            'name': 'Onarım Bilgilerini Doldur',
            'type': 'ir.actions.act_window',
            'res_model': 'ariza.onarim.bilgi.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ariza_id': record.id,
                'default_musteri_adi': record.partner_id.name if record.partner_id else '',
                'default_urun': record.urun,
                'default_teslim_magazasi_id': record.teslim_magazasi_id.id if record.teslim_magazasi_id else False,
                'default_onarim_bilgisi': record.onarim_bilgisi or '',
                'default_garanti_kapsaminda_mi': record.garanti_kapsaminda_mi or GarantiKapsam.HAYIR,
                'default_ucret_bilgisi': record.ucret_bilgisi or '',
                'default_onarim_ucreti': record.onarim_ucreti or 0.0,
            }
        }

    @staticmethod
    def iptal(record):
        """Herhangi -> IPTAL"""
        if record.transfer_id and record.transfer_id.state == 'done':
            raise UserError(_('Transferi bitene dönen arıza kayıtları iptal edilemez!'))
        record.state = ArizaStates.IPTAL
        record.message_post(
            body=_('Arıza kaydı iptal edildi.'),
            subject="Arıza Kaydı İptal Edildi",
            message_type='notification'
        )
        _logger.info(f"Arıza kaydı iptal edildi: {record.name} - Kullanıcı: {record.env.user.login}")
        return True

    @staticmethod
    def kullanici_tamamla(record):
        """TAMAMLANDI -> teslim wizard aç"""
        if record.ariza_tipi == ArizaTipi.MUSTERI and not record.hazir_basildi:
            raise UserError(_("Teslim Et işlemi için önce 'Hazır' butonuna basmanız gerekmektedir!"))
        if record.state != ArizaStates.TAMAMLANDI:
            raise UserError('Sadece tamamlanmış kayıtlar teslim edilebilir!')
        return {
            'name': 'Teslim Alan Bilgisi',
            'type': 'ir.actions.act_window',
            'res_model': 'ariza.teslim.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ariza_id': record.id,
                'default_musteri_adi': record.partner_id.name if record.partner_id else '',
                'default_urun': record.urun,
            }
        }

    @staticmethod
    def teslim_al_musteri(record):
        """Müşteri ürünü Hazır butonu - 2. SMS gönderir"""
        record.hazir_basildi = True
        if record.ariza_tipi != ArizaTipi.MUSTERI:
            raise UserError(_('Bu işlem sadece müşteri ürünü için kullanılabilir.'))
        if record.state != ArizaStates.TAMAMLANDI:
            raise UserError(_('Bu işlem sadece tamamlandı durumundaki kayıtlar için kullanılabilir.'))
        has_phone = record.partner_id and (
            (record.partner_id.mobile or record.partner_id.phone) or
            (record.sms_farkli_noya_gonder and record.sms_farkli_telefon and record.sms_farkli_telefon.strip())
        )
        if has_phone and not record.ikinci_sms_gonderildi:
            magaza_adi = record.teslim_magazasi_id.name if record.teslim_magazasi_id else ''
            temiz_magaza_adi = ariza_computed_helper.ArizaComputedHelper.clean_magaza_adi(magaza_adi) if magaza_adi else ''
            message = SMSTemplates.IKINCI_SMS.format(
                musteri_adi=record.partner_id.name or '',
                urun=record.urun or '',
                magaza_adi=temiz_magaza_adi or '',
                kayit_no=record.name or ''
            )
            record._send_sms_to_customer(message)
            record.ikinci_sms_gonderildi = True
            record.message_post(
                body=f"Teslim Al butonuna basıldı. Müşteriye 2. SMS gönderildi: {message}",
                subject="Teslim Al - 2. SMS Gönderildi",
                message_type='notification'
            )
        elif record.ikinci_sms_gonderildi:
            raise UserError(_('2. SMS zaten gönderilmiş. Tekrar gönderilemez.'))
        else:
            raise UserError(_('SMS gönderilemedi: Müşteri veya telefon bilgisi eksik.'))

    @staticmethod
    def onayla_kullanici_bazli(record):
        """Kullanıcı bazlı onay - ONAYLANDI durumuna geç"""
        current_user = record.env.user
        if not current_user.has_group('ariza_onarim.group_ariza_manager'):
            raise UserError(_('Bu işlemi sadece yetkili kullanıcılar yapabilir.'))
        record.state = ArizaStates.ONAYLANDI
        record.message_post(body=_('Arıza kaydı onaylandı ve onarım süreci aktif hale getirildi.'), message_type='notification')
        _logger.info(f"Arıza kaydı onaylandı: {record.name} - Kullanıcı: {current_user.login}")

    @staticmethod
    def onarim_baslat(record):
        """Onarım sürecini başlat - ONAYLANDI durumundan"""
        current_user = record.env.user
        if not current_user.has_group('ariza_onarim.group_ariza_manager'):
            raise UserError(_('Bu işlemi sadece yönetici yapabilir.'))
        if record.state != ArizaStates.ONAYLANDI:
            raise UserError(_('Sadece onaylanmış arıza kayıtları için onarım başlatılabilir.'))
        from odoo import fields
        record.onarim_baslangic_tarihi = fields.Date.today()
        record.onarim_durumu = 'devam_ediyor'
        record.message_post(body=_('Onarım süreci başlatıldı.'), message_type='notification')
        _logger.info(f"Onarım süreci başlatıldı: {record.name} - Kullanıcı: {current_user.login}")

    @staticmethod
    def lock(record):
        """Arıza kaydını kilitle"""
        record.state = ArizaStates.KILITLI

    @staticmethod
    def unlock(record):
        """Arıza kaydının kilidini aç"""
        record.state = ArizaStates.DRAFT
