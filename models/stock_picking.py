# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import requests,datetime, json, binascii

class Picking(models.Model):
    _inherit = "stock.picking"

    ss_id = fields.Integer(string="Shipstation ID", copy=False)
    ss_status = fields.Selection([
        ('awaiting_payment', 'Awaiting Payment'),
        ('awaiting_shipment', 'Awaiting Shipment'),
        ('shipped', 'Shipped'),
        ('on_hold', 'On Hold'),
        ('cancelled', 'Cancelled'),
        ], string='Shiipstation Status', copy=False)
    ss_address_status = fields.Selection([
        ('Address not yet validated', 'Address not Validated'),
        ('Address validated successfully', 'Address Validated'),
        ('Address validation warning', 'Address Validation Warning'),
        ('Address validation failed', 'Address Validation Failed'),
        ], string='Shipstation Address', copy=False)
    confirmation = fields.Selection([
        ('none', 'None'),
        ('delivery', 'Delivery'),
        ('signature', 'Signature'),
        ('adult_signature', 'Adult Signature'),
        ('direct_signature', 'Direct Signature'),
        ], string='Confirmation method', default='none',copy=False)
    do_not_send = fields.Boolean(string="Do Not Send to Shipstaion")
    customer_ship_account = fields.Many2one('customer.shipping.account',string="Third Party Account")
    ship_date = fields.Date(string="Ship Date")

    
