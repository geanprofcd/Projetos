"""Fluxo de SIMULACAO H1-005B6.

Nao cria entradas em dispatches, messages, whatsapp_outbox nem faz requisicoes externas.
Somente: leitura de CRM/Clientes, RPCs de staging e audit_log via RPCs.
"""
from __future__ import annotations
import hashlib
from uuid import UUID
from app.db.supabase import get_admin_client
from app.services import staging_dispatch_preview_service as preview

STATES = {'prepared':'Preparado', 'simulated':'Simulado (sem envio)',
          'failed':'Falha simulada', 'cancelled':'Cancelado'}
ACTIONS = {'simulate_success', 'simulate_failure', 'retry', 'cancel'}


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise ValueError(f'{label} inválido.') from None


def list_simulations() -> list[dict]:
    db = get_admin_client()
    rows = (db.table('staging_dispatch_simulations')
            .select('id,opportunity_id,state,attempt_count,lock_version,created_at')
            .order('created_at',desc=True).limit(60).execute().data or [])
    result=[]
    for item in rows:
        opp=preview._get('opportunities',str(item['opportunity_id']))
        result.append({**item,
                       'title': (opp or {}).get('title') or 'Oportunidade indisponível',
                       'state_label':STATES.get(item.get('state'),'Indefinido')})
    return result


def prepare_simulation(*, opportunity_id: str, content: str, actor_id: str) -> dict:
    opp_id=_uuid(opportunity_id,'Oportunidade')
    actor_id=_uuid(actor_id,'Usuário')
    opp=preview._get('opportunities',opp_id)
    if not opp or opp.get('status')!='open' or opp.get('archived_at') is not None:
        raise ValueError('Selecione uma oportunidade aberta.')
    customer=preview._get('customers',str(opp.get('customer_id')))
    if not customer or customer.get('status')!='active':
        raise ValueError('O cliente precisa estar ativo.')
    valid,masked=preview._phone_mask(customer.get('phone_normalized') or customer.get('phone'))
    if not valid:
        raise ValueError('O cliente precisa ter um telefone de teste válido (10 a 15 dígitos).')
    funnel=preview._get('sales_funnels',str(opp.get('funnel_id')))
    stage=preview._get('funnel_stages',str(opp.get('stage_id')))
    if not funnel or not stage or str(stage.get('funnel_id')) != str(funnel.get('id')):
        raise ValueError('Funil ou etapa inconsistente.')
    vals={'name':str(customer.get('name') or ''),
          'company_name':str(customer.get('company_name') or ''),
          'opportunity_title':str(opp.get('title') or ''),
          'funnel_name':str(funnel.get('name') or ''),
          'stage_name':str(stage.get('name') or '')}
    rendered=preview._render(content or '',vals)
    fingerprint=hashlib.sha256(rendered.encode('utf-8')).hexdigest()
    response=get_admin_client().rpc('vendra_staging_prepare_dispatch',{
        'p_opportunity_id':opp_id,'p_fingerprint':fingerprint,'p_actor_id':actor_id}).execute()
    if response.data is None:
        raise RuntimeError('Banco não confirmou o preparo da simulação.')
    return {'id':str(response.data),'message':rendered,
            'phone_masked':masked,'title':vals['opportunity_title'],
            'sent':False,'queued':False}


def change_state(*, simulation_id: str, action: str, lock_version: int, actor_id: str) -> int:
    simulation_id=_uuid(simulation_id,'Simulação')
    actor_id=_uuid(actor_id,'Usuário')
    if action not in ACTIONS:
        raise ValueError('Ação inválida.')
    try:
        version=int(lock_version)
    except (ValueError, TypeError):
        raise ValueError('Atualize a página antes de alterar a simulação.') from None
    if version<1:
        raise ValueError('Versão inválida.')
    response=get_admin_client().rpc('vendra_staging_change_dispatch_simulation',{
        'p_simulation_id':simulation_id,'p_action':action,
        'p_expected_version':version,'p_actor_id':actor_id}).execute()
    if response.data is None:
        raise RuntimeError('O banco não confirmou a alteração.')
    return int(response.data)
