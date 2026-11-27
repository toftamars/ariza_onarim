# -*- coding: utf-8 -*-
"""
B Stok kartı: tamirli ürünün indirimli satılan kopyası.

Kart ana ürüne ve indirim oranına bağlıdır (ürün + oran başına tek kart).
Kod: ANAKOD-BSTOK<oran> (ör. GRG14-SB-BSTOK15). İndirimi kart fiyatı değil,
"B-STOK" promosyonu verir: kart o oranın promosyon ürün listesine eklenir.
Modül promosyonun kendi ayarlarına (kod gereksinimi, kasalar) dokunmaz.

Bu modeldeki işlemler yalnız Python'dan (dönüşüm akışından) çağrılır; hepsi
alt çizgiyle başlar, RPC ile çağrılamaz.
"""

import logging
import random

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)

# Kasada ayrılmış önekler (21/22/23 tartı-fiyat-indirim, 041-043, 10, 414) dışı;
# 29 ile başlayan 13 haneli EAN, mevcutlarla çakışma kontrolüyle üretilir.
B_BARKOD_ONEKI = '29'
B_KOD_EKI = '-BSTOK'
# B-STOK promosyonlarını tanıma: ad ya da kod bu ifadeleri içerir
B_PROMOSYON_ADLARI = ('B-STOK', 'BSTOK')


def oran_metni(oran):
    """15.0 -> '15', 12.5 -> '12.5'"""
    return '%g' % oran


class ProductProduct(models.Model):
    _inherit = 'product.product'

    b_kaynak_urun_id = fields.Many2one(
        'product.product', string='B Stok Ana Ürünü', index=True, copy=False,
        help='Bu kart bir B Stok kartıysa, kopyalandığı ana ürün.')
    b_indirim_orani = fields.Float(
        string='B Stok İndirim Oranı (%)', copy=False,
        help='Bu B Stok kartının bağlı olduğu B-STOK promosyon oranı.')


class ArizaBStokKart(models.AbstractModel):
    """B Stok kartını bulma/açma ve promosyona bağlama işlemleri."""
    _name = 'ariza.b.stok.kart'
    _description = 'B Stok Kartı İşlemleri'

    # ---------------------------------------------------------------- promosyon
    @api.model
    def _b_promosyonlari(self, company):
        """Aktif, 'belirli ürünlerde yüzde indirim' veren B-STOK promosyonları.
        Tüm siparişe indirim yapanlar (ör. eski B-STOK%10, id 20) hariç tutulur."""
        Program = self.env['coupon.program'].sudo()
        ad_domain = ['|'] * (len(B_PROMOSYON_ADLARI) * 2 - 1)
        for ifade in B_PROMOSYON_ADLARI:
            ad_domain += [('name', 'ilike', ifade), ('promo_code', 'ilike', ifade)]
        return Program.search([
            ('active', '=', True),
            ('program_type', '=', 'promotion_program'),
            ('reward_type', '=', 'discount'),
            ('discount_type', '=', 'percentage'),
            ('discount_apply_on', '=', 'specific_products'),
            ('company_id', 'in', [company.id, False]),
        ] + ad_domain)

    @api.model
    def _oran_secenekleri(self, company):
        """Sihirbazdaki oran listesi: [('15', '%15'), ...] (promosyon adından değil
        ödülün gerçek yüzdesinden; adlar tutarsız)."""
        oranlar = sorted(set(self._b_promosyonlari(company).mapped('discount_percentage')))
        return [(oran_metni(o), '%%%s' % oran_metni(o)) for o in oranlar if o > 0]

    @api.model
    def _promosyona_bagla(self, b_urun, oran, company):
        """Kartı oranın promosyon listesine ekler, diğer B-STOK listelerinden çıkarır.
        Döner: (eklenen programlar, uyarı metni veya '')."""
        self.env['ariza.b.stok.donusum']._yonetici_mi()
        programlar = self._b_promosyonlari(company)
        hedef = programlar.filtered(
            lambda p: float_compare(p.discount_percentage, oran, precision_digits=2) == 0)
        if not hedef:
            raise UserError(_('%%%s için aktif B-STOK promosyonu bulunamadı.') % oran_metni(oran))
        for program in hedef:
            if b_urun not in program.discount_specific_product_ids:
                program.write({'discount_specific_product_ids': [(4, b_urun.id)]})
        for program in programlar - hedef:
            if b_urun in program.discount_specific_product_ids:
                program.write({'discount_specific_product_ids': [(3, b_urun.id)]})
        return hedef, self._kasa_uyarisi(hedef, oran)

    @api.model
    def _kasa_uyarisi(self, programlar, oran):
        if 'pos.config' not in self.env:
            return ''
        PosConfig = self.env['pos.config'].sudo()
        if 'promo_program_ids' not in PosConfig._fields:
            return ''
        domain = [('promo_program_ids', 'in', programlar.ids)]
        if 'use_coupon_programs' in PosConfig._fields:
            domain.append(('use_coupon_programs', '=', True))
        if PosConfig.search_count(domain):
            return ''
        return _('Dikkat: %%%s promosyonu hiçbir kasada açık değil; '
                 'kasada indirim düşmez.') % oran_metni(oran)

    # ---------------------------------------------------------------- kart
    @api.model
    def _kart_kodu(self, ana_urun, oran):
        if not ana_urun.default_code:
            raise UserError(_('"%s" ürününün iç referansı (kodu) yok; '
                              'B Stok kartı kodu üretilemez.') % ana_urun.display_name)
        return '%s%s%s' % (ana_urun.default_code.strip(), B_KOD_EKI, oran_metni(oran))

    @api.model
    def _mevcut_kart(self, ana_urun, oran):
        """Ürün + oran için açılmış kart (arşivli dahil). Önce bağlantıya,
        yoksa koda bakar; koda göre bulunan kart başka bir ana ürüne bağlıysa
        kullanılmaz."""
        Urun = self.env['product.product'].with_context(active_test=False)
        kart = Urun.search([
            ('b_kaynak_urun_id', '=', ana_urun.id),
            ('b_indirim_orani', '=', oran),
        ], limit=1)
        if kart or not ana_urun.default_code:
            return kart
        kart = Urun.search([('default_code', '=', self._kart_kodu(ana_urun, oran))], limit=1)
        if kart and kart.b_kaynak_urun_id and kart.b_kaynak_urun_id != ana_urun:
            raise UserError(_('%s kodlu ürün başka bir ana ürünün B Stok kartı; '
                              'kodu kontrol edin.') % kart.default_code)
        return kart

    @api.model
    def _kart_uygun_mu(self, kart, ana_urun, company):
        """Yeniden kullanılacak kartın stok aktarımına uygunluğu."""
        sorunlar = []
        if kart.type != 'product':
            sorunlar.append(_('stoklanabilir ürün değil'))
        if kart.tracking != 'none':
            sorunlar.append(_('seri/lot takipli'))
        if kart.uom_id != ana_urun.uom_id:
            sorunlar.append(_('ölçü birimi ana üründen farklı'))
        if kart.company_id and kart.company_id != company:
            sorunlar.append(_('başka şirkete ait'))
        if len(kart.product_tmpl_id.with_context(active_test=False).product_variant_ids) > 1:
            sorunlar.append(_('varyantlı'))
        if sorunlar:
            raise UserError(_('%(kod)s kartı kullanılamıyor: %(sorun)s.') % {
                'kod': kart.default_code, 'sorun': ', '.join(sorunlar)})

    @api.model
    def _kart_bul_veya_ac(self, ana_urun, oran, company):
        """Döner: (kart, yeni_mi)."""
        self.env['ariza.b.stok.donusum']._yonetici_mi()
        kart = self._mevcut_kart(ana_urun, oran)
        if kart:
            self._kart_uygun_mu(kart, ana_urun, company)
            # Arşivli kart: şablon ve varyant ayrı ayrı açılır
            sablon = kart.product_tmpl_id.with_context(active_test=False)
            if not sablon.active:
                sablon.write({'active': True})
            if not kart.active:
                kart.write({'active': True})
            if kart.b_kaynak_urun_id != ana_urun or kart.b_indirim_orani != oran:
                kart.write({'b_kaynak_urun_id': ana_urun.id, 'b_indirim_orani': oran})
            return kart, False
        return self._kart_ac(ana_urun, oran), True

    @api.model
    def _kart_ac(self, ana_urun, oran):
        sablon = ana_urun.product_tmpl_id
        yeni_sablon = sablon.copy(default={
            'name': '%s (B-STOK %%%s)' % (sablon.name, oran_metni(oran)),
        })
        if len(yeni_sablon.product_variant_ids) != 1:
            raise UserError(_('B Stok kartı tek varyantlı açılamadı (%s).') % sablon.display_name)
        kart = yeni_sablon.product_variant_ids
        kart.write({
            'default_code': self._kart_kodu(ana_urun, oran),
            'barcode': self._yeni_barkod(),
            'b_kaynak_urun_id': ana_urun.id,
            'b_indirim_orani': oran,
        })
        _logger.info('B Stok kartı açıldı: %s (ana ürün %s, %%%s)',
                     kart.default_code, ana_urun.id, oran_metni(oran))
        return kart

    @api.model
    def _yeni_barkod(self):
        Urun = self.env['product.product'].with_context(active_test=False).sudo()
        Paket = self.env['product.packaging'].sudo()
        for _deneme in range(20):
            govde = B_BARKOD_ONEKI + ''.join(random.choice('0123456789') for _i in range(10))
            barkod = govde + self._ean13_kontrol_hanesi(govde)
            if (not Urun.search_count([('barcode', '=', barkod)])
                    and not Paket.search_count([('barcode', '=', barkod)])):
                return barkod
        raise UserError(_('Benzersiz barkod üretilemedi, lütfen tekrar deneyin.'))

    @staticmethod
    def _ean13_kontrol_hanesi(govde12):
        toplam = sum(int(h) * (3 if i % 2 else 1) for i, h in enumerate(govde12))
        return str((10 - toplam % 10) % 10)
