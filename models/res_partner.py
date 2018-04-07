# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ResPartner(models.Model):
    _inherit = "res.partner"

    quotation_count = fields.Integer(string="Quotations")

    @api.multi
    def _get_quotation_count(self):
        for record in self:
            quotations = record.env['sale.quotation'].search([('partner_id','=',record.id)])
            record.quotation_count = len(repairs)

    @api.multi
    def open_quotations(self):
        for record in self:
            action_data = record.env.ref('sh_sale_mod.action_sale_quotation').read()[0]
            action_data.update({'domain':[('partner_id','=',record.id)],'context':{'default_partner_id':record.id}})
            return action_data
