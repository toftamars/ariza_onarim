# -*- coding: utf-8 -*-
"""
SMS Helper - SMS Service Layer

This service provides centralized SMS sending functionality with
proper error handling, logging, and retry logic.

Best Practices Applied:
- Proper exception handling
- Comprehensive logging
- Phone number validation
- SMS queue management via Odoo's sms.sms model
- Sudo usage for permission bypass (configurable)

Author: Arıza Onarım Module - Refactored
License: LGPL-3
"""

import logging
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SMSHelper:
    """
    SMS Service for Repair Module

    Provides centralized SMS sending through Odoo's native SMS module
    with validation, error handling, and logging.
    """

    @staticmethod
    def send_sms(env, partner, message, record_name='', raise_on_error=False):
        """
        Send SMS message to partner.

        Uses Odoo's native SMS module (sms.sms model) for queue-based sending.
        Automatically handles phone number validation and error logging.

        Args:
            env: Odoo environment
            partner (res.partner): Partner record with phone/mobile number
            message (str): SMS message content
            record_name (str, optional): Record name for logging context
            raise_on_error (bool): Raise UserError on failure instead of silent return

        Returns:
            tuple: (bool success, str error_message)

        Raises:
            UserError: If raise_on_error=True and sending fails

        Example:
            success, error = SMSHelper.send_sms(
                env, partner, "Ürün hazır!", record_name="ARZ-2024-001"
            )
            if not success:
                _logger.warning(f"SMS failed: {error}")
        """
        # Validate partner
        if not partner:
            error_msg = _("SMS gönderilemedi: Partner belirtilmemiş.")
            _logger.warning(f"{error_msg} - Kayıt: {record_name}")
            if raise_on_error:
                raise UserError(error_msg)
            return False, error_msg

        # Get phone number (prefer mobile over phone)
        phone_number = partner.mobile or partner.phone

        # Validate phone number
        if not phone_number:
            error_msg = _(
                "SMS gönderilemedi: Partner için telefon numarası bulunamadı.\n"
                "Partner: %s"
            ) % partner.name
            _logger.warning(f"{error_msg} - Kayıt: {record_name}")
            if raise_on_error:
                raise UserError(error_msg)
            return False, error_msg

        # Validate message
        if not message or not message.strip():
            error_msg = _("SMS gönderilemedi: Mesaj içeriği boş.")
            _logger.warning(f"{error_msg} - Kayıt: {record_name}")
            if raise_on_error:
                raise UserError(error_msg)
            return False, error_msg

        try:
            # Create SMS record - use sudo() to bypass permission checks
            # This allows all users to send SMS regardless of their access rights
            sms = env['sms.sms'].sudo().create({
                'number': phone_number,
                'body': message,
                'partner_id': partner.id,
            })

            # Send SMS immediately
            sms.sudo().send()

            # Success logging
            _logger.info(
                f"SMS sent successfully - Record: {record_name}, "
                f"Partner: {partner.name}, Phone: {phone_number}"
            )
            return True, ''

        except Exception as e:
            # Error logging with full context
            error_msg = _(
                "SMS gönderimi başarısız oldu.\n"
                "Kayıt: %s\n"
                "Partner: %s\n"
                "Telefon: %s\n"
                "Hata: %s"
            ) % (record_name, partner.name, phone_number, str(e))

            _logger.error(f"SMS send error: {error_msg}")

            if raise_on_error:
                raise UserError(error_msg)

            return False, str(e)

    @staticmethod
    def send_sms_batch(env, partner_message_list, raise_on_error=False):
        """
        Send SMS to multiple partners in batch.

        Processes multiple SMS sends and collects results for each.
        Continues sending even if some fail (unless raise_on_error=True).

        Args:
            env: Odoo environment
            partner_message_list (list): List of (partner, message, record_name) tuples
            raise_on_error (bool): Stop and raise error on first failure

        Returns:
            dict: Results dictionary with 'success', 'failed', and 'total' counts
                  {
                      'success': int,
                      'failed': int,
                      'total': int,
                      'failures': [(partner, error_msg), ...]
                  }

        Example:
            results = SMSHelper.send_sms_batch(env, [
                (partner1, "Message 1", "ARZ-001"),
                (partner2, "Message 2", "ARZ-002"),
            ])
            _logger.info(f"SMS batch: {results['success']}/{results['total']} sent")
        """
        results = {
            'success': 0,
            'failed': 0,
            'total': len(partner_message_list),
            'failures': []
        }

        for partner, message, record_name in partner_message_list:
            success, error = SMSHelper.send_sms(
                env, partner, message, record_name, raise_on_error=raise_on_error
            )

            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
                results['failures'].append((partner, error))

        _logger.info(
            f"SMS batch completed: {results['success']}/{results['total']} successful, "
            f"{results['failed']} failed"
        )

        return results

    @staticmethod
    def validate_phone_number(phone_number):
        """
        Validate phone number format (basic validation).

        Checks for minimum length and basic format rules.

        Args:
            phone_number (str): Phone number to validate

        Returns:
            tuple: (bool is_valid, str error_message)

        Example:
            is_valid, error = SMSHelper.validate_phone_number("+905551234567")
            if not is_valid:
                raise UserError(error)
        """
        if not phone_number:
            return False, _("Telefon numarası boş.")

        # Remove common separators
        cleaned = phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')

        # Basic length check (Turkish mobile: 10-13 digits with country code)
        if len(cleaned) < 10:
            return False, _("Telefon numarası çok kısa (min 10 karakter).")

        if len(cleaned) > 15:
            return False, _("Telefon numarası çok uzun (max 15 karakter).")

        # Check if contains mostly digits (allow + at start)
        if cleaned.startswith('+'):
            cleaned = cleaned[1:]

        if not cleaned.isdigit():
            return False, _("Telefon numarası geçersiz karakter içeriyor.")

        return True, ''

    @staticmethod
    def format_sms_template(template, **kwargs):
        """
        Format SMS template with variables.

        Safe template formatting with error handling for missing variables.

        Args:
            template (str): SMS template with {variable} placeholders
            **kwargs: Template variables

        Returns:
            str: Formatted SMS message

        Example:
            message = SMSHelper.format_sms_template(
                "Sayın {customer_name}, {product_name} ürününüz hazır.",
                customer_name="Ahmet Yılmaz",
                product_name="Gitar"
            )
        """
        try:
            return template.format(**kwargs)
        except KeyError as e:
            _logger.warning(f"SMS template formatting error: Missing variable {e}")
            # Return template as-is if formatting fails
            return template
        except Exception as e:
            _logger.error(f"SMS template formatting error: {str(e)}")
            return template
