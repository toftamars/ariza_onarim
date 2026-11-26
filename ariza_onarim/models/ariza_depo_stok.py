# -*- coding: utf-8 -*-
"""
Arıza deposu stoğu ve ürün notları.

Arıza yöneticileri ARIZA deposunun stok konumundaki (ARIZA/Stok) ürünleri
ürün başına tek satır görür ve her ürüne not yazar (örn. "sapı kırık,
onarıldı, %15 indirimle satılabilir"). Adetler stoktan okunur; bu ekran
stok değiştirmez. Notlar ayrı tabloda tutulur, ürün stoktan çıksa da kalır.
"""

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError

# Arıza deposunun kodu (stock.warehouse.code)
ARIZA_DEPO_KODU = 'ARIZA'
# Görünüm satır kimliği: şirket * ÇARPAN + ürün (ürün id'si bunun altında kalır)
ID_CARPANI = 100000000


class ArizaStokNotu(models.Model):
    _name = 'ariza.stok.notu'
    _description = 'Arıza Deposu Ürün Notu'
    _rec_name = 'product_id'

    product_id = fields.Many2one('product.product', string='Ürün', required=True,
                                 index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Şirket', required=True,
                                 default=lambda self: self.env.company)
    not_metni = fields.Text(string='Not')

    _sql_constraints = [
        ('urun_sirket_benzersiz', 'unique(product_id, company_id)',
         'Bir ürün için tek not tutulur.'),
    ]

    @api.model
    def kaydet(self, product, company, metin):
        """Ürünün notunu yazar (yoksa oluşturur). sudo kullanıcıyı değiştirmez;
        "Notu Yazan" gerçek kullanıcı olur."""
        metin = (metin or '').strip() or False
        kayit = self.sudo().search([
            ('product_id', '=', product.id),
            ('company_id', '=', company.id),
        ], limit=1)
        if kayit:
            kayit.write({'not_metni': metin})
        elif metin:
            self.sudo().create({
                'product_id': product.id,
                'company_id': company.id,
                'not_metni': metin,
            })


class ArizaDepoStok(models.Model):
    _name = 'ariza.depo.stok'
    _description = 'Arıza Deposu Stoğu'
    _auto = False
    _order = 'product_id'

    product_id = fields.Many2one('product.product', string='Ürün', readonly=True)
    company_id = fields.Many2one('res.company', string='Şirket', readonly=True)
    miktar = fields.Float(string='Adet', readonly=True, digits='Product Unit of Measure')
    not_metni = fields.Text(string='Not')
    not_yazan_id = fields.Many2one('res.users', string='Notu Yazan', readonly=True)
    not_tarihi = fields.Datetime(string='Not Tarihi', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    s.company_id * {ID_CARPANI} + s.product_id AS id,
                    s.product_id,
                    s.company_id,
                    s.miktar,
                    n.not_metni,
                    n.write_uid AS not_yazan_id,
                    n.write_date AS not_tarihi
                FROM (
                    SELECT q.product_id, w.company_id, SUM(q.quantity) AS miktar
                    FROM stock_quant q
                    JOIN stock_warehouse w
                      ON w.lot_stock_id = q.location_id AND w.code = %s
                    GROUP BY q.product_id, w.company_id
                    HAVING SUM(q.quantity) > 0
                ) s
                LEFT JOIN ariza_stok_notu n
                  ON n.product_id = s.product_id AND n.company_id = s.company_id
            )
        """, (ARIZA_DEPO_KODU,))

    def write(self, vals):
        """Bu ekranda yalnız not düzenlenir; not ayrı tabloya yazılır."""
        vals = dict(vals)
        if 'not_metni' not in vals or set(vals) - {'not_metni'}:
            raise UserError(_('Bu ekranda yalnızca not düzenlenebilir.'))
        self.check_access_rights('write')
        self.check_access_rule('write')
        Notlar = self.env['ariza.stok.notu']
        for satir in self:
            Notlar.kaydet(satir.product_id, satir.company_id, vals['not_metni'])
        self.invalidate_cache()
        return True
