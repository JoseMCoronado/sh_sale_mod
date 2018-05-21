# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import requests,datetime, json, binascii

class Picking(models.Model):
    _inherit = "stock.picking"

    ss_id = fields.Integer(string="Shipstation ID", copy=False)
    ss_ship_id = fields.Integer(string="Shipment ID", copy=False)
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

    @api.multi
    def do_transfer(self):
        super(Picking, self).do_transfer()
        for record in self:
            if record.ss_id != 0 and record.ss_status not in ['cancelled','shipped']:
                record.ship_ss()
            return True

    @api.multi
    def action_cancel(self):
        super(Picking, self).action_cancel()
        for record in self:
            if record.ss_id != 0 and record.ss_status not in ['cancelled','shipped']:
                record.delete_ssorder()
            return True


    @api.multi
    def create_update_ssorder(self):
        for record in self:
            company = record.env.user.company_id
            customer = record.partner_id
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
                }
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

    @api.multi
    def create_ss_label(self):
        for record in self:
            company = record.env.user.company_id
            url = '%s/orders/createlabelfororder' % (company.shipstation_root_endpoint)
            if not record.carrier_id or not record.carrier_id.service_code:
                raise UserError(_("Either the picking does not have a carrier selected or the carrier is not configured correctly."))
            python_dict =   {
                "orderId": record.ss_id,
                "carrierCode": record.carrier_id.service_code.carrier_code,
                "serviceCode": record.carrier_id.service_code.service_code,
                "packageCode": "package",
                "confirmation": record.confirmation,
                "shipDate": datetime.datetime.now().strftime('%Y-%m-%d'),
                "testLabel": False,
                "weight": {
                  "value": record.weight,
                  "units": "pounds"
                },
              }
            data_to_post = json.dumps(python_dict)
            conn = company.shipstation_connection(url,'POST',data_to_post)
            response = conn[0]
            content = conn[1]
            json_object_str = content
            json_object = json.loads(json_object_str)
            if response.status_code != requests.codes.ok:
                raise UserError(_("%s\n%s: %s" % (url,response.status_code,json_object['ExceptionMessage'])))
            record.write({
                'ss_ship_id': json_object['shipmentId'],
                'carrier_tracking_ref': json_object['trackingNumber'],
                'ss_status': 'awaiting_shipment',
            })
            logmessage = ("""<b>Shipstation</b> %s label for order <b>%s</b> has been <b>created</b> via the API.\n
            Tracking: %s\n
            Shipment Cost: %s\n
            Insurance Cost: %s""") % (record.carrier_id.name,record.ss_id,
            record.carrier_tracking_ref,
            json_object['shipmentCost'],
            json_object['insuranceCost'])
            record.message_post(body=logmessage, attachments=[('Label_%s-%s.%s' % (record.carrier_id.service_code.carrier_code,record.carrier_tracking_ref,'pdf'),
             binascii.a2b_base64(json_object['labelData']))])

    @api.multi
    def ship_ss(self):
        for record in self:
            company = record.env.user.company_id
            url = '%s/orders/markasshipped' % (company.shipstation_root_endpoint)
            python_dict = {
                "orderId": record.ss_id,
                "carrierCode": record.carrier_id.service_code.carrier_code,
                "shipDate": datetime.datetime.strptime(record.date_done,'%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d'),
                "trackingNumber": record.carrier_tracking_ref or None,
                "notifyCustomer": False,
                "notifySalesChannel": False
            }
            data_to_post = json.dumps(python_dict)
            conn = company.shipstation_connection(url,'POST',data_to_post)
            response = conn[0]
            content = conn[1]
            json_object_str = content
            json_object = json.loads(json_object_str)
            if response.status_code != requests.codes.ok:
                raise UserError(_("%s\n%s: %s" % (url,response.status_code,json_object['ExceptionMessage'])))
            record.write({
                'ss_status': 'shipped',
            })
            record.message_post(body=_("<b>Shipstation</b> order <b>%s</b> has been marked as <b>shipped</b> via the API.") % (json_object['orderId']))

    @api.multi
    def delete_ssorder(self):
        for record in self:
            company = record.env.user.company_id
            if not record.ss_id:
                raise UserError(_("There is no shipstation order linked to this transfer."))
            url = '%s/orders/%s' % (company.shipstation_root_endpoint,record.ss_id)
            conn = company.shipstation_connection(url,'DELETE',False)
            response = conn[0]
            content = conn[1]
            if response.status_code != requests.codes.ok:
                raise UserError(_("%s\n%s: %s" % (url,response.status_code,content)))
            json_object_str = content
            json_object = json.loads(json_object_str)
            record.write({
                'ss_status': 'cancelled',
            })
            record.message_post(body=_("<b>Shipstation</b> order <b>%s</b> %s") % (record.ss_id,json_object['message']))
