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

    @api.constrains('carrier_tracking_ref','ship_date')
    def set_tracking_to_invoice(self):
        for record in self:
            invoices = record.env['account.invoice'].search([('picking_id','=',record.id)])
            for inv in invoices:
                inv.write({'x_tracking':record.carrier_tracking_ref,'x_ship_date':record.ship_date})

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
                        invoice.write({
                            'picking_id': record.id,
                            'x_request_date': record.requested_date,
                            'x_commitment_date': record.commitment_date,
                        })
                except:
                    continue
            return True

    @api.multi
    def create_update_ssorder(self):
        for record in self:
            company = record.env.user.company_id
            customer = record.partner_id
            if record.sale_workorder_id:
                ss_name = str(record.sale_workorder_id.name)
            else:
                ss_name =str(record.name)
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
            if record.sale_id and record.sale_id.client_order_ref:
                clientref = record.sale_id.client_order_ref
            else:
                clientref = ''
            python_dict = {
                    "orderNumber": ss_name,
                    "orderKey": str(record.id),
                    "orderDate": str(datetime.datetime.now()),
                    "billTo": customer_object,
                    "shipTo": customer_object,
                    "items": order_item_list,
                    "orderStatus": record.ss_status or "awaiting_shipment",
                    "customerEmail": selected_email,
                    "customerNotes": clientref,
                }
            if record.carrier_id:
                python_dict.update({'carrierCode':record.carrier_id.carrier_code.code,'serviceCode':record.carrier_id.service_code})
            if record.customer_ship_account:
                add_option = {
                    "advancedOptions": {
                      "billToParty":"third_party",
                      "billToAccount": record.customer_ship_account.name,
                      "billToPostalCode": record.customer_ship_account.zip,
                      "billToCountryCode": record.customer_ship_account.partner_id.country_id.code or "US",
                      "customField1": record.customer_ship_account.carrier_id.name,
                      "customField2": record.customer_ship_account.name,
                      "customField3": record.customer_ship_account.zip,
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
