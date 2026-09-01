# -*- coding: utf-8 -*-
"""
Düzeltme Wizard - Onarım/garanti bilgilerinin geriye dönük düzeltilmesi

Onarım bilgileri "Onayla" adımında ariza.onarim.bilgi.wizard ile bir kez
doldurulur ve sonrasında hiçbir formda düzenlenebilir değildir. Yanlış girilen
garanti kapsamı gibi bilgilerin düzeltilebilmesi için bu wizard kullanılır.
Her düzeltme, gerekçesi ve eski/yeni değerleriyle birlikte chatter'a yazılır.
"""

import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from ..models.ariza_constants import ArizaStates, ArizaTipi, GarantiKapsam

_logger = logging.getLogger(__name__)

# Düzeltilebilir alanlar: (alan adı, etiket, selection listesi veya None)
DUZELTILEBILIR_ALANLAR = [
    ('garanti_kapsaminda_mi', 'Garanti Kapsamında mı?', GarantiKapsam.SELECTION),
    ('onarim_bilgisi', 'Onarım Bilgisi', None),
    ('ucret_bilgisi', 'Ücret Bilgisi', None),
    ('onarim_ucreti', 'Onarım Ücreti', None),
    ('onarim_disi_aciklama', 'Onarım Dışı Açıklama', None),
]

PARA_TOLERANSI = 0.01


def _ayni_para(a, b):
    """İki parasal değeri kuruş hassasiyetinde karşılaştırır"""
    return abs((a or 0.0) - (b or 0.0)) < PARA_TOLERANSI


def _goster(deger, selection):
    """Değeri chatter'da okunabilir metne çevirir"""
    if deger in (False, None, ''):
        return '(boş)'
    if selection:
        return dict(selection).get(deger, deger)
    return deger


class ArizaDuzeltmeWizard(models.TransientModel):
    _name = 'ariza.duzeltme.wizard'
    _description = 'Onarım Bilgisi Düzeltme Sihirbazı'

    ariza_id = fields.Many2one('ariza.kayit', string='Arıza Kaydı', required=True, readonly=True)
    ariza_adi = fields.Char(string='Arıza No', related='ariza_id.name', readonly=True)
    ariza_tipi = fields.Selection(related='ariza_id.ariza_tipi', string='Arıza Tipi', readonly=True)
    urun = fields.Char(related='ariza_id.urun_gosterimi', string='Ürün', readonly=True)
    currency_id = fields.Many2one(
        'res.currency', string='Para Birimi',
        default=lambda self: self.env.company.currency_id
    )

    garanti_kapsaminda_mi = fields.Selection(
        GarantiKapsam.SELECTION,
        string='Garanti Kapsamında mı?'
    )
    onarim_bilgisi = fields.Text(string='Onarım Bilgisi')
    ucret_bilgisi = fields.Char(string='Ücret Bilgisi')
    onarim_ucreti = fields.Monetary(string='Onarım Ücreti', currency_field='currency_id')
    onarim_disi_aciklama = fields.Text(string='Onarım Dışı Açıklama')

    duzeltme_nedeni = fields.Text(
        string='Düzeltme Nedeni',
        required=True,
        help='Bu düzeltmenin neden yapıldığı. Kayıt geçmişine (chatter) yazılır.'
    )

    @api.model
    def default_get(self, fields_list):
        """Mevcut değerleri wizard'a yükle (context'ten gelmezse active_id'den)"""
        res = super().default_get(fields_list)
        ariza_id = res.get('ariza_id') or self._context.get('active_id')
        if not ariza_id:
            return res
        ariza = self.env['ariza.kayit'].browse(ariza_id)
        res.update({
            'ariza_id': ariza.id,
            'garanti_kapsaminda_mi': ariza.garanti_kapsaminda_mi,
            'onarim_bilgisi': ariza.onarim_bilgisi,
            'ucret_bilgisi': ariza.ucret_bilgisi,
            'onarim_ucreti': ariza.onarim_ucreti,
            'onarim_disi_aciklama': ariza.onarim_disi_aciklama,
            'currency_id': (ariza.currency_id or self.env.company.currency_id).id,
        })
        return res

    def _yeni_degerler(self):
        """Kaydedilecek yeni değerleri döner (garanti kuralı uygulanmış hâliyle)"""
        yeni = {alan: self[alan] for alan, _etiket, _sel in DUZELTILEBILIR_ALANLAR}
        # Garanti kapsamındaysa onarım ücreti sıfırlanır
        # (ariza.onarim.bilgi.wizard ile aynı kural). Mağaza ürününde garanti ve
        # ücret alanları kullanılmadığı için kural uygulanmaz — aksi hâlde
        # görünmeyen bir alan yüzünden ücret sessizce sıfırlanabilirdi.
        if (self.ariza_tipi != ArizaTipi.MAGAZA
                and self.garanti_kapsaminda_mi in (GarantiKapsam.EVET, GarantiKapsam.URUN_DEGISIMI)):
            yeni['onarim_ucreti'] = 0.0
        return yeni

    def _degisiklikleri_topla(self, yeni_degerler):
        """Kayıt ile yeni değerler arasındaki farkları döner

        Dönen her eleman: (alan, etiket, eski_deger, yeni_deger, selection)
        """
        ariza = self.ariza_id
        degisiklikler = []
        for alan, etiket, selection in DUZELTILEBILIR_ALANLAR:
            eski = ariza[alan]
            yeni = yeni_degerler[alan]
            if alan == 'onarim_ucreti':
                if _ayni_para(eski, yeni):
                    continue
            elif (eski or False) == (yeni or False):
                continue
            degisiklikler.append((alan, etiket, eski, yeni, selection))
        return degisiklikler

    def action_duzeltmeyi_kaydet(self):
        """Düzeltmeyi kaydeder ve chatter'a eski/yeni değerlerle birlikte yazar"""
        self.ensure_one()
        ariza = self.ariza_id

        if not self.env.user.has_group('ariza_onarim.group_ariza_manager'):
            raise UserError(_('Bu işlemi sadece yetkili kullanıcılar yapabilir.'))
        if ariza.state not in ArizaStates.DUZELTILEBILIR:
            raise UserError(_(
                'Bu aşamadaki kayıtlar için düzeltme yapılamaz. Onarım bilgileri '
                'henüz doldurulmamış kayıtlarda bilgiler onarım akışı içinde girilir.'
            ))
        if not (self.duzeltme_nedeni or '').strip():
            raise UserError(_('Düzeltme nedeni girmeniz zorunludur.'))

        yeni_degerler = self._yeni_degerler()
        degisiklikler = self._degisiklikleri_topla(yeni_degerler)
        if not degisiklikler:
            raise UserError(_('Herhangi bir değişiklik yapılmadı.'))

        ariza.write({alan: yeni_degerler[alan] for alan, _e, _es, _y, _s in degisiklikler})

        satirlar = ''.join(
            '<li>%s: <b>%s</b> &rarr; <b>%s</b></li>' % (
                etiket, _goster(eski, selection), _goster(yeni, selection)
            )
            for _alan, etiket, eski, yeni, selection in degisiklikler
        )
        ariza.message_post(
            body=(
                'Kayıt bilgileri düzeltildi.<ul>%s</ul>'
                'Düzeltme nedeni: %s<br/>Düzelten: %s'
            ) % (satirlar, self.duzeltme_nedeni, self.env.user.name),
            subject='Bilgi Düzeltme',
            message_type='notification'
        )

        # Ürün Değişimi'ne düzeltilirse bildirim e-postası otomatik gitmez:
        # düzeltme bir iş akışı adımı değildir, yan etki (e-posta/SMS) tetiklemez.
        if (self.garanti_kapsaminda_mi == GarantiKapsam.URUN_DEGISIMI
                and ariza.ariza_tipi == ArizaTipi.MUSTERI):
            ariza.message_post(
                body=('Uyarı: Garanti kapsamı "Ürün Değişimi" olarak düzeltildi. '
                      'Ürün Değişimi bildirim e-postası bu düzeltmeyle otomatik gönderilmez; '
                      'gerekiyorsa ilgili birime elle bilgi veriniz.'),
                message_type='notification'
            )

        _logger.info(
            "Arıza kaydı düzeltildi: %s - Alanlar: %s - Kullanıcı: %s",
            ariza.name, ', '.join(d[0] for d in degisiklikler), self.env.user.login
        )
        return {'type': 'ir.actions.act_window_close'}
