"""Previa segura de disparo H1-005B5. NUNCA faz envios nem enfileira mensagens.

A unica escrita permitida e uma entrada de auditoria com metadados minimos:
sem telefone, corpo do texto, credenciais ou IDs externos do WhatsApp.
"""
from __future__ import annotations

import hashlib
import re
from uuid import UUID

from app.db.supabase import get_admin_client


ALLOWED_VARIABLES = {
    'nome': 'name',
    'empresa': 'company_name',
    'oportunidade': 'opportunity_title',
    'funil': 'funnel_name',
    'etapa': 'stage_name',
}


def _valid_uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise ValueError(f'{label} inválido.') from None


def _get(table: str, row_id: str) -> dict | None:
    db = get_admin_client()
    rows = db.table(table).select('*').eq('id', row_id).limit(1).execute().data or []
    return rows[0] if rows else None


def _phone_mask(raw: str | None) -> tuple[bool, str]:
    digits = re.sub(r'\D', '', raw or '')
    return 10 <= len(digits) <= 15, ('•••• ' + digits[-4:]) if digits else 'Não informado'


def list_dispatch_candidates() -> list[dict]:
    db = get_admin_client()
    rows = (db.table('opportunities').select('id,title,customer_id,funnel_id,stage_id,status,archived_at')
            .order('created_at', desc=True).limit(100).execute().data or [])
    options = []
    # A versao de homologacao prefere consultas pequenas a joins amplos.
    for o in rows:
        if o.get('status') != 'open' or o.get('archived_at') is not None:
            continue
        c = _get('customers', str(o['customer_id']))
        if not c or c.get('status') != 'active':
            continue
        options.append({'id': str(o['id']), 'title': o.get('title') or 'Oportunidade',
                        'customer_name': c.get('name') or 'Cliente'})
    return options


def _render(text: str, values: dict[str, str]) -> str:
    if not 1 <= len(text.strip()) <= 1024:
        raise ValueError('A mensagem precisa conter de 1 a 1.024 caracteres.')
    # Aceita somente as variaveis documentadas; nunca executa codigo ou expressoes.
    raw = text.strip()
    tokens = re.findall(r'{{\s*([^{}]+?)\s*}}', raw)
    if any(t not in ALLOWED_VARIABLES for t in tokens):
        raise ValueError('Variável desconhecida. Use apenas as opções exibidas no formulário.')
    if '{{' in re.sub(r'{{\s*[^{}]+?\s*}}', '', raw) or '}}' in re.sub(r'{{\s*[^{}]+?\s*}}', '', raw):
        raise ValueError('Variável incompleta na mensagem.')
    for token in set(tokens):
        raw = re.sub(r'{{\s*' + re.escape(token) + r'\s*}}',
                     lambda _match: values.get(ALLOWED_VARIABLES[token], ''), raw)
    if not raw.strip() or len(raw)>2048:
        raise ValueError('A mensagem resultante é inválida.')
    return raw


def simulate_dispatch(*, opportunity_id: str, content: str, actor_id: str) -> dict:
    opp_id = _valid_uuid(opportunity_id, 'Oportunidade')
    actor_id = _valid_uuid(actor_id, 'Usuário')
    opp = _get('opportunities', opp_id)
    if not opp or opp.get('status') != 'open' or opp.get('archived_at') is not None:
        raise ValueError('Selecione uma oportunidade aberta.')
    customer = _get('customers', str(opp.get('customer_id')))
    if not customer or customer.get('status') != 'active':
        raise ValueError('O cliente dessa oportunidade não está ativo.')
    phone = customer.get('phone_normalized') or customer.get('phone') or ''
    valid_phone, masked_phone = _phone_mask(phone)
    if not valid_phone:
        raise ValueError('Cadastre um telefone de teste válido (10 a 15 dígitos) no cliente.')
    funnel = _get('sales_funnels', str(opp.get('funnel_id')))
    stage = _get('funnel_stages', str(opp.get('stage_id')))
    if not funnel or not stage or str(stage.get('funnel_id')) != str(funnel.get('id')):
        raise ValueError('Funil ou etapa inconsistente. Atualize a página.')
    values = {'name': str(customer.get('name') or ''),
              'company_name': str(customer.get('company_name') or ''),
              'opportunity_title': str(opp.get('title') or ''),
              'funnel_name': str(funnel.get('name') or ''),
              'stage_name': str(stage.get('name') or '')}
    result = _render(content or '', values)
    # Registro de auditoria sem corpo de mensagem e sem dados pessoais.
    fingerprint = hashlib.sha256(result.encode('utf-8')).hexdigest()[:16]
    audit = {'actor_id': actor_id, 'entity_type': 'dispatch_preview',
             'entity_id': opp_id, 'action': 'simulated',
             'payload': {'stage': 'H1-005B5', 'fingerprint': fingerprint,
                         'delivered': False, 'queued': False}}
    data = get_admin_client().table('audit_log').insert(audit).execute().data or []
    if not data:
        raise RuntimeError('Falha ao registrar a simulação na auditoria.')
    return {'opportunity_title': values['opportunity_title'],
            'customer_name': values['name'], 'phone_masked': masked_phone,
            'message': result, 'fingerprint': fingerprint,
            'sent': False, 'queued': False}
