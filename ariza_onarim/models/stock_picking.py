# -*- coding: utf-8 -*-
"""
Stock Picking Model - Stock Transfer Customizations

This module extends stock.picking model to provide:
- Automatic e-Dispatch (Matbu) marking for repair module transfers
- Transfer validation workflow integration
- View customizations for repair-related transfers
- UBL (e-Invoice) vehicle information support

Author: Arıza Onarım Module
License: LGPL-3
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    """
    Stock Transfer Model Extension for Repair Module

    Extends stock.picking to automatically handle e-Dispatch settings,
    transfer validation workflow, and repair record integration.
    """
    _inherit = 'stock.picking'

    def _is_repair_transfer(self, origin=None):
        """
        Check if this transfer is related to repair module.

        Args:
            origin (str, optional): Transfer origin reference.
                                   If not provided, uses self.origin.

        Returns:
            bool: True if transfer is from repair module, False otherwise.
        """
        if origin is None:
            origin = self.origin or ''
        return self.env.context.get('from_ariza_onarim') or ('ARZ' in str(origin).upper())

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to set e-Dispatch type for repair transfers.

        Automatically sets edespatch_delivery_type to 'printed' (Matbu)
        for all transfers originating from repair module.

        Args:
            vals_list (list): List of dictionaries containing field values.

        Returns:
            recordset: Created stock.picking records.
        """
        for vals in vals_list:
            origin = str(vals.get('origin', ''))
            if self.env.context.get('from_ariza_onarim') or ('ARZ' in origin.upper()):
                vals['edespatch_delivery_type'] = 'printed'
                _logger.info(f"[REPAIR MODULE] e-Dispatch set to 'Printed' - Origin: {origin}")

        records = super().create(vals_list)

        # Post-creation validation and notification
        for record in records:
            if record._is_repair_transfer():
                if record.edespatch_delivery_type != 'printed':
                    _logger.warning(
                        f"[POST-CREATE] e-Dispatch type changed! "
                        f"Origin: {record.origin}, Current: {record.edespatch_delivery_type}. "
                        f"Correcting to 'printed'..."
                    )
                    record.write({'edespatch_delivery_type': 'printed'})
                    _logger.info(f"[POST-CREATE] Corrected to 'Printed': {record.name}")

                # Add message to chatter
                try:
                    record.message_post(
                        body="✅ Teslimat Türü: Matbu (Arıza Modülü - Otomatik)",
                        message_type='notification'
                    )
                except Exception as e:
                    _logger.debug(f"Could not post message to chatter: {e}")

        return records

    def write(self, vals):
        """
        Override write to protect e-Dispatch type for repair transfers.

        Prevents manual changes to edespatch_delivery_type for repair module
        transfers by resetting it to 'printed' after any write operation.

        Args:
            vals (dict): Dictionary containing field values to update.

        Returns:
            bool: Result of super().write()
        """
        result = super().write(vals)

        # Post-write validation for repair transfers
        for record in self:
            if record._is_repair_transfer():
                if record.edespatch_delivery_type != 'printed':
                    _logger.warning(
                        f"[POST-WRITE] e-Dispatch type was changed manually! "
                        f"Origin: {record.origin}, Current: {record.edespatch_delivery_type}. "
                        f"Reverting to 'printed'..."
                    )
                    super(StockPicking, record).write({'edespatch_delivery_type': 'printed'})
                    _logger.info(f"[POST-WRITE] Reverted to 'Printed': {record.name}")

        return result

    def button_validate(self):
        """
        Override transfer validation to integrate with repair workflow.

        When a transfer is validated:
        1. Executes standard validation logic
        2. If transfer is linked to a repair record:
           - Increments transfer_sayisi counter
           - Returns to repair form view (for single transfers)

        Returns:
            dict or bool: Action dictionary to return to repair form,
                         or standard result from super().
        """
        # Execute standard validation
        result = super().button_validate()

        # Process repair-related transfers
        for picking in self:
            if picking.origin and picking.state == 'done':
                # Search for related repair record
                ariza = self.env['ariza.kayit'].search([('name', '=', picking.origin)], limit=1)
                if ariza:
                    # Increment transfer counter
                    ariza.transfer_sayisi += 1
                    _logger.info(
                        f"[REPAIR TRANSFER] Transfer validated for {ariza.name}. "
                        f"Total transfers: {ariza.transfer_sayisi}"
                    )

                    # Return to repair form view for single transfers
                    if len(self) == 1:
                        return {
                            'type': 'ir.actions.act_window',
                            'res_model': 'ariza.kayit',
                            'res_id': ariza.id,
                            'view_mode': 'form',
                            'target': 'current',
                        }

        return result

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """
        Customize form view to hide note field and chatter when requested.

        Removes note field and chatter elements from the form view when
        'hide_note' is present in context. Useful for simplified popup views.

        Args:
            view_id (int, optional): View ID to render.
            view_type (str): Type of view (form, tree, etc.).
            toolbar (bool): Whether to include toolbar.
            submenu (bool): Whether to include submenu.

        Returns:
            dict: View definition with modifications.
        """
        res = super().fields_view_get(
            view_id=view_id,
            view_type=view_type,
            toolbar=toolbar,
            submenu=submenu
        )

        if view_type == 'form' and self.env.context.get('hide_note'):
            try:
                from lxml import etree
                arch = etree.fromstring(res.get('arch', ''))

                # Remove note field
                for node in arch.xpath("//field[@name='note']"):
                    parent = node.getparent()
                    if parent is not None:
                        parent.remove(node)

                # Remove chatter
                for node in arch.xpath("//*[contains(concat(' ', normalize-space(@class), ' '), ' oe_chatter ')]"):
                    parent = node.getparent()
                    if parent is not None:
                        parent.remove(node)

                res['arch'] = etree.tostring(arch, encoding='unicode')
            except Exception as e:
                _logger.warning(f"View processing error (stock.picking): {str(e)}")

        return res

    def _ubl_add_shipment_stage(self, shipment, ns, version='2.1'):
        """
        Add vehicle information to UBL shipment stage for e-Invoice.

        Extends standard UBL shipment stage generation to include vehicle
        information (plate number) when available.

        Args:
            shipment: UBL shipment XML element.
            ns (dict): XML namespace dictionary.
            version (str): UBL version (default: '2.1').
        """
        super()._ubl_add_shipment_stage(shipment, ns, version=version)

        # Add vehicle information if available
        if hasattr(self, 'vehicle_id') and self.vehicle_id:
            vehicle = shipment.find(ns['cac'] + 'TransportMeans')
            if vehicle is not None:
                vehicle_id_elem = vehicle.find(ns['cac'] + 'ID')
                if vehicle_id_elem is not None:
                    vehicle_id_elem.text = str(self.vehicle_id) if self.vehicle_id else '' 

 