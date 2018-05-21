# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    service_code = fields.Many2one('delivery.service.code',string="Service Code")

class DeliveryServiceCode(models.Model):
    _name = "delivery.service.code"
    _description = "Delivery Service Code"

    service_code = fields.Char(string="Service Code")
    carrier_code = fields.Char(string="Carrier Code")
    name = fields.Char(string="Name")
    domestic =fields.Boolean(string="Domestic")
    international =fields.Boolean(string="International")
