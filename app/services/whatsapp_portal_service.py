"""Conversas reais e controle persistente, exclusivamente no STAGING."""
from uuid import UUID
from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.access_service import level_for


class ConversationConflict(ValueError):
    pass


def _db():
    settings = get_settings()
    if settings.app_env != 'staging' or settings.demo_mode:
        raise ValueError('Conversas disponíveis somente no ambiente de homologação.')
    return get_admin_client()


def _id(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Atendimento inválido.') from None


def list_conversations():
    db = _db()
    rows = db.table('tickets').select('id,title,customer_id,status,automation_mode,updated_at').eq(
        'source', 'whatsapp').order('updated_at', desc=True).limit(100).execute().data or []
    if not rows:
        return []
    people = db.table('customers').select('id,name').in_(
        'id', list({r['customer_id'] for r in rows})).execute().data or []
    names = {p['id']: p['name'] for p in people}
    for row in rows:
        row['customer_name'] = names.get(row['customer_id'], 'Cliente')
    return rows


def get_conversation(ticket_id):
    ticket_id = _id(ticket_id)
    db = _db()
    rows = db.table('tickets').select('id,title,customer_id,status,automation_mode,automation_version').eq(
        'id', ticket_id).eq('source', 'whatsapp').limit(1).execute().data or []
    if not rows:
        return None
    ticket = rows[0]
    people = db.table('customers').select('name').eq('id', ticket['customer_id']).limit(1).execute().data or []
    ticket['customer_name'] = people[0]['name'] if people else 'Cliente'
    # Latest page, displayed chronologically; never expose WAMIDs/claim tokens.
    messages = db.table('messages').select('id,body,sender_kind,direction,delivery_status,created_at').eq(
        'ticket_id', ticket_id).eq('channel', 'whatsapp').eq('is_internal', False).order(
        'created_at', desc=True).order('id', desc=True).limit(100).execute().data or []
    control = db.rpc('vendra_whatsapp_control_v1', {'p_ticket_id': ticket_id}).execute().data
    if not isinstance(control, dict):
        raise RuntimeError('Controle de atendimento indisponível.')
    return {'ticket': ticket, 'messages': list(reversed(messages)), 'control': control}


def change_mode(*, ticket_id, mode, version, user):
    if user.get('status') != 'active' or level_for(user) != 'administrativo':
        raise PermissionError('Somente administradores podem alterar a automação.')
    ticket_id = _id(ticket_id)
    if mode not in ('human', 'ai') or isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError('Controle inválido. Atualize a conversa.')
    db = _db()
    detail = get_conversation(ticket_id)
    if not detail or detail['ticket']['status'] in ('finalizado', 'cancelado'):
        raise ValueError('Atendimento encerrado ou indisponível.')
    control = detail['control']
    if version != control.get('control_version'):
        raise ConversationConflict('Outra pessoa alterou o controle. Atualize a conversa.')
    if mode == 'ai' and not (control.get('enabled') and control.get('window_open')):
        raise ValueError('A IA exige automação disponível e uma mensagem do cliente nas últimas 24 horas.')
    try:
        result = db.rpc('vendra_whatsapp_mode_v1', {'p_ticket_id': ticket_id, 'p_mode': mode,
            'p_expected_version': version, 'p_actor_id': _id(user.get('id'))}).execute().data
    except Exception as exc:
        if str(getattr(exc, 'code', '')) in ('PT409', '40001'):
            raise ConversationConflict('Outra pessoa alterou o controle. Atualize a conversa.') from None
        raise
    if not isinstance(result, dict) or result.get('mode') != mode:
        raise RuntimeError('O banco não confirmou a alteração.')
    return result
