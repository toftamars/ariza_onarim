# -*- coding: utf-8 -*-
"""
B Stok dönüşümü: tamirli ürünü ARIZA konumunda B Stok kartına çevirir.

Elle yapılan işin aynısı: ana ürün o konumdan Envanter Düzenlemesi'ne çıkar,
B kart aynı konuma Envanter Düzenlemesi'nden girer; giriş, çıkışın değerleme
tutarıyla yapılır. Muhasebe kaydı bugünkü elle dönüşümün ürettiğiyle aynıdır
(iki taraf aynı hesaplara düşüyorsa net sıfır). Her dönüşüm kayıt altına alınır
ve ters hareketle geri alınabilir.

Kayıtlar kullanıcıya salt okunurdur; yalnız bu akış (yönetici kontrolünden
sonra sudo ile) oluşturur ve günceller.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare, float_is_zero

from .ariza_depo_stok import ARIZA_DEPO_KODU
from .b_stok_urun import oran_metni

_logger = logging.getLogger(__name__)

YONETICI_GRUBU = 'ariza_onarim.group_ariza_manager'
DURUM_SECENEKLERI = [
    ('a', 'A - Yeni gibi'),
    ('b', 'B - Hafif kusurlu'),
    ('c', 'C - Belirgin kusurlu'),
]


class ArizaBStokDonusum(models.Model):
    _name = 'ariza.b.stok.donusum'
    _description = 'B Stok Dönüşümü'
    _order = 'id desc'

    name = fields.Char(string='No', readonly=True, copy=False, default='/')
    company_id = fields.Many2one('res.company', string='Şirket', required=True, readonly=True)
    urun_id = fields.Many2one('product.product', string='Ana Ürün', required=True, readonly=True)
    b_urun_id = fields.Many2one('product.product', string='B Stok Kartı', required=True, readonly=True)
    b_kart_yeni = fields.Boolean(string='Kart Bu Dönüşümde Açıldı', readonly=True)
    konum_id = fields.Many2one('stock.location', string='Konum', required=True, readonly=True)
    envanter_konum_id = fields.Many2one('stock.location', string='Envanter Düzenlemesi Konumu',
                                        readonly=True)
    miktar = fields.Float(string='Adet', required=True, readonly=True,
                          digits='Product Unit of Measure')
    oran = fields.Float(string='İndirim (%)', required=True, readonly=True)
    durum = fields.Selection(DURUM_SECENEKLERI, string='Durum', readonly=True)
    not_metni = fields.Text(string='Not', readonly=True)
    birim_maliyet = fields.Float(string='Birim Maliyet', readonly=True, digits='Product Price')
    uyari = fields.Char(string='Uyarı', readonly=True)
    state = fields.Selection([('tamam', 'Tamamlandı'), ('geri_alindi', 'Geri Alındı')],
                             string='Durum (İşlem)', default='tamam', readonly=True)
    move_ids = fields.Many2many('stock.move', string='Stok Hareketleri', readonly=True, copy=False)

    # ---------------------------------------------------------------- yardımcılar
    @api.model
    def _yonetici_mi(self):
        if not self.env.user.has_group(YONETICI_GRUBU):
            raise AccessError(_('B Stok dönüşümünü yalnızca Arıza Onarım yöneticileri yapabilir.'))

    @api.model
    def _ariza_konumu_mu(self, konum):
        """Konum ARIZA deposunun altında bir iç konum mu?"""
        depo = self.env['stock.warehouse'].sudo().search([
            ('code', '=', ARIZA_DEPO_KODU), ('company_id', '=', konum.company_id.id)], limit=1)
        return bool(depo and konum.usage == 'internal'
                    and (konum.parent_path or '').startswith(depo.view_location_id.parent_path))

    @api.model
    def _serbest_miktar(self, urun, konum):
        """Konumdaki rezerve olmayan, lot/paket/sahip içermeyen adet."""
        quantlar = self.env['stock.quant'].sudo().search([
            ('product_id', '=', urun.id), ('location_id', '=', konum.id),
            ('lot_id', '=', False), ('package_id', '=', False), ('owner_id', '=', False),
        ])
        return sum(quantlar.mapped('quantity')) - sum(quantlar.mapped('reserved_quantity'))

    @api.model
    def _quant_kilitle(self, urun, konum):
        """Aynı ürün + konumda eşzamanlı dönüşümü sıraya sokar (negatif stok ve
        aynı koddan iki kart açılmasını önler)."""
        self.env.cr.execute(
            'SELECT id FROM stock_quant WHERE product_id = %s AND location_id = %s FOR UPDATE',
            (urun.id, konum.id))

    @api.model
    def _kontrol(self, urun, konum, miktar):
        company = konum.company_id
        if urun.tracking != 'none':
            raise UserError(_('Seri/lot numaralı ürünler henüz B Stok\'a çevrilemiyor.'))
        if len(urun.product_tmpl_id.product_variant_ids) > 1:
            raise UserError(_('Varyantlı ürünler henüz B Stok\'a çevrilemiyor.'))
        if urun.b_kaynak_urun_id:
            raise UserError(_('Bu ürün zaten bir B Stok kartı.'))
        if urun.with_company(company).cost_method != 'average':
            raise UserError(_('Yalnız ortalama maliyetli ürünler B Stok\'a çevrilebilir '
                              '(ürün kategorisini kontrol edin).'))
        if not self._ariza_konumu_mu(konum):
            raise UserError(_('B Stok dönüşümü yalnızca ARIZA deposu konumlarında yapılabilir.'))
        yuvarlama = urun.uom_id.rounding
        if float_compare(miktar, 0, precision_rounding=yuvarlama) <= 0:
            raise UserError(_('Adet sıfırdan büyük olmalı.'))
        serbest = self._serbest_miktar(urun, konum)
        if float_compare(miktar, serbest, precision_rounding=yuvarlama) > 0:
            raise UserError(_('%(konum)s konumunda serbest %(serbest)s adet var, '
                              '%(miktar)s adet çevrilemez.') % {
                'konum': konum.complete_name, 'serbest': serbest, 'miktar': miktar})

    def _envanter_hareketi(self, urun, miktar, kaynak, hedef, birim_fiyat=None):
        """Envanter Düzenlemesi türünde tek hareket oluşturup bitirir.

        Hareket değerleri, elle yapılan envanter düzeltmesinin kullandığı
        stock.quant._get_inventory_move_values ile üretilir; böylece özel
        modüllerin eklediği alanlar (ör. "Inventory In/Out" operasyon türü ve
        ona bağlı muhasebe hesabı) elle düzeltmedekiyle aynı olur.
        (Staging 2026-11-27: operasyon türü olmayan hareket çıkışı 621'e yazdı,
        elle düzeltme 159'a.)"""
        self.ensure_one()
        cikis_mi = kaynak.usage == 'internal'
        quant = self.env['stock.quant'].new({
            'product_id': urun.id,
            'location_id': (kaynak if cikis_mi else hedef).id,
            'company_id': self.company_id.id,
        })
        degerler = quant._get_inventory_move_values(miktar, kaynak, hedef, out=cikis_mi)
        if not degerler.get('picking_type_id'):
            tur = self._envanter_operasyon_turu(cikis_mi)
            if tur:
                degerler['picking_type_id'] = tur.id
        degerler.update({
            'name': _('B-STOK dönüşümü · %s') % self.name,
            'origin': self.name,
        })
        if birim_fiyat is not None:
            degerler['price_unit'] = birim_fiyat
        hareket = self.env['stock.move'].with_context(inventory_mode=False).create(degerler)
        hareket._action_done()
        if hareket.state != 'done':
            raise UserError(_('Stok hareketi tamamlanamadı (%s).') % urun.display_name)
        self.sudo().write({'move_ids': [(4, hareket.id)]})
        return hareket

    def _envanter_operasyon_turu(self, cikis_mi):
        """Elle envanter düzeltmelerinin taşıdığı operasyon türü (ör. "Inventory
        Out" / "Inventory In"); muhasebe hesabı kategori + bu türe göre seçiliyor
        (stock_accounting_valuation_advanced). Şirketin son elle düzeltmesinden
        okunur; bulunamazsa tür boş kalır."""
        self.ensure_one()
        alan = 'location_dest_id.usage' if cikis_mi else 'location_id.usage'
        son = self.env['stock.move'].sudo().search([
            ('is_inventory', '=', True),
            ('state', '=', 'done'),
            ('company_id', '=', self.company_id.id),
            ('picking_type_id', '!=', False),
            (alan, '=', 'inventory'),
            ('origin', 'not like', 'BSD/'),
        ], order='id desc', limit=1)
        return son.picking_type_id

    def _aktar(self, cikan, giren, miktar):
        """cikan ürünü konumdan çıkarır, giren ürünü aynı değerle konuma sokar.
        Değeri sıfır olan aktarım yapılmaz (giriş ürünün kendi maliyetine düşer,
        karşılıksız değer oluşur). Döner: birim maliyet."""
        self.ensure_one()
        envanter = self.envanter_konum_id
        cikis = self._envanter_hareketi(cikan, miktar, self.konum_id, envanter)
        deger = abs(sum(cikis.sudo().stock_valuation_layer_ids.mapped('value')))
        if float_is_zero(deger, precision_digits=2):
            raise UserError(_('%s ürününün maliyeti sıfır; değer kaybı olmaması için '
                              'dönüşüm yapılmadı.') % cikan.display_name)
        birim = deger / miktar
        self._envanter_hareketi(giren, miktar, envanter, self.konum_id, birim_fiyat=birim)
        return birim

    # ---------------------------------------------------------------- ana işlemler
    @api.model
    def donustur(self, urun, konum, miktar, oran, durum=False, not_metni=False):
        """Tamirli ürünü B Stok kartına çevirir; dönüşüm kaydını döner.
        Yalnız sihirbazdan (kayıt nesneleriyle) çağrılır."""
        self._yonetici_mi()
        company = konum.company_id
        if company != self.env.company:
            raise UserError(_('Bu konum %s şirketine ait; üstten o şirketi seçip '
                              'tekrar deneyin.') % company.name)
        self._quant_kilitle(urun, konum)
        self._kontrol(urun, konum, miktar)
        envanter = urun.with_company(company).property_stock_inventory
        if not envanter:
            raise UserError(_('Envanter Düzenlemesi konumu tanımlı değil.'))
        Kart = self.env['ariza.b.stok.kart']
        b_urun, yeni = Kart._kart_bul_veya_ac(urun, oran, company)
        if b_urun.with_company(company).cost_method != 'average':
            raise UserError(_('%s kartı ortalama maliyetli değil.') % b_urun.default_code)
        kayit = self.sudo().create({
            'name': self.env['ir.sequence'].sudo().with_company(company).next_by_code(
                'ariza.b.stok.donusum') or '/',
            'company_id': company.id,
            'urun_id': urun.id,
            'b_urun_id': b_urun.id,
            'b_kart_yeni': yeni,
            'konum_id': konum.id,
            'envanter_konum_id': envanter.id,
            'miktar': miktar,
            'oran': oran,
            'durum': durum,
            'not_metni': not_metni,
        }).with_env(self.env)
        birim = kayit._aktar(urun, b_urun, miktar)
        _programlar, uyari = Kart._promosyona_bagla(b_urun, oran, company)
        kayit.sudo().write({'birim_maliyet': birim, 'uyari': uyari or False})
        _logger.info('B Stok dönüşümü %s: %s x%s -> %s (%%%s) @ %s',
                     kayit.name, urun.id, miktar, b_urun.default_code, oran_metni(oran),
                     konum.complete_name)
        return kayit

    def action_geri_al(self):
        """B karttan ana ürüne ters aktarım (aynı konumda). Kart promosyonda kalır
        (başka stoğu olabilir)."""
        self._yonetici_mi()
        for kayit in self:
            # Aynı kaydın eşzamanlı iki kez geri alınmasını önler
            self.env.cr.execute(
                'SELECT id FROM ariza_b_stok_donusum WHERE id = %s FOR UPDATE NOWAIT',
                (kayit.id,))
            kayit.invalidate_cache()
            if kayit.state != 'tamam':
                raise UserError(_('%s zaten geri alınmış.') % kayit.name)
            if (not self._ariza_konumu_mu(kayit.konum_id)
                    or kayit.b_urun_id.b_kaynak_urun_id != kayit.urun_id):
                raise UserError(_('%s kaydı tutarsız; geri alınamaz.') % kayit.name)
            self._quant_kilitle(kayit.b_urun_id, kayit.konum_id)
            serbest = self._serbest_miktar(kayit.b_urun_id, kayit.konum_id)
            if float_compare(kayit.miktar, serbest,
                             precision_rounding=kayit.b_urun_id.uom_id.rounding) > 0:
                raise UserError(_('%(no)s geri alınamaz: B kartın %(konum)s konumunda '
                                  'serbest %(serbest)s adedi var.') % {
                    'no': kayit.name, 'konum': kayit.konum_id.complete_name, 'serbest': serbest})
            kayit._aktar(kayit.b_urun_id, kayit.urun_id, kayit.miktar)
            kayit.sudo().write({'state': 'geri_alindi'})
            _logger.info('B Stok dönüşümü geri alındı: %s', kayit.name)
        return True

    def action_hareketleri_ac(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stok Hareketleri'),
            'res_model': 'stock.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.move_ids.ids)],
        }
