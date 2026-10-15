"""H1-005B8: contrato transacional de homologacao, NUNCA um transportador.

Somente leitura de CRM/preflight e RPCs em tabelas staging_transport_*. Nunca
executa fila real, Make/Meta, webhooks ou qualquer pedido de envio.
"""
from __future__ import annotations
import hashlib
from uuid import UUID
from app.db.supabase import get_admin_client
from app.services import staging_delivery_preflight_service as preflight
from app.services import staging_dispatch_preview_service as preview
from tools.staging_guard import assert_staging

STATE_NAMES = {
    'blocked': 'Bloqueado / aguardando teste',
    'leased': 'Capturado apenas em simulacao',
    'validated': 'Validacao logica concluida (SEM ENVIO)',
    'failed': 'Falha simulada',
    'dead_letter': 'Esgotou tentativas simuladas',
    'cancelled': 'Cancelado',
}
ACTIONS = {'lease', 'validate_no_send', 'fail', 'expire', 'retry', 'cancel'}


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f'{label} invalido.') from None


def require_clean_staging():
    assert_staging()
    status = preflight.readiness()
    if not status['real_queue_clean']:
        raise ValueError('STAGING contem registros nas filas reais. Operacao bloqueada.')
    return status


def list_contracts(limit: int = 40) -> list[dict]:
    require_clean_staging()
    rows = (get_admin_client().table('staging_transport_contracts')
        .select('id,opportunity_id,fingerprint,state,attempt_count,lock_version,lease_until,last_failure_code,created_at')
        .order('created_at', desc=True).limit(min(max(int(limit),1),60)).execute().data or [])
    result=[]
    for row in rows:
        opp = preview._get('opportunities',str(row['opportunity_id']))
        result.append({**row, 'reference': str(row['fingerprint'])[:16],
                       'title': (opp or {}).get('title') or 'Oportunidade indisponivel',
                       'state_label': STATE_NAMES.get(row.get('state'),'Estado desconhecido')})
    return result


def prepare_contract(*, opportunity_id: str, content: str, actor_id: str) -> dict:
    opp_id = _uuid(opportunity_id,'Oportunidade')
    actor = _uuid(actor_id,'Usuario')
    require_clean_staging()
    plan = preflight.make_plan(opportunity_id=opp_id,content=content,actor_id=actor)
    rendered = plan['rendered_message']
    # Mesmo algoritmo da H1-005B7. O banco recebe SOMENTE o hash completo.
    fingerprint = hashlib.sha256((opp_id+'\n'+rendered).encode('utf-8')).hexdigest()
    response = get_admin_client().rpc('vendra_staging_h1_005b8_prepare',{
        'p_opportunity_id':opp_id, 'p_fingerprint':fingerprint,'p_actor_id':actor}).execute()
    data = response.data
    if not isinstance(data,dict) or not data.get('id'):
        raise RuntimeError('Banco nao confirmou o contrato de homologacao.')
    return {'id':str(data['id']),'state':data.get('state'),
            'reference':fingerprint[:16], 'created':bool(data.get('created')),
            'phone_masked':plan['phone_masked'],'sent':False,'queued':False}


def change_contract(*, contract_id: str, action: str, lock_version: int, actor_id: str) -> dict:
    cid = _uuid(contract_id,'Contrato')
    actor = _uuid(actor_id,'Usuario')
    if action not in ACTIONS:
        raise ValueError('Acao invalida.')
    try:
        version = int(lock_version)
    except (TypeError, ValueError):
        raise ValueError('Versao invalida.') from None
    if version<1:
        raise ValueError('Versao invalida.')
    require_clean_staging()
    response=get_admin_client().rpc('vendra_staging_h1_005b8_transition',{
        'p_contract_id':cid,'p_action':action,
        'p_expected_version':version,'p_actor_id':actor}).execute()
    if not isinstance(response.data,dict) or not response.data.get('state'):
        raise RuntimeError('Transicao nao confirmada pelo banco.')
    return response.data


def read_events(contract_id: str, limit: int=20) -> list[dict]:
    require_clean_staging()
    return (get_admin_client().table('staging_transport_events')
            .select('action,old_state,new_state,version,created_at')
            .eq('contract_id',_uuid(contract_id,'Contrato'))
            .order('created_at',desc=True).limit(min(max(int(limit),1),50))
            .execute().data or [])
