from odoo import api, fields, models
from odoo.exceptions import UserError


class Users(models.Model):
    _inherit = "res.users"

    chatwoot_account_id = fields.Char(
        string="Chatwoot Account ID",
        help="ID da conta do Chatwoot Padrão"
    )
