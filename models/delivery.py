# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    service_code = fields.Char(string="Service Code")
    carrier_code = fields.Many2one('delivery.carrier.code',string="Carrier Code")

class DeliveryServiceCode(models.Model):
    _name = "delivery.service.code"
    _description = "Delivery Service Code"

    service_code = fields.Char(string="Service Code")
    carrier_code = fields.Char(string="Carrier Code")
    name = fields.Char(string="Name")
    domestic =fields.Boolean(string="Domestic")
    international =fields.Boolean(string="International")

class DeliveryCarrierCode(models.Model):
    _name = "delivery.carrier.code"
    _description = "Delivery Carrier Code"

    name = fields.Char(string="Name")
    code = fields.Char(string="Code")

class CustomerShippingAccount(models.Model):
    _name = 'customer.shipping.account'
    _description = "Customer Shipping Accounts"
    _order = "sequence asc"

    sequence = fields.Integer('Sequence', default=1, help="Lower is better.")
    name = fields.Char(string="Account Number")
    carrier_id = fields.Many2one('delivery.carrier',string="Carrier")
    notes = fields.Char(string="Notes")
    partner_id = fields.Many2one('res.partner',string="Customer")
    zip = fields.Char(string="Billing Zip")
    sh_account = fields.Boolean(string="Speedhut Account")

    @api.multi
    def name_get(self):

        def _name_get(d):
            name = d.get('name', '')
            #partner_id = d.get('partner_id', '')
            carrier_id = d.get('carrier_id', '')
            name = '%s' % (name)
            if carrier_id:
                name = '%s (%s)' % (name,carrier_id)
            return (d['id'], name)

        self.check_access_rights("read")
        self.check_access_rule("read")

        result = []
        for record in self.sudo():
            mydict = {
                      'id': record.id,
                      'partner_id': record.partner_id.name,
                      'carrier_id': record.carrier_id.carrier_code.name,
                      'name': record.name,
                      }
            result.append(_name_get(mydict))
        return result
