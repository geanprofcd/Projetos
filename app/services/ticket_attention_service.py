"""Marcos temporais e SLA visual para atendimento ao lead.

Calcula a partir das mensagens persistidas: não depende de campo novo nem altera
histórico. Nunca trata nota interna como resposta ao cliente.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import logging

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.demo_store import DEMO_MESSAGES

# Em Windows, ZoneInfo precisa da base IANA que vem do pacote tzdata.
# O fallback abaixo impede que toda a aplicacao deixe de iniciar se o
# pacote ainda estiver ausente em uma instalacao local antiga.
try:
    LOCAL_TZ = ZoneInfo('America/Sao_Paulo')
except ZoneInfoNotFoundError:
    # Horario vigente em Sao Paulo: UTC-03; o fallback nao cobre
    # regras historicas de horario de verao. Instalar tzdata e obrigatorio.
    LOCAL_TZ = timezone(timedelta(hours=-3), name='America/Sao_Paulo (fallback)')
    logging.getLogger(__name__).warning(
        'Base de fuso horario indisponivel (America/Sao_Paulo). '
        'Usando UTC-03 temporariamente. Instale tzdata com pip.'
    )
ALERT_AFTER_SECONDS = 30 * 60
CLOSED_STATUSES = {'finalizado', 'cancelado'}


def parse_instant(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        instant = value
    else:
        try:
            instant = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(timezone.utc)


def date_br(value) -> str:
    # Campos SQL DATE não têm fuso horário: nunca deslocar para o dia anterior.
    if isinstance(value, str) and len(value) == 10 and value[4:5] == '-' and value[7:8] == '-':
        try:
            return datetime.strptime(value, '%Y-%m-%d').strftime('%d/%m/%Y')
        except ValueError:
            pass
    instant = parse_instant(value)
    return instant.astimezone(LOCAL_TZ).strftime('%d/%m/%Y') if instant else '—'


def time_br(value) -> str:
    instant = parse_instant(value)
    return instant.astimezone(LOCAL_TZ).strftime('%H:%M') if instant else '—'


def datetime_br(value) -> str:
    if not value:
        return '—'
    date_part = date_br(value)
    time_part = time_br(value)
    return f'{date_part} · {time_part}' if time_part != '—' else date_part


def _message_rows(ticket_ids: list[str]) -> dict[str, list[dict]]:
    result = {ticket_id: [] for ticket_id in ticket_ids}
    if not ticket_ids:
        return result
    if get_settings().demo_mode:
        for ticket_id in ticket_ids:
            result[ticket_id] = [m.copy() for m in DEMO_MESSAGES.get(ticket_id, [])]
        return result
    db = get_admin_client()
    # Paginação evita o limite implícito (geralmente 1000) do PostgREST.
    for begin in range(0, len(ticket_ids), 40):
        group = ticket_ids[begin:begin + 40]
        offset = 0
        while True:
            page = (
                db.table('messages')
                .select('id,ticket_id,created_at,direction,is_internal,delivery_status')
                .in_('ticket_id', group)
                .order('created_at')
                .range(offset, offset + 999)
                .execute().data or []
            )
            for item in page:
                key = str(item.get('ticket_id') or '')
                if key in result:
                    result[key].append(item)
            if len(page) < 1000:
                break
            offset += len(page)
    return result


def summarize_ticket(ticket: dict, messages: list[dict], *, now: datetime | None = None) -> dict:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    first_inbound = None
    last_external = None
    last_direction = None
    for row in sorted(messages, key=lambda x: (parse_instant(x.get('created_at')) or datetime.min.replace(tzinfo=timezone.utc), x.get('direction')=='inbound', str(x.get('id') or ''))):
        if row.get('is_internal'):
            continue
        direction = str(row.get('direction') or '').lower()
        moment = parse_instant(row.get('created_at'))
        if not moment or moment > now:
            continue
        if direction == 'inbound':
            if first_inbound is None:
                first_inbound = moment
            last_external = moment
            last_direction = 'inbound'
        elif direction == 'outbound' and row.get('delivery_status') not in ('failed','cancelled','pending'):
            last_external = moment
            last_direction = 'outbound'
    pending = (
        last_direction == 'inbound'
        and last_external is not None
        and (now - last_external).total_seconds() >= ALERT_AFTER_SECONDS
        and str(ticket.get('status') or '').lower() not in CLOSED_STATUSES
    )
    wait_minutes = max(0, int((now - last_external).total_seconds() // 60)) if pending else 0
    return {
        'arrival_date': date_br(ticket.get('created_at')),
        'first_reply_time': time_br(first_inbound),
        'first_reply_at': first_inbound.isoformat() if first_inbound else None,
        'last_activity_at': last_external.isoformat() if last_external else None,
        'last_direction': last_direction,
        'pending': bool(pending),
        'pending_since': last_external.isoformat() if pending else None,
        'pending_minutes': wait_minutes,
        # Define uma identidade diferente a cada nova mensagem pendente.
        'alert_key': f"{ticket.get('id')}:{last_external.isoformat()}" if pending else None,
    }


def summarize_tickets(tickets: list[dict], *, now: datetime | None = None) -> dict[str, dict]:
    if not tickets:
        return {}
    keys = [str(t['id']) for t in tickets if t.get('id') is not None]
    rows = _message_rows(keys)
    return {str(t['id']): summarize_ticket(t, rows.get(str(t['id']), []), now=now) for t in tickets}
