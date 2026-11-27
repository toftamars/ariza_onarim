# -*- coding: utf-8 -*-
"""B Stok satış raporu (salt okunur SQL görünümü).

Kasa (POS) ve satış siparişi satırlarından B Stok kartlarının satışlarını tek
listede toplar. B kart: ana ürüne bağlı kart ya da kodu/adı "B-STOK"/"BSTOK"
içeren eski kart. Tutarlar satır tutarıdır; kasadaki promosyon indirimi ayrı
bir satır olduğundan "İndirim" kartın oranı üzerinden hesaplanır.

Kasa: ödenmiş/kapanmış/faturalı siparişler (iadeler eksi adetle).
Satış siparişi: onaylı/kilitli siparişler (sipariş adedi).
"""

from odoo import fields, models, tools

KANAL_SECENEKLERI = [('kasa', 'Mağaza Kasası'), ('siparis', 'Satış Siparişi')]


class ArizaBStokSatis(models.Model):
    _name = 'ariza.b.stok.satis'
    _description = 'B Stok Satış Raporu'
    _auto = False
    _order = 'tarih desc, id desc'
    _rec_name = 'belge'

    tarih = fields.Datetime(string='Tarih', readonly=True)
    kanal = fields.Selection(KANAL_SECENEKLERI, string='Kanal', readonly=True)
    belge = fields.Char(string='Belge', readonly=True)
    magaza = fields.Char(string='Kasa / Satış Ekibi', readonly=True)
    musteri_id = fields.Many2one('res.partner', string='Müşteri', readonly=True)
    satici_id = fields.Many2one('res.users', string='Satan', readonly=True)
    b_urun_id = fields.Many2one('product.product', string='B Stok Kartı', readonly=True)
    ana_urun_id = fields.Many2one('product.product', string='Ana Ürün', readonly=True)
    marka_id = fields.Many2one('product.brand', string='Marka', readonly=True)
    categ_id = fields.Many2one('product.category', string='Kategori', readonly=True)
    oran = fields.Float(string='Oran (%)', readonly=True, group_operator='avg')
    miktar = fields.Float(string='Adet', readonly=True)
    tutar = fields.Float(string='Tutar (KDV Dahil)', readonly=True)
    tutar_haric = fields.Float(string='Tutar (KDV Hariç)', readonly=True)
    indirim = fields.Float(string='İndirim (Oran Üzerinden)', readonly=True,
                           help='Satır tutarı × kart oranı / 100. Oranı olmayan '
                                '(ana ürüne bağlanmamış) kartlarda 0.')
    company_id = fields.Many2one('res.company', string='Şirket', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH b_kart AS (
                    SELECT p.id AS urun_id, p.b_kaynak_urun_id AS ana_urun_id,
                           COALESCE(p.b_indirim_orani, 0) AS oran,
                           t.product_brand_id AS marka_id, t.categ_id
                    FROM product_product p
                    JOIN product_template t ON t.id = p.product_tmpl_id
                    WHERE p.b_kaynak_urun_id IS NOT NULL
                       OR p.default_code ILIKE '%%B-STOK%%' OR p.default_code ILIKE '%%BSTOK%%'
                       OR t.name ILIKE '%%B-STOK%%' OR t.name ILIKE '%%BSTOK%%'
                )
                SELECT l.id * 2 AS id, o.date_order AS tarih, 'kasa' AS kanal,
                       o.name AS belge, c.name AS magaza,
                       o.partner_id AS musteri_id, o.user_id AS satici_id,
                       b.urun_id AS b_urun_id, b.ana_urun_id, b.marka_id, b.categ_id,
                       b.oran, l.qty AS miktar,
                       l.price_subtotal_incl AS tutar, l.price_subtotal AS tutar_haric,
                       l.price_subtotal_incl * b.oran / 100.0 AS indirim,
                       o.company_id
                FROM pos_order_line l
                JOIN pos_order o ON o.id = l.order_id
                     AND o.state IN ('paid', 'done', 'invoiced')
                JOIN b_kart b ON b.urun_id = l.product_id
                LEFT JOIN pos_session s ON s.id = o.session_id
                LEFT JOIN pos_config c ON c.id = s.config_id
                UNION ALL
                SELECT l.id * 2 + 1 AS id, o.date_order AS tarih, 'siparis' AS kanal,
                       o.name AS belge, tm.name AS magaza,
                       o.partner_id AS musteri_id, o.user_id AS satici_id,
                       b.urun_id AS b_urun_id, b.ana_urun_id, b.marka_id, b.categ_id,
                       b.oran, l.product_uom_qty AS miktar,
                       l.price_total AS tutar, l.price_subtotal AS tutar_haric,
                       l.price_total * b.oran / 100.0 AS indirim,
                       o.company_id
                FROM sale_order_line l
                JOIN sale_order o ON o.id = l.order_id AND o.state IN ('sale', 'done')
                JOIN b_kart b ON b.urun_id = l.product_id
                LEFT JOIN crm_team tm ON tm.id = o.team_id
                WHERE l.display_type IS NULL
            )
        """ % self._table)
