# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class SaleOrder(models.Model):
    _inherit = "sale.order"

    order_type = fields.Selection([
        ('order', 'Sales Order'),
        ('rma', 'RMA'),
        ], string='Order Type (Technical)', default="order")
    original_sale_id = fields.Many2one('sale.order',string="Original Sale Order")
    rma_count = fields.Integer(string='RMA count',compute='_get_rma_count',readonly=True,store=False)
    rma_ids = fields.One2many('sale.order', 'original_sale_id', string='RMAs')
    defect_order_line = fields.One2many('sale.order.line', related="order_line",string="Defect Order Lines")

    @api.multi
    def action_view_rma_orders(self):
        action = self.env.ref('sale.action_quotations')
        result = action.read()[0]
        result['context'] = {}
        all_rma_ids = sum([order.rma_ids.ids for order in self], [])
        if len(all_rma_ids) > 1:
            result['domain'] = "[('id','in',[" + ','.join(map(str, all_rma_ids)) + "])]"
        elif len(all_rma_ids) == 1:
            res = self.env.ref('sale.view_order_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = all_rma_ids and all_rma_ids[0] or False
        return result

    @api.multi
    def _get_rma_count(self):
        for order in self:
            order.rma_count = len(order.rma_ids)

    @api.multi
    def create_rma(self):
        for record in self:
            copied_sale = record.copy()
            copied_sale.order_type = 'rma'
            copied_sale.name = self.env['ir.sequence'].next_by_code('rma.sequence')
            copied_sale.client_order_ref = copied_sale.name
            copied_sale.original_sale_id = record.id
            action = record.env.ref('sale.action_quotations')
            result = action.read()[0]
            res = record.env.ref('sale.view_order_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = copied_sale.id
            return result

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    defect_type = fields.Many2one('sale.order.line.defect.type',string="Defect Type")
    defect_notes = fields.Text(string="Defect Notes")

class SaleOrderLineDefectType(models.Model):
    _name = "sale.order.line.defect.type"
    _description = "RMA Defect Type"

    name = fields.Char(string="Type")
