import base64
import requests
import io
import mimetypes
import os
from odoo import models, fields
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class ChatwootInstance(models.Model):
    _name = 'chatwoot.instance'
    _description = 'Chatwoot Instance'

    base_url = fields.Char(
        string="Base URL",
        help="URL base do Chatwoot"
    )

    user_ids = fields.Many2many(
        "chatwoot.users",
        "instance_id",
        string="Usuarios"
    )

    name = fields.Char(required=True)

    account_id = fields.Char(
        string="Account ID",
        default="1",
        help="ID da conta do Chatwoot"
    )

    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )

    team_ids = fields.One2many(
        "chatwoot.team",
        "instance_id",
        string="Teams"
    )


    def get_contact_id(self, token, phone_number, partner):
        url = f"{self.base_url}/api/v1/accounts/{self.account_id}/contacts/search"
        params = {
            "q": phone_number,
            "page": 1,
        }
        headers = {
            "api_access_token": token
        }
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        contacts = data.get("payload", [])
        if contacts:
            return contacts[0].get("id")
        else:
            payload = {
                "name": partner.name,
                "phone_number": phone_number
            }
            create_response = requests.post(
                f"{self.base_url}/api/v1/accounts/{self.account_id}/contacts",
                json=payload,
                headers=headers
            )
            created_data = create_response.json()
            id = created_data.get("payload", {}).get("contact", {}).get("id")
            if id:
                return id
            else:
                raise Exception(f"Impossivel Criar Contato no Chatwoot") 

    def create_new_conversation(self, token, phone_number, partner, team_id, assignee_id, inbox_record):
        #TODO Ainda não sei como tratar a conversa, ideias: Busca pela conversa aberta para aquele contato ou
        # criar uma nova conversa sempre e fecha-la depois de enviar a mensagem, o que obriga o user a enviar tudo que for necessário de uma vez só.
        url = f"{self.base_url}/api/v1/accounts/{self.account_id}/conversations"
        payload = {
            "contact_id": self.get_contact_id(token, phone_number, partner),
            "source_id": phone_number,
            "inbox_id":    inbox_record.inbox_id,
            "team_id": int(team_id),
            "assignee_id": int(assignee_id),
            "status": "open",
            # "message": {
            #     "content": content,
            # }
        }
        headers = {
            "api_access_token": token,
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    
    def get_unique_conversation(self, token, conversation_id):
        url_conversation = f"{self.base_url}/api/v1/accounts/{self.account_id}/conversations/{conversation_id}"
        headers = {
            "api_access_token": token
        }
        response_conversation = requests.get(url_conversation, headers=headers)
        return response_conversation.json()

    def get_message(self, token, conversation_id):
        url_message = f"{self.base_url}/api/v1/accounts/{self.account_id}/conversations/{conversation_id}/messages"
        headers = {
            "api_access_token": token
        }
        response_message = requests.get(url_message, headers=headers)
        return response_message.json()

    def set_resolved_conversation(self, token, conversation_id):
        url = f"{self.base_url}/api/v1/accounts/{self.account_id}/conversations/{conversation_id}/toggle_status"
        payload = {
            "status": "resolved",
        }
        headers = {
            "api_access_token": token,
        }
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            raise Exception(f"Failed to resolve conversation {conversation_id}: {response.text}")
        else:
            return True

    def send_text(self, token, conversation_id, message):
        url = f"{self.base_url}/api/v1/accounts/{self.account_id}/conversations/{conversation_id}/messages"
        payload = {
            "content": message,
        }
        headers = {
            "api_access_token": token,
        }
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        return response.json()

    def send_chatwoot_attachment(self, token, conversation_id, attachment, message=None):
        file_content = base64.b64decode(attachment.datas)
        file_stream = io.BytesIO(file_content)

        filename = attachment.name or "arquivo"

        name, ext = os.path.splitext(filename)

        # Se não tiver extensão ou for estranha, força PDF
        if not ext or ext.lower() not in ['.pdf', '.xml', '.jpg', '.png', '.txt']:
            filename = f"{filename}.pdf"

        mimetype = attachment.mimetype
        if not mimetype:
            mimetype, _ = mimetypes.guess_type(filename)

        if not mimetype:
            mimetype = "application/pdf"

        _logger.info(
            "Chatwoot SEND -> conversation_id=%s | attachment_id=%s | filename=%s | checksum=%s | size=%s bytes",
            conversation_id, attachment.id, filename, attachment.checksum, len(file_content)
        )

        url = f"{self.base_url}/api/v1/accounts/{self.account_id}/conversations/{conversation_id}/messages"
        headers = {
            "api_access_token": token
        }

        files = {
            "attachments[]": (
                filename,
                file_stream,
                mimetype
            )
        }

        data = {}
        if message:
            data["content"] = message

        response = requests.post(
            url,
            headers=headers,
            data=data,
            files=files,
            timeout=30,
        )
        response.raise_for_status()
        resp_json = response.json()

        resp_attachments = resp_json.get("attachments", [])
        _logger.info(
            "Chatwoot RESPONSE <- attachment_id=%s | message_id=%s | resp_attachments=%s",
            attachment.id, resp_json.get("id"), resp_attachments
        )

        return resp_json

    def add_label_to_conversation(self, token, conversation_id):
        url = f"{self.base_url}/api/v1/accounts/{self.account_id}/conversations/{conversation_id}/labels"
        payload = {
            "labels": [
                "start_conversation"
            ]
        }
        headers = {
            "api_access_token": token,
        }
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        return response.json()
    
    def action_sync_teams(self):
        self.ensure_one()

        user = self.user_ids.filtered(lambda u: u.api_token)[:1]
        if not user:
            raise UserError("Nenhum usuário com API token")
        url = f"{self.base_url}/api/v1/accounts/{self.account_id}/teams"
        headers = {"api_access_token": user.api_token}
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            raise UserError(r.text)
        Team = self.env["chatwoot.team"]
        data = r.json()  
        for team in data:   
            rec = Team.search([
                ("team_id", "=", team["id"]),
                ("instance_id", "=", self.id)
            ], limit=1)

            vals = {
                "name": team["name"],
                "team_id": team["id"],
                "instance_id": self.id,
                "active": True
            }

            if rec:
                rec.write(vals)
            else:
                Team.create(vals)

        return True
