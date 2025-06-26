from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    magaza_id = fields.Many2one('account.analytic.account', string='Mağaza') 