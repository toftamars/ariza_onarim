# -*- coding: utf-8 -*-
"""
Arıza Search Helper - Özel domain genişletme (urun alanı araması)
"""


class ArizaSearchHelper:
    """Arıza kaydı özel arama mantığı"""

    @staticmethod
    def expand_urun_domain(domain):
        """
        'urun' alanı için domain'i genişletir.
        urun Char + magaza_urun_id.name + magaza_urun_id.default_code'da arar.
        """
        new_domain = []
        i = 0
        while i < len(domain):
            item = domain[i]
            if isinstance(item, (list, tuple)) and len(item) == 3:
                field, operator, value = item
                if field == 'urun' and operator in ('ilike', 'like', '=', '!='):
                    new_domain.extend([
                        '|',
                        ('urun', operator, value),
                        '|',
                        ('magaza_urun_id.name', operator, value),
                        ('magaza_urun_id.default_code', operator, value)
                    ])
                else:
                    new_domain.append(item)
            else:
                new_domain.append(item)
            i += 1
        return new_domain
