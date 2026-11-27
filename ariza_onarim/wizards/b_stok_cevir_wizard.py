# -*- coding: utf-8 -*-
"""B Stok'a Çevir sihirbazı (yalnız yönetici).

İki giriş: Arıza Deposu Stoğu satırından (ürün ve konum sabit gelir) ya da
"B Stok'a Çevir" menüsünden (konum ve ürün seçilir; mağaza stokları dahil).
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.b_stok_donusum import DURUM_SECENEKLERI, YONETICI_GRUBU


class ArizaBStokCevirWizard(models.TransientModel):
    _name = 'ariza.b.stok.cevir.wizard'
    _description = "B Stok'a Çevir"

    sabit = fields.Boolean(string='Satırdan Açıldı', default=False,
                           help='Arıza Deposu Stoğu satırından açıldıysa ürün ve konum değiştirilemez.')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    konum_id = fields.Many2one(
        'stock.location', string='Konum', required=True,
        domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]")
    urun_id = fields.Many2one(
        'product.product', string='Ürün', required=True,
        domain="[('type', '=', 'product'), ('tracking', '=', 'none'), "
               "('b_kaynak_urun_id', '=', False), "
               "('stock_quant_ids.location_id', '=', konum_id)]")
    serbest_miktar = fields.Float(string='Çevrilebilir Adet', compute='_compute_bilgi',
                                  digits='Product Unit of Measure')
    miktar = fields.Float(string='Çevrilecek Adet', required=True, default=1.0,
                          digits='Product Unit of Measure')
    oran = fields.Selection(selection='_oran_secenekleri', string='İndirim Oranı', required=True)
    durum = fields.Selection(DURUM_SECENEKLERI, string='Durum')
    not_metni = fields.Text(string='Not')
    kart_kodu = fields.Char(string='B Stok Kartı', compute='_compute_bilgi')
    kart_durumu = fields.Char(string='Kart', compute='_compute_bilgi')

    @api.model
    def _oran_secenekleri(self):
        return self.env['ariza.b.stok.kart']._oran_secenekleri(self.env.company)

    @api.onchange('konum_id')
    def _onchange_konum_id(self):
        if not self.sabit:
            self.urun_id = False

    @api.depends('urun_id', 'konum_id', 'oran')
    def _compute_bilgi(self):
        yonetici = self.env.user.has_group(YONETICI_GRUBU)
        Donusum = self.env['ariza.b.stok.donusum']
        Kart = self.env['ariza.b.stok.kart']
        for sihirbaz in self:
            sihirbaz.serbest_miktar = 0.0
            sihirbaz.kart_kodu = False
            sihirbaz.kart_durumu = False
            if not yonetici or not sihirbaz.urun_id:
                continue
            if sihirbaz.konum_id:
                sihirbaz.serbest_miktar = Donusum._serbest_miktar(
                    sihirbaz.urun_id, sihirbaz.konum_id)
            if sihirbaz.oran and sihirbaz.urun_id.default_code:
                oran = float(sihirbaz.oran)
                try:
                    mevcut = Kart._mevcut_kart(sihirbaz.urun_id, oran)
                except UserError as hata:
                    sihirbaz.kart_durumu = str(hata.args[0]) if hata.args else _('Kart sorunlu')
                    continue
                sihirbaz.kart_kodu = (mevcut.default_code if mevcut
                                      else Kart._kart_kodu(sihirbaz.urun_id, oran))
                sihirbaz.kart_durumu = (_('Mevcut kart kullanılacak') if mevcut
                                        else _('Yeni kart açılacak'))

    def action_onayla(self):
        self.ensure_one()
        if not self.oran:
            raise UserError(_('İndirim oranı seçin.'))
        kayit = self.env['ariza.b.stok.donusum'].donustur(
            self.urun_id, self.konum_id, self.miktar, float(self.oran),
            durum=self.durum, not_metni=self.not_metni)
        return {
            'type': 'ir.actions.act_window',
            'name': _('B Stok Dönüşümü'),
            'res_model': 'ariza.b.stok.donusum',
            'res_id': kayit.id,
            'view_mode': 'form',
            'target': 'current',
        }
