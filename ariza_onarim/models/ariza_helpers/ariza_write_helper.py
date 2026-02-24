# -*- coding: utf-8 -*-
"""
Arıza Write Helper - write() override mantığı

Otomatik atanan hedef konum değiştirilemez.
"""

from . import hedef_konum_helper


class ArizaWriteHelper:
    """write() hedef konum koruması"""

    @staticmethod
    def filter_hedef_konum_protected(recordset):
        """
        Hedef konumu otomatik atanan kayıtları filtreler.

        Returns:
            tuple: (otomatik_recordset, diger_recordset)
        """
        otomatik = recordset.filtered(
            lambda r: hedef_konum_helper.HedefKonumHelper.hedef_konum_otomatik_mi(
                r.ariza_tipi, r.teknik_servis, r.tedarikci_id
            )
        )
        diger = recordset - otomatik
        return (otomatik, diger)

    @staticmethod
    def vals_without_hedef_konum(vals):
        """vals dict'ten hedef_konum_id'yi çıkarır"""
        return {k: v for k, v in vals.items() if k != 'hedef_konum_id'}
