# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import datetime, base64, json, requests

class ResCompany(models.Model):
    _inherit = "res.company"

    shipstation_key = fields.Char(string="SS Key")
    shipstation_secret = fields.Char(string="SS Secret")
    shipstation_root_endpoint = fields.Char(string="SS Root Endpoint")

    @api.multi
    def shipstation_connection(self,url,method,data_to_post):
        for record in self:
            if  not record.shipstation_root_endpoint or not record.shipstation_key or not record.shipstation_secret:
                raise UserError(_("Shipstation API is not configured correctly, make sure all keys and urls are present."))
            api_key = record.shipstation_key
            secret =  record.shipstation_secret

            auth_string = base64.encodestring(('%s:%s' % (api_key,secret)).encode()).decode().replace('\n', '')

            headers = {
              'Authorization': "Basic %s" % auth_string
            }
            if method == 'DELETE':
                r = requests.delete(url, headers=headers)
            elif method == 'POST':
                headers.update({'Content-Type': 'application/json'})
                r = requests.post(url,data=data_to_post, headers=headers)
            else:
                r = requests.get(url, headers=headers)
            return r,r.content

    @api.multi
    def get_carriers(self):
        for record in self:
            url = '%s/carriers' % (record.shipstation_root_endpoint)
            conn = record.shipstation_connection(url,'GET',False)
            response = conn[0]
            content = conn[1]
            if response.status_code != requests.codes.ok:
                raise UserError(_("%s\n%s: %s" % (url,response.status_code,content)))
            json_object_str = content
            json_object = json.loads(json_object_str)
            carrier_list = []
            for c in json_object:
                carrier_list.append(c['code'])
                if not record.env['delivery.carrier.code'].search([('code','=',c['code'])]):
                    record.env['delivery.carrier.code'].create({'name':c['name'],'code':c['code']})
            return carrier_list

    @api.multi
    def get_service(self):
        for record in self:
            carrier_list = record.get_carriers()
            for c in carrier_list:
                url = '%s/carriers/listservices?carrierCode=%s' % (record.shipstation_root_endpoint,c)
                conn = record.shipstation_connection(url,'GET',False)
                response = conn[0]
                content = conn[1]
                if response.status_code != requests.codes.ok:
                    raise UserError(_("%s\n%s: %s" % (url,response.status_code,content)))
                service = record.env['delivery.carrier']
                present_service_list = service.search([]).mapped('service_code')
                json_object_str = content
                json_object = json.loads(json_object_str)
                for c in json_object:
                    if c['code'] not in present_service_list:
                        data = {
                            'name': c['name'],
                            'integration_level': 'rate',
                            'carrier_code': record.env['delivery.carrier.code'].search([('code','=',c['carrierCode'])]).id,
                            'service_code': c['code'],
                            'product_id': record.env.ref('sh_sale_mod.delivery_product').product_variant_id.id,
                        }
                        service.create(data)
