# -*- coding: utf-8 -*-
"""
Transit (yolda) akışı yardımcıları.

Mağaza ürünü teknik servise giderken tek transfer yerine iki adım kullanılır:
  1) Çıkış: mağaza konumu → "X/// Mağaza > Servis Transferi" (transit)
  2) Varış: transit → servis stoğu (MAT rotasının itme kuralı otomatik oluşturur)

Transit konumu isimden değil, rotanın stok kurallarından bulunur (isimler düzensiz:
örn. "VNTG > DTL Transferi"). Özellik sistem parametresiyle açılıp kapanır.
"""

import logging

from ..ariza_constants import ArizaTipi, TeknikServis
from .chatter_helper import ChatterHelper as Chatter

_logger = logging.getLogger(__name__)

PARAM_AKTIF = 'ariza_onarim.yolda_akisi_aktif'
PARAM_ROUTE_ID = 'ariza_onarim.yolda_route_id'
VARSAYILAN_ROTA_ADI = 'Mağazalar Arası Transfer'

# Yolda akışının uygulandığı teknik servisler (kendi deposu olan iç servisler)
KAPSAMDAKI_SERVISLER = TeknikServis.DTL_SERVISLER + [
    TeknikServis.ZUHAL_ARIZA_DEPO,
    TeknikServis.ZUHAL_NEFESLI,
]


class TransitHelper:
    """Yolda akışı için rota / transit konum çözümleme"""

    @staticmethod
    def is_aktif(env):
        deger = env['ir.config_parameter'].sudo().get_param(PARAM_AKTIF, 'False')
        return str(deger).strip().lower() in ('1', 'true', 'evet', 'yes')

    @staticmethod
    def get_route(env, company=None):
        """Yolda akışında kullanılacak rotayı döner (parametre, yoksa isimle).

        İsimle aramada yalnız kaydın şirketine ait (ya da şirketsiz) rotalar
        alınır: diğer şirketlerde benzer adlı rotalar var (ör. "C-Mağazalar
        Arası Transfer (MAT)" Çağdaş'a ait) ve sudo hepsini görür.
        """
        Route = env['stock.location.route'].sudo()
        company = company or env.company
        route_id = env['ir.config_parameter'].sudo().get_param(PARAM_ROUTE_ID)
        if route_id:
            try:
                route = Route.browse(int(route_id)).exists()
            except (TypeError, ValueError):
                route = Route.browse()
            if route:
                return route
            _logger.warning("[YOLDA] %s parametresindeki rota bulunamadı: %s", PARAM_ROUTE_ID, route_id)
        routes = Route.search([
            ('name', 'ilike', VARSAYILAN_ROTA_ADI),
            ('company_id', 'in', [company.id, False]),
        ])
        if len(routes) > 1:
            _logger.warning(
                "[YOLDA] '%s' adıyla %s rota bulundu; ilki kullanılıyor. "
                "%s parametresiyle rota kimliğini belirtin.",
                VARSAYILAN_ROTA_ADI, len(routes), PARAM_ROUTE_ID,
            )
        return routes[:1]

    @staticmethod
    def kapsamda_mi(ariza):
        """Kayıt yolda akışına uygun mu (tip + servis)?"""
        return (
            ariza.ariza_tipi == ArizaTipi.MAGAZA
            and ariza.teknik_servis in KAPSAMDAKI_SERVISLER
        )

    @staticmethod
    def find_transit(env, route, kaynak_konum, hedef_konum):
        """
        Kaynak depodan hedefe giden transit konumu ve itme kuralının nihai
        hedefini döner: (transit_konum, nihai_hedef) veya (False, False).

        Önce nihai hedefi birebir hedef_konum olan kural, yoksa hedef ile aynı
        depoya giden kural tercih edilir. Çekme kuralının kaynağı kaynak depo
        olmalıdır (çekme kuralının kaynak konumu ise önemsizdir; çıkışı modül açar).
        """
        if not route or not kaynak_konum or not hedef_konum:
            return False, False
        kaynak_wh = kaynak_konum.warehouse_id
        hedef_wh = hedef_konum.warehouse_id
        if not kaynak_wh or not hedef_wh:
            return False, False

        Rule = env['stock.rule'].sudo()
        push_rules = Rule.search([
            ('route_id', '=', route.id),
            ('action', 'in', ('push', 'pull_push')),
            ('location_src_id.usage', '=', 'transit'),
        ])
        # Odoo itme kuralını hareketin deposuyla (= çıkışın operasyon tipi,
        # yani kaynak mağaza) ya da deposuz kurallar arasında arar; aynısını uygula.
        adaylar = push_rules.filtered(
            lambda r: r.location_id.warehouse_id == hedef_wh
            and (not r.warehouse_id or r.warehouse_id == kaynak_wh)
        )
        # Birebir hedef eşleşmesi öne
        adaylar = adaylar.sorted(lambda r: 0 if r.location_id == hedef_konum else 1)

        for push in adaylar:
            transit = push.location_src_id
            pulls = Rule.search([
                ('route_id', '=', route.id),
                ('action', 'in', ('pull', 'pull_push')),
                ('location_id', '=', transit.id),
            ])
            if pulls.filtered(lambda p: p.location_src_id.warehouse_id == kaynak_wh):
                return transit, push.location_id
        return False, False

    @staticmethod
    def tani(env, route, kaynak_konum, hedef_konum):
        """find_transit'in hangi adımda elendiğini anlatan kısa metin."""
        parcalar = [f"rota={route.display_name if route else 'YOK'}"]
        kaynak_wh = kaynak_konum.warehouse_id if kaynak_konum else False
        hedef_wh = hedef_konum.warehouse_id if hedef_konum else False
        parcalar.append(f"kaynak depo={kaynak_wh.name if kaynak_wh else 'YOK'}")
        parcalar.append(f"hedef depo={hedef_wh.name if hedef_wh else 'YOK'}")
        if route and kaynak_wh and hedef_wh:
            Rule = env['stock.rule'].sudo()
            push_rules = Rule.search([
                ('route_id', '=', route.id),
                ('action', 'in', ('push', 'pull_push')),
                ('location_src_id.usage', '=', 'transit'),
            ])
            hedefe = push_rules.filtered(lambda r: r.location_id.warehouse_id == hedef_wh)
            parcalar.append(f"itme kuralı={len(push_rules)}, hedef depoya={len(hedefe)}")
            pulls = Rule.search([
                ('route_id', '=', route.id),
                ('action', 'in', ('pull', 'pull_push')),
                ('location_id', 'in', hedefe.mapped('location_src_id').ids),
            ])
            kaynaktan = pulls.filtered(lambda p: p.location_src_id.warehouse_id == kaynak_wh)
            parcalar.append(f"çekme kuralı={len(pulls)}, kaynak depodan={len(kaynaktan)}")
        return ', '.join(parcalar)

    @staticmethod
    def hazirla(ariza, kaynak_konum, hedef_konum):
        """
        Kayıt için yolda akışı uygulanabiliyorsa (route, transit, nihai_hedef)
        döner; uygulanamıyorsa None. Uygulanamama sebebi chatter'a yazılır
        (yalnız özellik açık ve kayıt kapsamdaysa).
        """
        env = ariza.env
        if not TransitHelper.is_aktif(env) or not TransitHelper.kapsamda_mi(ariza):
            return None
        route = TransitHelper.get_route(env, ariza.company_id)
        transit, nihai = TransitHelper.find_transit(env, route, kaynak_konum, hedef_konum)
        if not route or not transit:
            tani = TransitHelper.tani(env, route, kaynak_konum, hedef_konum)
            _logger.warning("[YOLDA] %s kurulamadı: %s", ariza.name, tani)
            Chatter.uyari(ariza, "Yolda transfer kurulamadı (rota bulunamadı); tek adımlı transfer oluşturuldu.")
            return None
        return route, transit, nihai
