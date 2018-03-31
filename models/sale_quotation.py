# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class SaleQuotation(models.Model):
    _name = "sale.quotation"
    _description = 'Sale Quotation'
    _order = 'create_date desc'
    _inherit = ['mail.thread']

    name = fields.Char(string='Quotation #', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    reference = fields.Char(string="External Reference")
    partner_id = fields.Many2one('res.partner', string="Customer")
    notes = fields.Text(string="Notes")
    quotation_line_ids = fields.One2many('sale.quotation.line','quotation_id', string="Quotation Lines", store=True)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('sale.quotation.sequence') or _('New')
        result = super(SaleQuotation, self).create(vals)
        return result

    @api.multi
    def open_add_line(self):
        for record in self:
            pricelists = record.env['product.pricelist'].search([])
            action_data = record.env.ref('sh_sale_mod.action_add_sale_quotation').read()[0]
            action_data.update({'context':{'default_quotation_id':record.id,'default_pricelist_ids':[(6,0,pricelists.ids)]}})
            return action_data

    @api.multi
    def action_order_send(self):
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = ir_model_data.get_object_reference('sh_sale_mod', 'mail_template_sale_quotation')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference('mail', 'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        ctx = dict()
        ctx.update({
            'default_model': 'sale.quotation',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
        })
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

class SaleQuotationLine(models.Model):
    _name = "sale.quotation.line"
    _order = "sequence asc"

    quotation_id = fields.Many2one('sale.quotation', string="Quotation")
    product_id = fields.Many2one('product.product', string="Product")
    name = fields.Char('Description',related="product_id.name", readonly="True",store="True")
    original_price = fields.Float(string='Orig. Price',releated="product_id.lst_price", readonly="True",store="True" )
    min_quantity = fields.Float(string='Min. Qty')
    price = fields.Char(string="Price")
    item_id = fields.Many2one('product.pricelist.item',string="Pricelist Items")

    sequence = fields.Integer('Sequence', default=1)

class AddSaleQuotationLine(models.TransientModel):
    _name = "add.sale.quotation.line"
    _description = 'Add Sale Quotation Line Wizard'

    quotation_id = fields.Many2one('sale.quotation',string="Sale Quotation")
    product_id = fields.Many2one('product.product', string="Product")
    pricelist_ids = fields.Many2many('product.pricelist', string="Pricelists")

    @api.multi
    def add_sale_quotation_lines(self):
        for record in self:
            if record.quotation_id:
                print record.pricelist_ids
                pricelist_items = record.pricelist_ids.mapped('item_ids').filtered(lambda r: r.product_tmpl_id == record.product_id.product_tmpl_id)
                print pricelist_items
                if pricelist_items:
                    new_lines = record.env['sale.quotation.line']
                    for line in pricelist_items - record.quotation_id.quotation_line_ids.mapped('item_id'):
                        data = {
                            'product_id': record.product_id.id,
                            'min_quantity': line.min_quantity,
                            'price': line.price,
                            'item_id': line.id,
                        }
                        new_line = new_lines.new(data)
                        new_lines += new_line
                    record.quotation_id.quotation_line_ids += new_lines
                else:
                    new_lines = record.env['sale.quotation.line']
                    data = {
                        'product_id': record.product_id.id,
                        'min_quantity': 1,
                        'price': str(round(record.product_id.list_price,2))+' USD',
                    }
                    new_line = new_lines.new(data)
                    new_lines += new_line
                    record.quotation_id.quotation_line_ids += new_lines
