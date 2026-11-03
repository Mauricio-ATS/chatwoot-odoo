import requests
from odoo import models, fields
from datetime import timedelta

class MailActivity(models.Model):
    _inherit = 'mail.activity'

    chatwoot_id = fields.Many2one(
        'chatwoot.instance', 
        string="Instância", 
        default=lambda self: self.env['chatwoot.instance'].search(
            [('account_id', '=', self.env.user.chatwoot_account_id)],
            limit=1
        ),
    )

    

    def action_notify_activity_cron(self):
        MailActivity = self.env['mail.activity']

        chatwoot = self.env['chatwoot.instance'].search(
            [("account_id", "=", self.env.user.chatwoot_account_id)],
            limit=1
        )

        if not chatwoot:
            return

        inbox = self.env['chatwoot.inbox'].search(
            [('user_chat_id', '=', chatwoot.user_ids[0].id)],
            limit=1
        )

        if not inbox:
            return

        vencimento = fields.Date.today() + timedelta(days=chatwoot.activity_due_days)

        activities = MailActivity.search([
            ('date_deadline', '=', vencimento)
        ])

        team_id = 36        # ATS
        assignee_id = 3     # usuário chatwoot

        for activity in activities:

            notify = f"""
    Olá {activity.user_id.name},
    Você tem uma atividade pendente:

    Tipo: {activity.activity_type_id.name}
    Assunto: {activity.summary}
    Nota: {activity.note}
    Vencimento: {activity.date_deadline}
    """

            phone_number = activity.user_id.partner_id.phone_sanitized

            conversation = chatwoot.create_new_conversation(
                phone_number,
                activity.user_id.partner_id,
                team_id,
                assignee_id,
                inbox
            )

            conversation_id = conversation.get("id")

            if conversation_id:
                chatwoot.send_text(conversation_id, notify)
                chatwoot.set_resolved_conversation(conversation_id)


class ChatwootInstance(models.Model):
    _inherit = 'chatwoot.instance'

    activity_due_days = fields.Integer(
        string="Dias para notificação de atividades",
        default=1,
        help="Número de dias antes do vencimento da atividade para enviar a notificação.",
    )


        