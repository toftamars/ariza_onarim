# -*- coding: utf-8 -*-
"""
SMS Helper - SMS işlemleri için helper metodlar
"""

import logging

_logger = logging.getLogger(__name__)


class SMSHelper:
    """SMS işlemleri için helper metodlar"""

    @staticmethod
    def _normalize_phone(phone):
        """Telefon numarasını normalize eder (karşılaştırma için)"""
        if not phone:
            return None
        # Boşluk, tire, parantez gibi karakterleri kaldır
        normalized = ''.join(filter(str.isdigit, phone))
        return normalized if normalized else None

    @staticmethod
    def send_sms(env, partner, message, record_name=''):
        """
        SMS gönderir. Hem mobile hem phone alanlarını kontrol eder.
        Aynı numara varsa sadece bir kere, farklıysa ikisine de gönderir.
        
        Args:
            env: Odoo environment
            partner: res.partner record (telefon numarası olmalı)
            message: SMS mesajı
            record_name: Kayıt adı (log için)
            
        Returns:
            bool: Başarılı ise True, değilse False
        """
        if not partner:
            _logger.warning(
                f"SMS gönderilemedi: Partner yok - Kayıt: {record_name}"
            )
            return False
        
        # Mobile ve phone alanlarını al
        mobile = partner.mobile or ''
        phone = partner.phone or ''
        
        # Normalize et (karşılaştırma için)
        mobile_normalized = SMSHelper._normalize_phone(mobile)
        phone_normalized = SMSHelper._normalize_phone(phone)
        
        # Hiç telefon numarası yoksa
        if not mobile_normalized and not phone_normalized:
            _logger.warning(
                f"SMS gönderilemedi: Partner'da telefon numarası yok - "
                f"Kayıt: {record_name}, Partner: {partner.name}"
            )
            return False
        
        # Gönderilecek numaraları belirle
        numbers_to_send = []
        
        # Aynı numara mı kontrol et
        if mobile_normalized and phone_normalized:
            if mobile_normalized == phone_normalized:
                # Aynı numara - sadece bir kere gönder
                numbers_to_send = [mobile]  # mobile öncelikli
                _logger.info(f"Aynı numara tespit edildi - sadece bir kere gönderilecek: {mobile}")
            else:
                # Farklı numaralar - ikisine de gönder
                numbers_to_send = [mobile, phone]
                _logger.info(f"Farklı numaralar tespit edildi - ikisine de gönderilecek: {mobile}, {phone}")
        elif mobile_normalized:
            # Sadece mobile var
            numbers_to_send = [mobile]
        elif phone_normalized:
            # Sadece phone var
            numbers_to_send = [phone]
        
        # SMS'leri gönder
        success_count = 0
        for number in numbers_to_send:
            if not number or not number.strip():
                continue
                
            try:
                # SMS'i doğru yöntemle gönder
                sms = env['sms.sms'].create({
                    'number': number.strip(),
                    'body': message,
                    'partner_id': partner.id,
                })
                sms.send()
                success_count += 1
                _logger.info(f"SMS gönderildi: {record_name} - {number.strip()}")
            except Exception as e:
                # SMS hatası logu
                _logger.error(f"SMS hatası: {record_name} - Numara: {number} - Hata: {str(e)}")
        
        return success_count > 0

