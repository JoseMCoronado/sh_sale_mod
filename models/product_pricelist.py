# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    partner_id = fields.Many2one('res.partner',string="Customer")
    notes = fields.Text(string="Message for Customers")
