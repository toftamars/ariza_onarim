# -*- coding: utf-8 -*-
"""
Repair Record Completion Wizard (DEPRECATED)

NOTE: This wizard is deprecated and no longer used in the current workflow.
Kept for backward compatibility with older records.

Use the main record completion workflow instead.

Author: Arıza Onarım Module - Refactored
License: LGPL-3
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

from ..models.ariza_constants import SMSTemplates

_logger = logging.getLogger(__name__)


class ArizaKayitTamamlaWizard(models.TransientModel):
    """
    Repair Record Completion Wizard (DEPRECATED)

    **IMPORTANT**: This wizard is deprecated. Use the main record
    completion workflow in ariza.kayit model instead.

    Historical functionality:
    - Creates return transfer (from technical service to store)
    - Sends completion SMS to customer
    - Redirects to transfer form

    Kept for compatibility with older installations.
    """
    _name = 'ariza.kayit.tamamla.wizard'
    _description = 'Arıza Kaydı Tamamlama Sihirbazı (ESKİ - KULLANILMIYOR)'

    ariza_id = fields.Many2one(
        'ariza.kayit',
        string='Arıza Kaydı',
        required=True,
        help='Repair record to complete'
    )
    onay_mesaji = fields.Text(
        string='Onay Mesajı',
        readonly=True,
        help='Confirmation message displayed to user'
    )

    def action_tamamla(self):
        """
        Complete repair record and create return transfer.

        **DEPRECATED**: Use ariza.kayit.action_teslim_al() instead.

        Workflow:
        1. Create return transfer (technical service → store)
        2. Send completion SMS to customer
        3. Redirect to transfer form

        Returns:
            dict: Window action to transfer form or close action

        Raises:
            UserError: If transfer creation fails
        """
        self.ensure_one()
        ariza = self.ariza_id

        _logger.warning(
            f"DEPRECATED: Using old completion wizard for repair {ariza.name}. "
            f"Please use the main workflow instead."
        )

        # Validate initial transfer exists
        if not ariza.transfer_id:
            raise UserError(
                _("İlk transfer bulunamadı. Bu wizard sadece daha önce "
                  "transfer oluşturulmuş kayıtlar için kullanılabilir.")
            )

        # Get transfer source/destination
        mevcut_kaynak = ariza.transfer_id.location_id
        mevcut_hedef = ariza.transfer_id.location_dest_id

        try:
            # Create return transfer (technical service → store)
            yeni_transfer = ariza._create_stock_transfer(
                kaynak_konum=mevcut_hedef,  # From: technical service
                hedef_konum=mevcut_kaynak,  # To: store
                transfer_tipi='ikinci'  # Mark as return transfer
            )

            if not yeni_transfer:
                raise UserError(
                    _("Transfer oluşturulamadı!\n\n"
                      "Kaynak: %s\n"
                      "Hedef: %s\n\n"
                      "Lütfen konum ayarlarını kontrol edin.") %
                    (mevcut_hedef.name, mevcut_kaynak.name)
                )

            # Update transfer counter
            ariza.write({
                'transfer_sayisi': ariza.transfer_sayisi + 1,
            })

            _logger.info(
                f"Return transfer created for {ariza.name}: {yeni_transfer.name}"
            )

            # Send completion SMS
            self._send_completion_sms(ariza)

            # Redirect to transfer form
            return {
                'type': 'ir.actions.act_window',
                'name': _('Transfer Belgesi'),
                'res_model': 'stock.picking',
                'res_id': yeni_transfer.id,
                'view_mode': 'form',
                'target': 'current',
            }

        except Exception as e:
            _logger.error(f"Error completing repair {ariza.name}: {str(e)}")
            raise UserError(
                _("Tamamlama işlemi başarısız oldu: %s") % str(e)
            )

    def _send_completion_sms(self, ariza):
        """
        Send completion SMS to customer.

        Args:
            ariza (ariza.kayit): Repair record

        Note:
            Only sends SMS for customer and store repair types.
            Email sending has been disabled in current version.
        """
        if not ariza.partner_id:
            _logger.debug(f"No partner for repair {ariza.name}, skipping SMS")
            return

        has_phone = (ariza.partner_id.mobile or ariza.partner_id.phone) or (
            ariza.sms_farkli_noya_gonder and ariza.sms_farkli_telefon and ariza.sms_farkli_telefon.strip()
        )
        if not has_phone:
            _logger.warning(
                f"No phone number for partner {ariza.partner_id.name}, "
                f"cannot send SMS for repair {ariza.name}"
            )
            return

        # Only send SMS for customer/store types
        if ariza.ariza_tipi not in ('musteri', 'magaza'):
            _logger.debug(
                f"Repair type {ariza.ariza_tipi} does not require SMS"
            )
            return

        try:
            if ariza.ariza_tipi == 'musteri':
                # Customer repair completion SMS
                sms_mesaji = SMSTemplates.IKINCI_SMS.format(
                    musteri_adi=ariza.partner_id.name or '',
                    urun=ariza.urun or '',
                    magaza_adi='',  # Store name not available in this wizard
                    kayit_no=ariza.name or ''
                )

                # Add warranty note if applicable
                if ariza.garanti_kapsaminda_mi == 'evet':
                    sms_mesaji += SMSTemplates.GARANTI_EKLENTISI
            else:
                # Store product completion SMS
                sms_mesaji = (
                    f"Sayın {ariza.partner_id.name}, "
                    f"{ariza.urun} ürününüz teslim edilmiştir. "
                    f"Kayıt No: {ariza.name} B021"
                )

            # Send SMS using helper
            ariza._send_sms_to_customer(sms_mesaji)
            _logger.info(f"Completion SMS sent for repair {ariza.name}")

        except Exception as e:
            _logger.error(f"Error sending completion SMS for {ariza.name}: {str(e)}")
            # Don't raise - SMS failure shouldn't block completion
