# -*- coding: utf-8 -*-
"""
Arıza Create Service - Kayıt oluşturma mantığı
"""

import logging
from ..ariza_constants import ArizaStates, ArizaTipi, IslemTipi
from . import hedef_konum_helper
from . import sequence_helper

_logger = logging.getLogger(__name__)


class ArizaCreateService:
    """Arıza kaydı oluşturma servisi"""

    @staticmethod
    def prepare_vals(env, vals):
        """Create öncesi vals hazırlığı - varsayılanlar, hedef konum vb."""
        if not vals.get('analitik_hesap_id') and vals.get('sorumlu_id'):
            sorumlu = env['res.users'].browse(vals['sorumlu_id'])
            if sorumlu and sorumlu.employee_id and sorumlu.employee_id.magaza_id:
                vals['analitik_hesap_id'] = sorumlu.employee_id.magaza_id.id
        if not vals.get('name'):
            vals['name'] = sequence_helper.SequenceHelper.generate_ariza_number(env)
        if not vals.get('state'):
            vals['state'] = ArizaStates.DRAFT
        if not vals.get('islem_tipi'):
            vals['islem_tipi'] = IslemTipi.ARIZA_KABUL
        if vals.get('ariza_tipi') and vals.get('teknik_servis') and not vals.get('hedef_konum_id'):
            tedarikci = env['res.partner'].browse(vals.get('tedarikci_id')) if vals.get('tedarikci_id') else None
            konum = hedef_konum_helper.HedefKonumHelper.get_hedef_konum(
                env,
                vals.get('teknik_servis'),
                vals.get('ariza_tipi'),
                company_id=vals.get('company_id') or env.company.id,
                tedarikci_id=tedarikci,
            )
            if konum:
                vals['hedef_konum_id'] = konum.id
        if not vals.get('ariza_tipi'):
            vals['ariza_tipi'] = ArizaTipi.MUSTERI
        if not vals.get('sorumlu_id'):
            vals['sorumlu_id'] = env.user.id

    @staticmethod
    def post_create(records):
        """Create sonrası - barkod, chatter mesajı"""
        for record in records:
            if record.ariza_tipi == ArizaTipi.MUSTERI and not record.barcode:
                record.barcode = record.env['ir.sequence'].next_by_code('ariza.kayit.barcode') or False
                if record.barcode:
                    _logger.info(f"Müşteri ürünü barkod oluşturuldu: {record.name} - Barkod: {record.barcode}")
        for record in records:
            try:
                ariza_tanimi = record.ariza_tanimi or "Arıza tanımı belirtilmemiş"
                record.message_post(body=f"Arıza Tanımı: {ariza_tanimi}", message_type='notification')
            except Exception as e:
                _logger.error(f"Chatter mesajı eklenemedi: {record.name} - {str(e)}")
