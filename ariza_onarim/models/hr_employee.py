# -*- coding: utf-8 -*-
"""
HR Employee Extension - Store Assignment

Extends hr.employee model to add store/branch assignment functionality
for employee-store relationship management.

Best Practices Applied:
- Proper field constraints
- Validation decorators
- Domain restrictions
- Comprehensive docstrings

Author: Arıza Onarım Module - Refactored
License: LGPL-3
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    """
    Employee Extension for Store Assignment

    Adds store/branch assignment to employees for repair module
    access control and workflow routing.
    """
    _inherit = 'hr.employee'

    magaza_id = fields.Many2one(
        'account.analytic.account',
        string='Mağaza',
        domain="[('warehouse_id', '!=', False)]",
        index=True,
        help='Çalışanın atandığı mağaza/şube. '
             'Arıza kayıtlarında varsayılan mağaza olarak kullanılır.'
    )

    @api.constrains('magaza_id')
    def _check_magaza_has_warehouse(self):
        """
        Validate that assigned store has warehouse configuration.

        Ensures data consistency by requiring warehouse for store assignment.
        """
        for employee in self:
            if employee.magaza_id and not employee.magaza_id.warehouse_id:
                raise ValidationError(
                    _("Seçilen mağaza için warehouse tanımlı değil.\n"
                      "Çalışan: %s\n"
                      "Mağaza: %s\n\n"
                      "Lütfen önce mağaza için warehouse tanımı yapın.") %
                    (employee.name, employee.magaza_id.name)
                )

    @api.model
    def get_employees_by_store(self, store_id):
        """
        Get all employees assigned to specific store.

        Args:
            store_id (int): Store analytic account ID

        Returns:
            recordset: Employee records

        Example:
            employees = env['hr.employee'].get_employees_by_store(store.id)
        """
        if not store_id:
            return self.browse([])

        employees = self.search([
            ('magaza_id', '=', store_id),
            ('active', '=', True)
        ], order='name')

        _logger.debug(f"Found {len(employees)} employees for store ID {store_id}")
        return employees

    @api.model
    def get_employee_store(self, user_id=None):
        """
        Get store assigned to employee (by user).

        Args:
            user_id (int, optional): User ID. If not provided, uses current user.

        Returns:
            account.analytic.account: Store record or False

        Example:
            store = env['hr.employee'].get_employee_store()
            if store:
                print(f"Current user's store: {store.name}")
        """
        if user_id is None:
            user_id = self.env.user.id

        employee = self.search([
            ('user_id', '=', user_id),
            ('active', '=', True)
        ], limit=1)

        if employee and employee.magaza_id:
            _logger.debug(
                f"Store found for user {user_id}: {employee.magaza_id.name}"
            )
            return employee.magaza_id

        _logger.debug(f"No store assignment found for user {user_id}")
        return False

    def name_get(self):
        """
        Override name_get to show store name for employees.

        Returns employee name with store in format: "Name (Store)"
        """
        result = []
        for employee in self:
            if employee.magaza_id:
                name = f"{employee.name} ({employee.magaza_id.name})"
            else:
                name = employee.name
            result.append((employee.id, name))
        return result
