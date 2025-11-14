# -*- coding: utf-8 -*-
"""
SMS Helper - SMS işlemleri için helper metodlar
"""

import logging

_logger = logging.getLogger(__name__)


class SMSHelper:
    """SMS işlemleri için helper metodlar"""

    @staticmethod
    def send_sms(env, partner, message, record_name=''):
        """
        SMS gönderir.
        
        Args:
            env: Odoo environment
            partner: res.partner record (telefon numarası olmalı)
            message: SMS mesajı
            record_name: Kayıt adı (log için)
            
        Returns:
            bool: Başarılı ise True, değilse False
        """
        # Önce mobile, yoksa phone kullan
        phone_number = partner.mobile or partner.phone if partner else None
        if not partner or not phone_number:
            _logger.warning(
                f"SMS gönderilemedi: Partner veya telefon yok - "
                f"Kayıt: {record_name}"
            )
            return False
        
        try:
            # SMS'i doğru yöntemle gönder - sudo() ile herkes SMS gönderebilsin
            sms = env['sms.sms'].sudo().create({
                'number': phone_number,
                'body': message,
                'partner_id': partner.id,
            })
            sms.sudo().send()
            
            # Başarılı SMS logu
            _logger.info(f"SMS gönderildi: {record_name} - {phone_number}")
            return True
            
        except Exception as e:
            # SMS hatası logu
            _logger.error(f"SMS hatası: {record_name} - {str(e)}")
            return False

