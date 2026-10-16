"""Ordem comercial por mensagens externas, com recebidas pendentes primeiro."""
from datetime import datetime, timezone
from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.ticket_attention_service import summarize_tickets, parse_instant


def activity_key(row, summary):
    instant = parse_instant(summary.get('last_activity_at') or row.get('updated_at') or row.get('created_at'))
    return (summary.get('last_direction') == 'inbound',
            instant or datetime.min.replace(tzinfo=timezone.utc), str(row.get('id') or ''))


def list_ticket_rows(*, customer_ids=None, limit=100):
    if not get_settings().demo_mode:
        params={'p_limit':limit}
        if customer_ids is not None:
            from uuid import UUID
            params['p_customer_ids']='{'+','.join(str(UUID(str(value))) for value in customer_ids)+'}'
        return get_admin_client().rpc('vendra_ticket_activity_list_v1',params,get=True).execute().data or []
    from app.services.demo_store import DEMO_TICKETS
    rows=[row.copy() for row in DEMO_TICKETS if customer_ids is None or row.get('customer_id') in customer_ids]
    summaries=summarize_tickets(rows)
    rows.sort(key=lambda row:activity_key(row,summaries.get(str(row['id']),{})),reverse=True)
    return rows[:limit]
