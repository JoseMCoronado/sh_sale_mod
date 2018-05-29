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
    customer_ship_account = fields.Many2one('x_customer.shipping.account',string="Third Party Account")
    ship_date = fields.Date(string="Ship Date")

    @api.constrains('partner_id')
    def set_shipping_account(self):
        for record in self:
            accounts = record.env['x_customer.shipping.account'].search([('x_partner_id','=',record.partner_id.id)])
            if accounts:
                if record.carrier_id:
                    refined_accounts = accounts.search([('x_carrier_id','=',record.carrier_id.id)])
                    if refined_accounts:
                        record.customer_ship_account = refined_accounts[0]
                else:
                    record.customer_ship_account = accounts[0]

    @api.constrains('carrier_tracking_ref','ship_date')
    def set_tracking_to_invoice(self):
        for record in self:
            invoices = record.env['account.invoice'].search([('picking_id','=',record.id)])
            for inv in invoices:
                inv.write({'x_tracking':record.ship_date,'x_ship_date':record.carrier_tracking_ref})

    @api.multi
    def do_transfer(self):
        super(Picking, self).do_transfer()
        for record in self:
            if record.picking_type_code == 'outgoing' and record.do_not_send != True:
                record.create_update_ssorder()
            if record.sale_id and not record.purchase_id:
                try:
                    record.sale_id.action_invoice_create()
                    for invoice in record.sale_id.invoice_ids.filtered(lambda r: r.state == 'draft'):
                        invoice.action_invoice_open()
                        invoice.picking_id = record.id
                except:
                    continue
            return True

    @api.multi
    def create_update_ssorder(self):
        for record in self:
            company = record.env.user.company_id
            customer = record.partner_id

            domain_customers = []
            domain_customers.append(customer.id)
            if customer.parent_id :
                domain_customers.append(customer.parent_id.id)
            children = record.env['res.partner'].browse(domain_customers).mapped('child_ids').filtered(lambda x: x.type == 'delivery')
            if children:
                selected_email = children[0].email
            else:
                selected_email = customer.email

            customer_object = {
              "name": customer.name,
              "company": customer.parent_id.name or None,
              "street1": customer.street,
              "street2": customer.street2 or None,
              "city": customer.city,
              "state": customer.state_id.code,
              "postalCode": customer.zip,
              "country": customer.country_id.code,
              "phone": customer.phone or None,
            }
            url = '%s/orders/createorder' % (company.shipstation_root_endpoint)
            order_item_list = []
            for p in record.pack_operation_product_ids:
                newitem = {
                  "lineItemKey": str(p.id),
                  "sku": p.product_id.default_code,
                  "name": p.product_id.name,
                  "weight": {
                    "value": p.product_id.weight,
                    "units": "pounds"
                  },
                  "quantity": int(p.product_qty),
                  "unitPrice": p.product_id.product_tmpl_id.list_price,
                  "upc": p.product_id.barcode or None,
                }
                order_item_list.append(newitem)

            python_dict = {
                    "orderNumber": str(record.name),
                    "orderKey": str(record.id),
                    "orderDate": str(datetime.datetime.now()),
                    "billTo": customer_object,
                    "shipTo": customer_object,
                    "items": order_item_list,
                    "orderStatus": record.ss_status or "awaiting_shipment",
                    "customerEmail": selected_email
                }
            if record.customer_ship_account:
                add_option = {
                    "advancedOptions": {
                      "billToParty":"third_party",
                      "billToAccount": record.customer_ship_account.x_acct_num,
                      "billToPostalCode": record.customer_ship_account.x_zip,
                      "billToCountryCode": record.customer_ship_account.x_partner_id.country_id.code or "US",
                      "customField1": record.customer_ship_account.x_carrier_id.name,
                      "customField2": record.customer_ship_account.x_acct_num,
                      "customField3": record.customer_ship_account.x_zip,
                    },
                }
                python_dict.update(add_option)
            data_to_post = json.dumps(python_dict)
            conn = company.shipstation_connection(url,'POST',data_to_post)
            response = conn[0]
            content = conn[1]
            if response.status_code != requests.codes.ok:
                raise UserError(_("%s\n%s: %s" % (url,response.status_code,content)))
            json_object_str = content
            json_object = json.loads(json_object_str)
            if record.ss_id == 0:
                record.message_post(body=_("<b>Shipstation</b> order <b>%s</b> has been <b>created</b> via the API.") % (json_object['orderId']))
            else:
                record.message_post(body=_("<b>Shipstation</b> order <b>%s</b> has been <b>updated</b> via the API.") % (json_object['orderId']))
            record.write({
                'ss_id': json_object['orderId'],
                'ss_status': json_object['orderStatus'],
                'ss_address_status': json_object['shipTo']['addressVerified'],
            })
