# -*- coding: utf-8 -*-
"""
Sequence Helper - Sequence işlemleri için helper metodlar
"""

import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class SequenceHelper:
    """Sequence işlemleri için helper metodlar"""

    @staticmethod
    def generate_ariza_number(env, model_name='ariza.kayit'):
        """
        Arıza numarası oluşturur (sequence veya manuel).
        
        Args:
            env: Odoo environment
            model_name: Model adı (varsayılan: 'ariza.kayit')
            
        Returns:
            str: Arıza numarası
        """
        try:
            # Önce sequence'den dene
            sequence_number = env['ir.sequence'].next_by_code(model_name)
            if sequence_number:
                return sequence_number
        except Exception as seq_error:
            _logger.warning(
                f"Sequence bulunamadı, manuel numara oluşturuluyor: "
                f"{str(seq_error)}"
            )
        
        # Sequence bulunamazsa manuel numara oluştur
        current_year = datetime.now().year
        last_record = env[model_name].search(
            [('name', '!=', False)],
            order='id desc',
            limit=1
        )
        
        if last_record and last_record.name != 'New':
            try:
                last_number = int(last_record.name.split('/')[-1])
                new_number = last_number + 1
            except (ValueError, IndexError) as parse_error:
                _logger.warning(
                    f"Son kayıt numarası parse edilemedi, 1'den başlanıyor: "
                    f"{str(parse_error)} - Kayıt: {last_record.name if last_record else 'N/A'}"
                )
                new_number = 1
        else:
            new_number = 1
        
        return f"ARZ/{current_year}/{new_number:05d}"

