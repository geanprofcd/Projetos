"""Comando de texto humano transacional; sem transporte ou repetição automática."""
from uuid import UUID

from app.core.config import get_settings
from app.db.supabase import get_admin_client


class HumanCommandConflict(ValueError):
    pass


class HumanCommandUnavailable(ValueError):
    pass


def request_human_text(*, actor_id, ticket_id, body, request_id):
    settings = get_settings()
    if (settings.demo_mode or not settings.whatsapp_persistent_control_enabled
            or settings.app_env not in ('staging', 'production') or not settings.supabase_configured):
        raise ValueError('Comando persistente não configurado.')
    try:
        actor_id, ticket_id, request_id = [str(UUID(str(v))) for v in (actor_id, ticket_id, request_id)]
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Formulário inválido. Atualize o atendimento antes de enviar.') from None
    body = str(body or '').strip()
    if not 1 <= len(body) <= 4096:
        raise ValueError('Digite um texto de até 4096 caracteres.')
    try:
        value = get_admin_client().rpc('vendra_whatsapp_human_request_v1', {
            'p_actor_id': actor_id, 'p_ticket_id': ticket_id,
            'p_body': body, 'p_request_id': request_id,
        }).execute().data
    except Exception as exc:
        code = str(getattr(exc, 'code', ''))
        if code == 'PT409':
            raise HumanCommandConflict('Este formulário já foi utilizado com outro texto. Atualize o atendimento.') from None
        if code in ('22023', '42501'):
            raise ValueError('Confira a janela WhatsApp, o cliente e sua permissão antes de responder.') from None
        # Resultado incerto: o mesmo request_id permite recuperar o comando confirmado.
        raise HumanCommandUnavailable('Não foi possível confirmar o comando. Reenvie este mesmo formulário para conferir, sem trocar o texto.') from None
    try:
        if not isinstance(value, dict) or value.get('accepted') is not True or type(value.get('duplicate')) is not bool:
            raise ValueError
        message_id, outbox_id = str(UUID(value['message_id'])), str(UUID(value['outbox_id']))
        message, outbox = value['message'], value['outbox']
        if (message['id'] != message_id or message['ticket_id'] != ticket_id
                or message['sender_id'] != actor_id or message['body'] != body
                or message['direction'] != 'outbound' or message['is_internal'] is not False
                or message['sender_kind'] != 'human' or message['channel'] != 'whatsapp'
                or outbox['id'] != outbox_id or outbox['ticket_id'] != ticket_id
                or outbox['message_id'] != message_id):
            raise ValueError
    except (KeyError, ValueError, TypeError, AttributeError):
        raise HumanCommandUnavailable('O banco não confirmou o comando. Reenvie este mesmo formulário para conferir.') from None
    return {'accepted': True, 'duplicate': value['duplicate'], 'message_id': message_id,
            'outbox_id': outbox_id, 'outbox': {k: outbox.get(k) for k in
                ('id', 'ticket_id', 'message_id', 'status', 'created_at')}}
