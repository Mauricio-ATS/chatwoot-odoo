import base64
import requests
import io
import mimetypes
import os
from odoo import models, fields
from odoo.exceptions import UserError

class ChatwootUsers(models.Model):
    _name = 'chatwoot.users'
    _description = 'Chatwoot Users'


    inbox_ids = fields.One2many(
        "chatwoot.inbox",
        "user_chat_id",
        string="Inboxes"
    )

    instance_id = fields.Many2one(
        "chatwoot.instance",
        ondelete="cascade"
    )

    code = fields.Char(
        string="Código Técnico",
        required=True,
        help="Chave usada para mapear o usuário no selection"
    )
    
    name = fields.Char(required=True)

    api_token = fields.Char(
        string="API Token",
        help="Token de acesso à API do Chatwoot"
    )

    def action_sync_inboxes(self):
        instances = self.env["chatwoot.instance"].search([("user_ids", "in", self.id)])
        if not instances:
            raise UserError("Usuário não está associado a nenhuma instância do Chatwoot.")
        for instance in instances:
            self.write({"instance_id": [(4, instance.id)]})
            url = f"{instance.base_url}/api/v1/accounts/{instance.account_id}/inboxes"
            headers = {"api_access_token": self.api_token}

            r = requests.get(url, headers=headers, timeout=30)
            data = r.json()

            Inbox = self.env["chatwoot.inbox"]

            for inbox in data.get("payload", []):
                rec = Inbox.search([
                    ("user_chat_id", "=", self.id),
                    ("inbox_id", "=", inbox["id"])
                ], limit=1)

                vals = {
                    "name": inbox["name"],
                    "inbox_id": inbox["id"],
                    "user_chat_id": self.id
                }

                if rec:
                    rec.write(vals)
                else:
                    Inbox.create(vals)

class ChatwootInbox(models.Model):
    _name = "chatwoot.inbox"
    _description = "Chatwoot Inbox"

    name = fields.Char(required=True)
    inbox_id = fields.Integer(required=True)
    user_chat_id = fields.Many2one(
        "chatwoot.users",
        required=True,
        ondelete="cascade"
    )
    sequence = fields.Integer(default=10)


class ChatwootTeam(models.Model):
    _name = "chatwoot.team"
    _description = "Chatwoot Team"

    name = fields.Char(required=True)

    team_id = fields.Integer(
        required=True,
        index=True
    )

    instance_id = fields.Many2one(
        "chatwoot.instance",
        required=True,
        ondelete="cascade"
    )

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("team_instance_unique",
         "unique(team_id, instance_id)",
         "Team já existe para esta instância.")
    ]


   