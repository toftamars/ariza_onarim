# -*- coding: utf-8 -*-
"""
Transfer Builder - Stock transfer oluşturma helper sınıfı
"""

import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class TransferBuilder:
    """
    Stock transfer (stock.picking) oluşturma için Builder Pattern.

    Bu sınıf, _create_stock_transfer() metodundaki karmaşıklığı azaltır
    ve transfer oluşturma işlemini daha okunabilir hale getirir.
    """

    def __init__(self, env, ariza_record):
        """
        Args:
            env: Odoo environment
            ariza_record: ArizaKayit record
        """
        self.env = env
        self.ariza = ariza_record
        self.picking_vals = {}
        self.move_lines = []

    def set_picking_type(self, picking_type):
        """Picking type (operasyon tipi) ayarla"""
        if picking_type:
            self.picking_vals['picking_type_id'] = picking_type.id
            self.picking_vals['location_id'] = picking_type.default_location_src_id.id
            self.picking_vals['location_dest_id'] = picking_type.default_location_dest_id.id
        return self

    def set_locations(self, source_location, dest_location):
        """Kaynak ve hedef konumları ayarla"""
        if source_location:
            self.picking_vals['location_id'] = source_location.id
        if dest_location:
            self.picking_vals['location_dest_id'] = dest_location.id
        return self

    def set_partner(self, partner):
        """Partner (müşteri/tedarikçi) ayarla"""
        if partner:
            self.picking_vals['partner_id'] = partner.id
        return self

    def set_origin(self, origin):
        """Origin (kaynak belge) ayarla"""
        if origin:
            self.picking_vals['origin'] = origin
        return self

    def set_scheduled_date(self, date=None):
        """Planlanan tarih ayarla (varsayılan: bugün)"""
        self.picking_vals['scheduled_date'] = date or datetime.now()
        return self

    def set_company(self, company):
        """Şirket ayarla"""
        if company:
            self.picking_vals['company_id'] = company.id
        return self

    def set_carrier(self, carrier):
        """Kargo firması ayarla"""
        if carrier:
            self.picking_vals['carrier_id'] = carrier.id
        return self

    def add_move_line(self, product, quantity, source_location=None, dest_location=None, description=None):
        """
        Hareket satırı (stock.move) ekle

        Args:
            product: product.product recordset
            quantity: Miktar
            source_location: Kaynak konum (opsiyonel, picking'den alınır)
            dest_location: Hedef konum (opsiyonel, picking'den alınır)
            description: Açıklama
        """
        if not product:
            _logger.warning("add_move_line: Ürün belirtilmedi")
            return self

        move_vals = {
            'name': description or product.display_name,
            'product_id': product.id,
            'product_uom_qty': quantity,
            'product_uom': product.uom_id.id,
            'location_id': source_location.id if source_location else self.picking_vals.get('location_id'),
            'location_dest_id': dest_location.id if dest_location else self.picking_vals.get('location_dest_id'),
        }

        self.move_lines.append((0, 0, move_vals))
        return self

    def set_note(self, note):
        """Not ekle"""
        if note:
            self.picking_vals['note'] = note
        return self

    def enable_edespatch(self, edespatch_type=None):
        """E-İrsaliye aktif et"""
        self.picking_vals['edespatch_flag'] = True
        if edespatch_type:
            self.picking_vals['edespatch_type'] = edespatch_type
        return self

    def build(self):
        """
        Transfer'i oluştur ve kaydet

        Returns:
            stock.picking recordset veya False
        """
        if not self.picking_vals:
            _logger.error("TransferBuilder: picking_vals boş, transfer oluşturulamadı")
            return False

        # Move lines ekle
        if self.move_lines:
            self.picking_vals['move_ids_without_package'] = self.move_lines

        try:
            picking = self.env['stock.picking'].create(self.picking_vals)
            _logger.info(f"Transfer oluşturuldu: {picking.name} (ID: {picking.id})")
            return picking
        except Exception as e:
            _logger.error(f"Transfer oluşturma hatası: {str(e)}")
            return False

    def get_vals(self):
        """
        Vals dictionary'yi döndür (create() için)

        Returns:
            dict: picking_vals
        """
        vals = self.picking_vals.copy()
        if self.move_lines:
            vals['move_ids_without_package'] = self.move_lines
        return vals


class TransferHelper:
    """Transfer işlemleri için yardımcı fonksiyonlar"""

    @staticmethod
    def get_picking_type(env, warehouse, operation_name, company_id=None):
        """
        Picking type (operasyon tipi) bulur.

        Args:
            env: Odoo environment
            warehouse: stock.warehouse recordset
            operation_name (str): Operasyon adı (örn: "Tamir Teslimatları")
            company_id: Company ID (opsiyonel)

        Returns:
            stock.picking.type recordset veya False
        """
        domain = [
            ('name', '=', operation_name),
            ('warehouse_id', '=', warehouse.id)
        ]

        if company_id:
            domain.append(('company_id', '=', company_id))

        picking_type = env['stock.picking.type'].search(domain, limit=1)

        if picking_type:
            _logger.info(f"Picking type bulundu: {picking_type.name} (Warehouse: {warehouse.name})")
        else:
            _logger.warning(f"Picking type bulunamadı: {operation_name} (Warehouse: {warehouse.name})")

        return picking_type

    @staticmethod
    def validate_transfer(picking):
        """
        Transfer'i onayla (validate)

        Args:
            picking: stock.picking recordset

        Returns:
            bool: Başarılı ise True
        """
        if not picking:
            return False

        try:
            # İlk önce kontrol et
            if picking.state in ['done', 'cancel']:
                _logger.warning(f"Transfer zaten {picking.state} durumunda: {picking.name}")
                return False

            # Confirm et (eğer draft ise)
            if picking.state == 'draft':
                picking.action_confirm()

            # Assign et (eğer confirmed ise)
            if picking.state in ['confirmed', 'waiting']:
                picking.action_assign()

            # Validate et
            if picking.state == 'assigned':
                picking.button_validate()
                _logger.info(f"Transfer onaylandı: {picking.name}")
                return True
            else:
                _logger.warning(f"Transfer atanamadı (state: {picking.state}): {picking.name}")
                return False

        except Exception as e:
            _logger.error(f"Transfer onaylama hatası ({picking.name}): {str(e)}")
            return False
