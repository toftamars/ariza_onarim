# -*- coding: utf-8 -*-
"""Eski B kartlarını ana ürüne bağlama sihirbazı (yalnız yönetici).

Elle açılmış "KOD (B-STOK)" kartlarına yönetici oran verir ve ana ürünü onaylar.
Modül kartı ana ürüne + orana bağlar, fiyatını eşitler ve kartı o oranın B-STOK
promosyonuna taşır. Sonraki dönüşümlerde aynı ürün + oran gelirse bu kart kullanılır.
Kart kodu ve stoğu değişmez.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.b_stok_urun import oran_metni


class ArizaBStokBaglaWizard(models.TransientModel):
    _name = 'ariza.b.stok.bagla.wizard'
    _description = 'Eski B Kartlarını Ana Ürüne Bağla'

    satir_ids = fields.One2many('ariza.b.stok.bagla.satir', 'wizard_id', string='Kartlar')

    @api.model
    def olustur(self, kartlar):
        """Seçili kartlar için önerilerle dolu sihirbaz: ana ürün koddan, oran
        kartın bugün bulunduğu tek B-STOK listesinden tahmin edilir."""
        Kart = self.env['ariza.b.stok.kart']
        secenekler = {deger for deger, _etiket in Kart._oran_secenekleri(self.env.company)}
        programlar = Kart._b_promosyonlari(self.env.company)
        kartlar = kartlar.filtered(lambda k: not k.b_kaynak_urun_id)
        if not kartlar:
            raise UserError(_('Seçili kartların hepsi zaten bir ana ürüne bağlı.'))
        satirlar = []
        for kart in kartlar:
            ana = Kart._ana_urun_tahmini(kart)
            oran = False
            listeler = programlar.filtered(lambda p: kart in p.discount_specific_product_ids)
            yuzdeler = set(listeler.mapped('discount_percentage'))
            if len(yuzdeler) == 1:
                oran = oran_metni(yuzdeler.pop())
            satirlar.append((0, 0, {
                'kart_id': kart.id,
                'ana_urun_id': ana.id,
                'oran': oran if oran in secenekler else False,
            }))
        return self.create({'satir_ids': satirlar})

    def action_bagla(self):
        self.ensure_one()
        self.env['ariza.b.stok.donusum']._yonetici_mi()
        Kart = self.env['ariza.b.stok.kart']
        company = self.env.company
        if not self.satir_ids:
            raise UserError(_('Bağlanacak kart yok.'))
        # Önce hepsini denetle: biri bile sorunluysa hiçbiri bağlanmaz
        sorunlar = []
        gorulen = {}
        for satir in self.satir_ids:
            oran = float(satir.oran) if satir.oran else 0.0
            etiket = satir.kart_id.default_code or satir.kart_id.display_name
            sorun = Kart._baglama_sorunu(satir.kart_id, satir.ana_urun_id, oran, company)
            anahtar = (satir.ana_urun_id.id, oran)
            if not sorun and anahtar in gorulen:
                sorun = _('aynı ana ürün ve oran %s satırında da seçili') % gorulen[anahtar]
            gorulen.setdefault(anahtar, etiket)
            if sorun:
                sorunlar.append('• %s: %s' % (etiket, sorun))
        if sorunlar:
            raise UserError(_('Hiçbir kart bağlanmadı, şu satırları düzeltin:\n%s')
                            % '\n'.join(sorunlar))
        uyarilar = set()
        for satir in self.satir_ids:
            uyari = Kart._eski_karti_bagla(
                satir.kart_id, satir.ana_urun_id, float(satir.oran), company)
            if uyari:
                uyarilar.add(uyari)
        mesaj = _('%s kart ana ürüne bağlandı ve oranının promosyonuna taşındı.') % len(self.satir_ids)
        if uyarilar:
            mesaj += ' ' + ' '.join(sorted(uyarilar))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('B Stok kartları'),
                'message': mesaj,
                'type': 'warning' if uyarilar else 'success',
                'sticky': bool(uyarilar),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class ArizaBStokBaglaSatir(models.TransientModel):
    _name = 'ariza.b.stok.bagla.satir'
    _description = 'Eski B Kartı Bağlama Satırı'

    wizard_id = fields.Many2one('ariza.b.stok.bagla.wizard', required=True, ondelete='cascade')
    kart_id = fields.Many2one('product.product', string='B Kartı', required=True, readonly=True)
    kart_adi = fields.Char(related='kart_id.name', string='Kart Adı')
    mevcut_oranlar = fields.Char(related='kart_id.b_mevcut_oranlar', string='Bugünkü Liste')
    stok = fields.Float(related='kart_id.b_stok_adedi', string='Stok')
    ana_urun_id = fields.Many2one(
        'product.product', string='Ana Ürün',
        domain="[('b_kaynak_urun_id', '=', False), ('id', '!=', kart_id), "
               "('default_code', 'not ilike', 'BSTOK'), ('default_code', 'not ilike', 'B-STOK'), "
               "('name', 'not ilike', 'B-STOK')]")
    ana_urun_adi = fields.Char(related='ana_urun_id.name', string='Ana Ürün Adı')
    oran = fields.Selection(selection='_oran_secenekleri', string='Oran')

    @api.model
    def _oran_secenekleri(self):
        return self.env['ariza.b.stok.kart']._oran_secenekleri(self.env.company)
