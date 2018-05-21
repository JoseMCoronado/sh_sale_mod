# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class ResUsers(models.Model):
    _inherit = "res.users"

    auto_online = fields.Boolean(string='Auto Online (Technical)')
