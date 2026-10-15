"""H1-005B7: preflight estritamente read-only para futura integracao WhatsApp.

NAO usa dispatches/outbox como fila, NAO aciona RPC claim, webhooks, HTTP externos
nem grava qualquer dado. Plano efemero entregue exclusivamente ao navegador.
"""
from __future__ import annotations

import hashlib
from uuid import UUID

from app.db.supabase import get_admin_client
from app.services import staging_dispatch_preview_service as preview
from tools.staging_guard import assert_staging

REAL_TABLES = ('dispatches', 'whatsapp_outbox', 'messages')
OBSERVED_TABLES = (*REAL_TABLES, 'staging_dispatch_simulations')


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (AttributeError, TypeError, ValueError):
        raise ValueError(f'{label} inválido.') from None


def _count(db, name: str) -> int:
    """Conta linhas com COUNT exato sem descarregar PII nem detalhes de registros."""
    if name not in OBSERVED_TABLES:
        raise ValueError('Consulta de tabela nao permitida.')
    response = db.table(name).select('id', count='exact').limit(1).execute()
    count = getattr(response, 'count', None)
    if not isinstance(count, int) or count < 0:
        raise RuntimeError(f'Contagem de {name} indisponível; bloquear prontidão.')
    return count


def readiness() -> dict:
    """Checagem fail-closed; sem expor configuracoes sensiveis no navegador."""
    assert_staging()
    db = get_admin_client()
    counts = {name: _count(db, name) for name in OBSERVED_TABLES}
    clean = all(counts[name] == 0 for name in REAL_TABLES)
    return {
        'counts': counts,
        'real_queue_clean': clean,
        'environment': 'VENDRA-STAGING',
        'external_sends_enabled': False,
        'worker_enabled': False,
        'dry_run': True,
        'approved_template_verified': False,
        'opt_in_verified': False,
        'ready_to_send': False,  # envio real nunca autorizado nesta fase
    }


def make_plan(*, opportunity_id: str, content: str, actor_id: str) -> dict:
    """Valida pedido e monta envelope DRY-RUN sem nenhuma persistencia."""
    assert_staging()
    opportunity_id = _uuid(opportunity_id, 'Oportunidade')
    _uuid(actor_id, 'Usuário')
    # Se aparecer qualquer entrada na fila real, bloqueamos o preflight.
    status = readiness()
    if not status['real_queue_clean']:
        raise ValueError('Foram encontrados registros de envio real no STAGING. Investigação necessária.')
    opp = preview._get('opportunities', opportunity_id)
    if not opp or opp.get('status') != 'open' or opp.get('archived_at') is not None:
        raise ValueError('A oportunidade precisa estar aberta.')
    customer = preview._get('customers', str(opp.get('customer_id')))
    if not customer or customer.get('status') != 'active':
        raise ValueError('O cliente precisa estar ativo.')
    ok, masked = preview._phone_mask(customer.get('phone_normalized') or customer.get('phone'))
    if not ok:
        raise ValueError('Telefone inválido para o teste (10 a 15 dígitos).')
    funnel = preview._get('sales_funnels', str(opp.get('funnel_id')))
    stage = preview._get('funnel_stages', str(opp.get('stage_id')))
    if not funnel or not stage or str(stage.get('funnel_id')) != str(funnel.get('id')):
        raise ValueError('Etapa não pertence ao funil da oportunidade.')
    values = {
        'name': str(customer.get('name') or ''),
        'company_name': str(customer.get('company_name') or ''),
        'opportunity_title': str(opp.get('title') or ''),
        'funnel_name': str(funnel.get('name') or ''),
        'stage_name': str(stage.get('name') or ''),
    }
    rendered = preview._render(content or '', values)
    # Referencia deterministica apenas para comparacao; NAO e chave de envio aceita pelo provedor.
    fingerprint = hashlib.sha256((opportunity_id + '\n' + rendered).encode('utf-8')).hexdigest()
    return {
        'opportunity_title': values['opportunity_title'],
        'customer_name': values['name'],
        'phone_masked': masked,
        'rendered_message': rendered,
        'idempotency_reference': fingerprint[:16],
        'message_length': len(rendered),
        'destination': 'BLOQUEADO (nenhuma requisicao externa)',
        'transport': 'disabled',
        'delivery_state': 'not_queued',
        'queued': False,
        'sent': False,
        'persisted': False,
        'template_approval': 'nao_verificada',
        'opt_in': 'nao_verificado',
    }
