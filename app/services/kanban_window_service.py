"""Janelas limitadas no banco; nunca materializar todo o funil no backend."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.db.supabase import get_admin_client
from app.services.product_service import money_label
from app.services.ticket_attention_service import date_br, time_br, parse_instant

WINDOW_SIZE = 120


def parse_windows(value: dict, stage_ids: set[str]) -> dict[str, int]:
    if not isinstance(value, dict) or len(value) > 100:
        raise ValueError('Janelas do funil inválidas.')
    result = {}
    for key, offset in value.items():
        if str(key) not in stage_ids or type(offset) not in (int, str):
            raise ValueError('Etapa ou posição inválida.')
        try:
            offset = int(offset)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError('Posição inválida.') from exc
        if offset < 0 or offset > 99_999_999:
            raise ValueError('Posição inválida.')
        result[str(key)] = offset
    return result


def list_kanban_windows(funnel: dict, *, search=None, assigned_user_id=None, windows=None) -> list[dict]:
    stages = [s for s in funnel.get('stages', []) if s.get('is_active', True)]
    positions = parse_windows(windows or {}, {str(s['id']) for s in stages})
    if assigned_user_id:
        UUID(str(assigned_user_id))
    result = get_admin_client().rpc('vendra_kanban_window_v1', {
        'p_funnel_id': str(funnel['id']), 'p_search': search or None,
        'p_assigned_user_id': assigned_user_id or None,
        'p_windows': positions, 'p_limit': WINDOW_SIZE,
    }).execute().data or []
    by_stage = {str(row['stage_id']): row for row in result}
    now = datetime.now(timezone.utc)
    columns = []
    for stage in stages:
        data = by_stage.get(str(stage['id']), {})
        cards = data.get('cards') or []
        if len(cards) > WINDOW_SIZE:
            raise ValueError('O banco retornou uma janela acima do limite.')
        for item in cards:
            item['calculated_value_label'] = money_label(item.get('calculated_value'))
            item['arrival_date'] = date_br(item.get('ticket_created_at') or item.get('created_at'))
            item['first_reply_time'] = time_br(item.get('first_reply_at'))
            activity = parse_instant(item.get('last_activity_at'))
            item['pending'] = bool(item.get('last_direction') == 'inbound' and activity
                and (now-activity).total_seconds() >= 1800
                and item.get('ticket_status') not in ('finalizado','cancelado'))
        columns.append({'stage': stage, 'cards': cards,
            'count': int(data.get('count') or 0), 'offset': int(data.get('offset') or 0),
            'windowed': True, 'total_label': money_label(data.get('total') or 0)})
    return columns
