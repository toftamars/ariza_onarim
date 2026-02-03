# -*- coding: utf-8 -*-
"""
Sequence Helper - Sequence Generation Service Layer

This service provides centralized sequence/numbering management with
fallback strategies and proper error handling.

Best Practices Applied:
- Proper exception handling
- Fallback to manual numbering
- Year-based sequences
- Comprehensive logging
- Transaction safety

Author: Arıza Onarım Module - Refactored
License: LGPL-3
"""

import logging
from datetime import datetime
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SequenceHelper:
    """
    Sequence Service for Repair Module

    Provides automatic number generation with database sequence
    and manual fallback strategies.
    """

    @staticmethod
    def generate_ariza_number(env, model_name='ariza.kayit', force_new=False):
        """
        Generate repair record number (from sequence or manual fallback).

        Tries to use ir.sequence first. If sequence not found or fails,
        generates manual number in format: ARZ/YYYY/XXXXX

        Args:
            env: Odoo environment
            model_name (str): Model name for sequence lookup (default: 'ariza.kayit')
            force_new (bool): Force new number even if sequence exists

        Returns:
            str: Generated repair number (e.g., "ARZ/2024/00001")

        Example:
            number = SequenceHelper.generate_ariza_number(env)
            # Returns: "ARZ/2024/00123"
        """
        if not force_new:
            try:
                # Try to get next number from sequence
                sequence_number = env['ir.sequence'].next_by_code(model_name)
                if sequence_number:
                    _logger.debug(f"Number generated from sequence: {sequence_number}")
                    return sequence_number
            except Exception as seq_error:
                _logger.warning(
                    f"Sequence not found or failed, falling back to manual numbering: {str(seq_error)}"
                )

        # Fallback: Generate manual number
        return SequenceHelper._generate_manual_number(env, model_name)

    @staticmethod
    def _generate_manual_number(env, model_name):
        """
        Generate manual repair number in format: ARZ/YYYY/XXXXX

        Finds the last record and increments counter.
        Thread-safe through Odoo's transaction management.

        Args:
            env: Odoo environment
            model_name (str): Model name

        Returns:
            str: Manual repair number

        Format:
            ARZ / {current_year} / {5-digit_counter}
            Example: ARZ/2024/00123
        """
        current_year = datetime.now().year

        # Find last record (ordered by ID for consistency)
        last_record = env[model_name].search(
            [('name', '!=', False), ('name', '!=', 'New')],
            order='id desc',
            limit=1
        )

        new_number = 1  # Default starting number

        if last_record:
            try:
                # Parse last number: "ARZ/2024/00123" -> 123
                last_number_str = last_record.name.split('/')[-1]
                last_number = int(last_number_str)
                new_number = last_number + 1

                _logger.debug(
                    f"Last number parsed: {last_number}, new number: {new_number}"
                )
            except (ValueError, IndexError) as parse_error:
                _logger.warning(
                    f"Could not parse last record number, starting from 1. "
                    f"Error: {str(parse_error)}, Last record: {last_record.name}"
                )
                new_number = 1

        generated_number = f"ARZ/{current_year}/{new_number:05d}"
        _logger.info(f"Manual number generated: {generated_number}")
        return generated_number

    @staticmethod
    def ensure_sequence_exists(env, model_name='ariza.kayit', create_if_missing=True):
        """
        Ensure sequence exists for model. Optionally create if missing.

        Args:
            env: Odoo environment
            model_name (str): Model name for sequence
            create_if_missing (bool): Create sequence if not found

        Returns:
            ir.sequence: Sequence record or False

        Raises:
            UserError: If sequence not found and create_if_missing=False
        """
        # Check if sequence exists
        sequence = env['ir.sequence'].search([
            ('code', '=', model_name)
        ], limit=1)

        if sequence:
            _logger.debug(f"Sequence exists for {model_name}: {sequence.name}")
            return sequence

        if not create_if_missing:
            raise UserError(
                _("Sequence bulunamadı: %s\n\n"
                  "Lütfen Ayarlar > Teknik > Sequences menüsünden "
                  "gerekli sequence'i oluşturun.") % model_name
            )

        # Create new sequence
        current_year = datetime.now().year
        sequence = env['ir.sequence'].sudo().create({
            'name': f'Arıza Kayıt Sequence ({current_year})',
            'code': model_name,
            'prefix': f'ARZ/{current_year}/',
            'padding': 5,
            'number_next': 1,
            'number_increment': 1,
            'implementation': 'standard',
        })

        _logger.info(f"Created new sequence for {model_name}: {sequence.name}")
        return sequence

    @staticmethod
    def validate_number_format(number, expected_prefix='ARZ'):
        """
        Validate repair number format.

        Args:
            number (str): Number to validate
            expected_prefix (str): Expected prefix (default: 'ARZ')

        Returns:
            tuple: (bool is_valid, str error_message)

        Example:
            is_valid, error = SequenceHelper.validate_number_format("ARZ/2024/00123")
            if not is_valid:
                raise UserError(error)
        """
        if not number or number == 'New':
            return False, _("Geçersiz numara: boş veya 'New'")

        parts = number.split('/')
        if len(parts) != 3:
            return False, _(
                "Geçersiz numara formatı. Beklenen: %s/YYYY/XXXXX, "
                "Alınan: %s"
            ) % (expected_prefix, number)

        prefix, year, counter = parts

        if prefix != expected_prefix:
            return False, _(
                "Geçersiz prefix. Beklenen: %s, Alınan: %s"
            ) % (expected_prefix, prefix)

        try:
            year_int = int(year)
            if year_int < 2000 or year_int > 2100:
                return False, _("Geçersiz yıl: %s") % year
        except ValueError:
            return False, _("Yıl sayısal değil: %s") % year

        try:
            int(counter)
        except ValueError:
            return False, _("Sayaç sayısal değil: %s") % counter

        return True, ''

    @staticmethod
    def reset_yearly_sequence(env, model_name='ariza.kayit'):
        """
        Reset sequence counter for new year.

        Should be called at beginning of each year to reset counter to 1.
        Useful for cron jobs or manual year rollover.

        Args:
            env: Odoo environment
            model_name (str): Model name for sequence

        Returns:
            bool: True if reset successful

        Example:
            # In a cron job:
            SequenceHelper.reset_yearly_sequence(env)
        """
        current_year = datetime.now().year

        sequence = env['ir.sequence'].search([
            ('code', '=', model_name)
        ], limit=1)

        if not sequence:
            _logger.warning(f"No sequence found for {model_name}, cannot reset")
            return False

        # Update sequence for new year
        sequence.sudo().write({
            'prefix': f'ARZ/{current_year}/',
            'number_next': 1,
        })

        _logger.info(
            f"Sequence reset for new year: {sequence.name}, "
            f"prefix: ARZ/{current_year}/, counter: 1"
        )
        return True
