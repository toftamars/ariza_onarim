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
        if not partner or not partner.phone:
            _logger.warning(
                f"SMS gönderilemedi: Partner veya telefon yok - "
                f"Kayıt: {record_name}"
            )
            return False
        
        try:
            # SMS'i doğru yöntemle gönder
            sms = env['sms.sms'].create({
                'number': partner.phone,
                'body': message,
                'partner_id': partner.id,
            })
            sms.send()
            
            # Başarılı SMS logu
            _logger.info(f"SMS gönderildi: {record_name} - {partner.phone}")
            return True
            
        except Exception as e:
            # SMS hatası logu
            _logger.error(f"SMS hatası: {record_name} - {str(e)}")
            return False

