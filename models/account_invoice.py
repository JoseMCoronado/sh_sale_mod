# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    picking_id = fields.Many2one('stock.picking', string="Picking")

    @api.constrains('picking_id')
    def set_tracking_to_invoice(self):
        for record in self:
            if record.picking_id:
                record.write({'x_tracking':record.picking_id.ship_date,'x_ship_date':record.picking_id.carrier_tracking_ref})
