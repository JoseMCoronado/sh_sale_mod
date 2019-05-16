# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleQuotation(models.Model):
    _name = "sale.quotation"
    _description = "Sale Quotation"
    _order = "create_date desc"
    _inherit = ["mail.thread"]

    name = fields.Char(
        string="Quotation #",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _("New"),
    )
    reference = fields.Char(string="Internal Reference", tracking="onchange")
    partner_id = fields.Many2one(
        "res.partner", string="Customer", tracking="onchange", required=True
    )
    notes = fields.Text(string="Message for Customers", tracking="onchange")
    quotation_line_ids = fields.One2many(
        "sale.quotation.line",
        "quotation_id",
        string="Quotation Lines",
        store=True,
        tracking="onchange",
    )
    destination_pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Destination Pricelist",
        tracking="onchange",
        required=True,
    )
    show_add = fields.Boolean(
        "Show Add (Technical)", compute="_show_add_button", store=False, readonly=True
    )
    show_modify = fields.Boolean(
        "Show Modify(Technical)", compute="_show_add_button", store=False, readonly=True
    )
    display_msrp = fields.Boolean("Display MSRP")

    @api.multi
    def _show_add_button(self):
        for record in self:
            if any(not l.item_id for l in record.quotation_line_ids):
                record.show_add = True
            if any(l.item_id for l in record.quotation_line_ids):
                record.show_modify = True

    @api.model
    def create(self, vals):
        if vals.get("name", _("New")) == _("New"):
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "sale.quotation.sequence"
            ) or _("New")
        result = super(SaleQuotation, self).create(vals)
        return result

    @api.multi
    def add_pricelist_items(self):
        for record in self:
            if record.destination_pricelist_id:
                for line in record.quotation_line_ids.filtered(lambda x: not x.item_id):
                    data = {
                        "product_tmpl_id": line.product_id.product_tmpl_id.id,
                        "applied_on": "1_product",
                        "min_quantity": line.min_quantity,
                        "compute_price": line.compute_price,
                        "fixed_price": line.fixed_price,
                        "percent_price": line.percent_price,
                        "pricelist_id": record.destination_pricelist_id.id,
                    }
                    newitem = record.env["product.pricelist.item"].create(data)
                    line.write({"item_id": newitem.id})
            else:
                raise UserError(_("Destination pricelist has not been set."))

    @api.multi
    def modify_pricelist_items(self):
        for record in self:
            if record.destination_pricelist_id:
                for line in record.quotation_line_ids.filtered(lambda x: x.item_id):
                    data = {
                        "product_tmpl_id": line.product_id.product_tmpl_id.id,
                        "applied_on": "1_product",
                        "min_quantity": line.min_quantity,
                        "compute_price": line.compute_price,
                        "fixed_price": line.fixed_price,
                        "percent_price": line.percent_price,
                        "pricelist_id": record.destination_pricelist_id.id,
                    }
                    line.item_id.write(data)
            else:
                raise UserError(_("Destination pricelist has not been set."))

    @api.multi
    def open_add_line(self):
        for record in self:
            pricelist = []
            if record.partner_id.property_product_pricelist:
                pricelist.append(record.partner_id.property_product_pricelist.id)
            if record.destination_pricelist_id.id:
                pricelist.append(record.destination_pricelist_id.id)
            action_data = record.env.ref(
                "sh_sale_mod.action_add_sale_quotation"
            ).read()[0]
            action_data.update(
                {
                    "context": {
                        "default_quotation_id": record.id,
                        "default_pricelist_ids": [(6, 0, pricelist)],
                    }
                }
            )
            return action_data

    @api.multi
    def action_order_send(self):
        self.ensure_one()
        ir_model_data = self.env["ir.model.data"]
        try:
            template_id = ir_model_data.get_object_reference(
                "sh_sale_mod", "mail_template_sale_quotation"
            )[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference(
                "mail", "email_compose_message_wizard_form"
            )[1]
        except ValueError:
            compose_form_id = False
        ctx = dict()
        ctx.update(
            {
                "default_model": "sale.quotation",
                "default_res_id": self.ids[0],
                "default_use_template": bool(template_id),
                "default_template_id": template_id,
                "default_composition_mode": "comment",
            }
        )
        return {
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "views": [(compose_form_id, "form")],
            "view_id": compose_form_id,
            "target": "new",
            "context": ctx,
        }


class SaleQuotationLine(models.Model):
    _name = "sale.quotation.line"
    _order = "sequence asc"

    quotation_id = fields.Many2one("sale.quotation", string="Quotation")
    product_id = fields.Many2one("product.product", string="Product")
    name = fields.Char("Description", store="True")
    original_price = fields.Float(
        string="Orig. Price", related="product_id.lst_price", readonly=True, store=False
    )
    min_quantity = fields.Float(string="Min. Qty")
    price = fields.Char(
        "Price",
        compute="_get_pricelist_item_name_price",
        help="Explicit rule name for this pricelist line.",
    )
    item_id = fields.Many2one("product.pricelist.item", string="Pricelist Items")
    sequence = fields.Integer("Sequence", default=1)
    compute_price = fields.Selection(
        [("fixed", "Fixed Price"), ("percentage", "Percent (Discount)")],
        string="Compute Method",
        copy=False,
    )
    fixed_price = fields.Float(string="Fixed Price")
    percent_price = fields.Float(string="Percent Price (%)")


class AddSaleQuotationLine(models.TransientModel):
    _name = "add.sale.quotation.line"
    _description = "Add Sale Quotation Line Wizard"

    quotation_id = fields.Many2one("sale.quotation", string="Sale Quotation")
    product_id = fields.Many2one("product.product", string="Product")
    pricelist_ids = fields.Many2many("product.pricelist", string="Pricelists")

    @api.multi
    def add_sale_quotation_lines(self):
        for record in self:
            if record.quotation_id:
                pricelist_items = record.pricelist_ids.mapped("item_ids").filtered(
                    lambda r: r.product_tmpl_id == record.product_id.product_tmpl_id
                )
                if pricelist_items:
                    new_lines = record.env["sale.quotation.line"]
                    for line in (
                        pricelist_items
                        - record.quotation_id.quotation_line_ids.mapped("item_id")
                    ):
                        if (
                            line.pricelist_id
                            == record.quotation_id.destination_pricelist_id
                        ):
                            item = line.id
                        else:
                            item = False
                        data = {
                            "product_id": record.product_id.id,
                            "min_quantity": line.min_quantity,
                            "compute_price": line.compute_price,
                            "fixed_price": line.fixed_price,
                            "percent_price": line.percent_price,
                            "item_id": item,
                        }
                        new_line = new_lines.new(data)
                        new_lines += new_line
                    record.quotation_id.quotation_line_ids += new_lines
                else:
                    new_lines = record.env["sale.quotation.line"]
                    data = {
                        "product_id": record.product_id.id,
                        "min_quantity": 1,
                        "compute_price": "fixed",
                        "fixed_price": record.product_id.list_price,
                    }
                    new_line = new_lines.new(data)
                    new_lines += new_line
                    record.quotation_id.quotation_line_ids += new_lines
