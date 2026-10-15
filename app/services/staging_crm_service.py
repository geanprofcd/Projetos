"""CRM H1-005B4: escritas exclusivamente via RPCs atomicas no Supabase-STAGING.

Nenhum envio externo ou alteracao no projeto principal.
"""
from __future__ import annotations
from uuid import UUID

from app.db.supabase import get_admin_client
from app.services.staging_attendance_service import list_crm_overview, list_internal_tickets


def _uuid(value: str, name: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise ValueError(f'{name} inválido.') from None


def list_crm():
    funnels, opportunities = list_crm_overview()
    return funnels, opportunities, list_internal_tickets(limit=100)


def _rpc(method: str, args: dict):
    result = get_admin_client().rpc(method, args).execute()
    if result.data is None:
        raise RuntimeError('O banco não confirmou a operação. Atualize a página.')
    return result.data


def create_funnel(*, name: str, stages_text: str, actor_id: str) -> str:
    name = (name or '').strip()
    stages = [v.strip() for v in (stages_text or '').splitlines() if v.strip()]
    if not 1 <= len(name) <= 120:
        raise ValueError('Informe um nome de funil com até 120 caracteres.')
    if not 2 <= len(stages) <= 12 or any(len(v)>120 for v in stages) or len({v.casefold() for v in stages}) != len(stages):
        raise ValueError('Informe entre 2 e 12 etapas diferentes, uma por linha.')
    return str(_rpc('vendra_staging_create_funnel', {
        'p_name': name, 'p_stage_names': stages, 'p_actor_id': _uuid(actor_id, 'Usuário')}))


def create_opportunity(*, ticket_id: str, stage_id: str, title: str, actor_id: str) -> str:
    title=(title or '').strip()
    if not 1 <= len(title) <= 180:
        raise ValueError('Informe um título com até 180 caracteres.')
    return str(_rpc('vendra_staging_create_opportunity', {
        'p_ticket_id': _uuid(ticket_id,'Atendimento'),
        'p_stage_id': _uuid(stage_id,'Etapa'),
        'p_title': title,
        'p_actor_id': _uuid(actor_id,'Usuário')}))


def move_opportunity(*, opportunity_id: str, stage_id: str, lock_version: int, actor_id: str) -> int:
    try: lock_version = int(lock_version)
    except (ValueError, TypeError):raise ValueError('Atualize a página e tente novamente.') from None
    if lock_version < 1:raise ValueError('Versão inválida. Atualize a página.')
    return int(_rpc('vendra_staging_move_opportunity', {
        'p_opportunity_id': _uuid(opportunity_id,'Oportunidade'),
        'p_to_stage_id': _uuid(stage_id,'Etapa'),
        'p_expected_lock_version': lock_version,
        'p_actor_id': _uuid(actor_id,'Usuário')}))
