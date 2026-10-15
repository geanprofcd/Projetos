"""Atendimentos internos STAGING: sem WhatsApp, disparos, outbox ou IA.

Somente as tabelas ja homologadas em H1-001/H1-004. Toda chamada real
usa a chave backend no servidor; NUNCA e entregue ao browser.
"""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from app.db.supabase import get_admin_client

STATUSES = ('novo','em_atendimento','aguardando_cliente','aguardando_interno','aguardando_orcamento','finalizado','cancelado')
PRIORITIES = ('baixa','normal','alta','urgente')


def _uuid(raw: str, label: str) -> str:
    try: return str(UUID(str(raw)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f'{label} inválido.') from None


def _one(table: str, row_id: str):
    rows = (get_admin_client().table(table).select('*').eq('id', row_id).limit(1).execute().data or [])
    return rows[0] if rows else None


def _name_map(table: str, ids: set[str], key: str) -> dict[str,str]:
    if not ids: return {}
    rows = get_admin_client().table(table).select(f'id,{key}').in_('id',list(ids)).execute().data or []
    return {str(row['id']):row.get(key) or '—' for row in rows}


def list_internal_tickets(*, limit: int = 100) -> list[dict]:
    rows = (get_admin_client().table('tickets').select('*').eq('source','interno')
            .order('created_at',desc=True).limit(min(max(limit,1),100)).execute().data or [])
    customers=_name_map('customers',{str(r['customer_id']) for r in rows},'name')
    assigned=_name_map('profiles',{str(r['assigned_user_id']) for r in rows if r.get('assigned_user_id')},'full_name')
    for row in rows:
        row['customer_name']=customers.get(str(row['customer_id']),'Cliente')
        row['assigned_name']=assigned.get(str(row.get('assigned_user_id')),'Sem responsável')
    return rows


def create_internal_ticket(*, actor_id: str, title: str, customer_id: str, priority: str='normal') -> dict:
    title=(title or '').strip()
    if not 1<=len(title)<=180: raise ValueError('Informe um assunto com até 180 caracteres.')
    if priority not in PRIORITIES: raise ValueError('Prioridade inválida.')
    customer_id=_uuid(customer_id, 'Cliente')
    actor_id=_uuid(actor_id,'Usuário')
    customer=_one('customers',customer_id)
    if not customer or customer.get('status')!='active':
        raise ValueError('Selecione um cliente ativo cadastrado no STAGING.')
    payload={'title':title,'customer_id':customer_id,'assigned_user_id':actor_id,
             'source':'interno','status':'novo','priority':priority}
    result=get_admin_client().table('tickets').insert(payload).execute().data or []
    if not result: raise RuntimeError('O banco não confirmou a criação do atendimento.')
    return result[0]


def get_internal_ticket(ticket_id:str) -> dict | None:
    row=_one('tickets',_uuid(ticket_id,'Atendimento'))
    if not row or row.get('source')!='interno': return None
    customer=_one('customers',str(row['customer_id']))
    row['customer_name']=(customer or {}).get('name') or 'Cliente'
    return row


def list_internal_notes(ticket_id:str, *, limit:int=100) -> list[dict]:
    rows=(get_admin_client().table('internal_notes').select('*')
          .eq('ticket_id',_uuid(ticket_id,'Atendimento'))
          .order('created_at',desc=False).limit(min(max(limit,1),100)).execute().data or [])
    names=_name_map('profiles',{str(r['user_id']) for r in rows if r.get('user_id')},'full_name')
    for r in rows:r['author_name']=names.get(str(r.get('user_id')),'Equipe')
    return rows


def add_internal_note(*, ticket_id:str, actor_id:str, content:str) -> dict:
    ticket_id=_uuid(ticket_id,'Atendimento'); actor_id=_uuid(actor_id,'Usuário')
    content=(content or '').strip()
    if not 1<=len(content)<=5000:raise ValueError('A nota deve conter de 1 a 5.000 caracteres.')
    ticket=get_internal_ticket(ticket_id)
    if not ticket:raise ValueError('Atendimento interno não encontrado.')
    if ticket['status'] in ('finalizado','cancelado'):
        raise ValueError('Não é possível adicionar notas a um atendimento encerrado.')
    row={'ticket_id':ticket_id,'user_id':actor_id,'content':content}
    result=get_admin_client().table('internal_notes').insert(row).execute().data or []
    if not result:raise RuntimeError('O banco não confirmou a gravação da nota.')
    return result[0]


def list_crm_overview() -> tuple[list[dict],list[dict]]:
    db=get_admin_client()
    funnels=db.table('sales_funnels').select('*').order('name').limit(50).execute().data or []
    stages=db.table('funnel_stages').select('*').order('position').limit(200).execute().data or []
    opps=db.table('opportunities').select('*').order('created_at',desc=True).limit(100).execute().data or []
    stage_map={str(r['id']):r for r in stages};funnel_map={str(r['id']):r for r in funnels}
    customer_map=_name_map('customers',{str(r['customer_id']) for r in opps},'name')
    for f in funnels:
        f['stages']=[s for s in stages if str(s['funnel_id'])==str(f['id'])]
    for o in opps:
        o['customer_name']=customer_map.get(str(o['customer_id']),'Cliente')
        o['funnel_name']=(funnel_map.get(str(o['funnel_id'])) or {}).get('name','—')
        o['stage_name']=(stage_map.get(str(o['stage_id'])) or {}).get('name','—')
    return funnels,opps
