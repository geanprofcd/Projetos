from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.demo_store import DEMO_MESSAGES, DEMO_TICKETS

WINDOW_HOURS = 24


class WhatsAppTemplateRequiredError(ValueError):
    """Raised when a free-form WhatsApp send would violate the service window."""


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _format_remaining(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h {minutes:02d}min"
    return f"{minutes}min"


def _latest_demo_inbound(ticket_id: str) -> datetime | None:
    values: list[datetime] = []
    for message in DEMO_MESSAGES.get(str(ticket_id), []):
        if message.get("direction") != "inbound" or message.get("channel") != "whatsapp":
            continue
        parsed = _parse_dt(message.get("created_at"))
        if parsed:
            values.append(parsed)
    return max(values) if values else None


def _latest_real_inbound(ticket_id: str) -> datetime | None:
    rows = (
        get_admin_client()
        .table("messages")
        .select("created_at")
        .eq("ticket_id", ticket_id)
        .eq("channel", "whatsapp")
        .eq("direction", "inbound")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    return _parse_dt(rows[0].get("created_at")) if rows else None


def get_whatsapp_service_window(ticket_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Derive the 24h WhatsApp customer-service window from persisted inbound messages.

    This intentionally does not use ``whatsapp_active_at`` because outbound/template
    activity must never reopen the free-form customer-service window.
    """
    current = now or _now_dt()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    if get_settings().demo_mode:
        ticket = next((row for row in DEMO_TICKETS if str(row.get("id")) == str(ticket_id)), None)
        if not ticket or ticket.get("source") != "whatsapp":
            return {
                "applicable": False,
                "open": False,
                "state": "not_whatsapp",
                "send_mode": "not_applicable",
                "template_required": False,
                "last_customer_message_at": None,
                "expires_at": None,
                "remaining_seconds": 0,
                "remaining_label": "—",
            }
        latest = _latest_demo_inbound(ticket_id)
    else:
        rows = get_admin_client().table("tickets").select("id,source").eq("id", ticket_id).limit(1).execute().data or []
        if not rows or rows[0].get("source") != "whatsapp":
            return {
                "applicable": False,
                "open": False,
                "state": "not_whatsapp",
                "send_mode": "not_applicable",
                "template_required": False,
                "last_customer_message_at": None,
                "expires_at": None,
                "remaining_seconds": 0,
                "remaining_label": "—",
            }
        latest = _latest_real_inbound(ticket_id)

    expires = latest + timedelta(hours=WINDOW_HOURS) if latest else None
    is_open = bool(expires and current < expires)
    remaining = int((expires - current).total_seconds()) if is_open and expires else 0
    return {
        "applicable": True,
        "open": is_open,
        "state": "open" if is_open else "closed",
        "send_mode": "freeform" if is_open else "template_required",
        "template_required": not is_open,
        "last_customer_message_at": latest.isoformat() if latest else None,
        "expires_at": expires.isoformat() if expires else None,
        "remaining_seconds": remaining,
        "remaining_label": _format_remaining(remaining) if is_open else "encerrada",
        "window_hours": WINDOW_HOURS,
    }


def require_freeform_window(ticket_id: str) -> dict[str, Any]:
    window = get_whatsapp_service_window(ticket_id)
    if window.get("applicable") and not window.get("open"):
        raise WhatsAppTemplateRequiredError(
            "A janela de 24 horas do WhatsApp está encerrada. Mensagem livre bloqueada; use um modelo aprovado em Disparos ou aguarde uma nova mensagem do cliente."
        )
    return window
