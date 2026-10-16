"""Adapta as RPCs homologadas ao contrato da interface comercial existente."""
from uuid import UUID
from app.core.config import get_settings
from app.db.supabase import get_admin_client


class ControlConflict(ValueError):
    pass


def _uuid(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Atendimento ou usuário inválido.') from None


def _db():
    settings = get_settings()
    if (settings.demo_mode or not settings.whatsapp_persistent_control_enabled
            or settings.app_env not in ('staging', 'production') or not settings.supabase_configured):
        raise ValueError('Controle persistente não configurado.')
    return get_admin_client()


def _map(value, assistant_name):
    if (not isinstance(value, dict) or value.get('accepted') is not True or value.get('mode') not in ('ai','human')
            or isinstance(value.get('control_version'), bool) or not isinstance(value.get('control_version'), int)):
        raise ValueError('O banco não confirmou o controle do atendimento.')
    result = {k:value.get(k) for k in ('enabled','mode','connected','route_to_ai','control_version','window_open','expires_at','thread_id')}
    result.update(mode_label='Conectado à IA' if result['connected'] else 'IA desconectada deste atendimento',
        connection_state='connected' if result['connected'] else 'disconnected',
        # Existing UI uses this field to choose Connect/Disconnect. Window policy remains route_to_ai.
        should_respond=bool(result['connected']),assistant_name=assistant_name,requires_migration=False)
    return result


def read_control(ticket_id, *, assistant_name='Assistente de IA'):
    db = _db();ticket_id = _uuid(ticket_id)
    try:
        value = db.rpc('vendra_whatsapp_control_v1', {'p_ticket_id':ticket_id}).execute().data
    except Exception:
        raise ValueError('Controle do atendimento indisponível. Confira a integração antes de alterar a IA.') from None
    return _map(value, assistant_name)


def change_mode(ticket_id, *, mode, actor_id, assistant_name='Assistente de IA', expected_version=None):
    if mode not in ('ai','human'):
        raise ValueError('Modo de atendimento inválido.')
    db = _db();ticket_id=_uuid(ticket_id);actor_id=_uuid(actor_id)
    # Match the ACL of the currently homologated SQL, without impersonation or implicit grants.
    profiles = db.table('profiles').select('access_level,status').eq('id',actor_id).limit(1).execute().data or []
    if not profiles or profiles[0].get('status')!='active' or profiles[0].get('access_level') not in ('administrativo','comercial','gerencial'):
        raise ValueError('Somente a equipe de atendimento ativa pode alterar a automação persistente.')
    control = read_control(ticket_id,assistant_name=assistant_name)
    if expected_version is not None and (isinstance(expected_version,bool) or not isinstance(expected_version,int)
            or expected_version!=control['control_version']):
        raise ControlConflict('Outra pessoa alterou o controle. Atualize o atendimento.')
    if mode=='ai' and not (control.get('enabled') and control.get('window_open')):
        raise ValueError('A IA exige automação disponível e mensagem do cliente nas últimas 24 horas.')
    try:
        result = db.rpc('vendra_whatsapp_mode_v1', {'p_ticket_id':ticket_id,'p_mode':mode,
            'p_expected_version':control['control_version'],'p_actor_id':actor_id}).execute().data
    except Exception as exc:
        if str(getattr(exc,'code','')) in ('PT409','40001'):
            raise ControlConflict('Outra pessoa alterou o controle. Atualize o atendimento.') from None
        raise ValueError('Não foi possível confirmar a alteração. Atualize o atendimento antes de repetir.') from None
    mapped=_map(result,assistant_name)
    if mapped['mode']!=mode:
        raise ValueError('O banco não confirmou a alteração.')
    return mapped
