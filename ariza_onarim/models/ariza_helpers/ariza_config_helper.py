# -*- coding: utf-8 -*-
"""
Arıza Config Helper - Sistem parametreleri ve varsayılan değerler
"""

import logging
from ..ariza_constants import DefaultValues

_logger = logging.getLogger(__name__)


class ArizaConfigHelper:
    """Sistem parametreleri okuma"""

    @staticmethod
    def get_default_driver_id(env):
        """
        Default sürücü ID'sini system parameter'dan alır.
        System parameter yoksa veya geçersizse constants'tan default değeri kullanır.
        """
        try:
            driver_id_str = env['ir.config_parameter'].sudo().get_param('ariza_onarim.default_driver_id')
            if driver_id_str:
                driver_id = int(driver_id_str)
                driver_partner = env['res.partner'].browse(driver_id)
                if driver_partner.exists():
                    return driver_id
                _logger.warning(f"System parameter'daki sürücü ID ({driver_id}) geçersiz. Default kullanılıyor.")
        except (ValueError, TypeError) as e:
            _logger.warning(f"System parameter'dan sürücü ID okunamadı: {str(e)}. Default kullanılıyor.")
        except Exception as e:
            _logger.error(f"System parameter okuma hatası: {str(e)}. Default kullanılıyor.")
        return DefaultValues.DEFAULT_DRIVER_ID
