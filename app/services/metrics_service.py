from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.demo_store import DEMO_MESSAGES, DEMO_TICKETS
from app.services.ticket_service import list_tickets


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = max(0.0, seconds)
    if seconds < 3600:
        minutes = max(1, round(seconds / 60))
        return f"{minutes} min"
    hours = seconds / 3600
    if hours < 24:
        return f"{hours:.1f} h".replace(".0", "")
    days = hours / 24
    return f"{days:.1f} d".replace(".0", "")


def service_metrics(user: dict, ticket_limit: int = 200) -> dict:
    tickets = list_tickets(user, limit=ticket_limit)
    if not tickets:
        return {
            "first_response_seconds": None,
            "first_response_label": "—",
            "first_response_samples": 0,
            "resolution_seconds": None,
            "resolution_label": "—",
            "resolution_samples": 0,
        }

    ticket_ids = {str(row["id"]) for row in tickets}
    messages_by_ticket: dict[str, list[dict]] = {ticket_id: [] for ticket_id in ticket_ids}

    if get_settings().demo_mode:
        for ticket_id in ticket_ids:
            messages_by_ticket[ticket_id] = [row.copy() for row in DEMO_MESSAGES.get(ticket_id, [])]
    else:
        rows = (
            get_admin_client()
            .table("messages")
            .select("id,ticket_id,direction,is_internal,created_at")
            .in_("ticket_id", list(ticket_ids))
            .order("created_at")
            .execute()
            .data
            or []
        )
        for row in rows:
            messages_by_ticket.setdefault(str(row["ticket_id"]), []).append(row)

    first_responses: list[float] = []
    resolutions: list[float] = []

    for ticket in tickets:
        created_at = _parse(ticket.get("created_at"))
        if not created_at:
            continue
        rows = sorted(messages_by_ticket.get(str(ticket["id"]), []), key=lambda row: row.get("created_at") or "")
        inbound_at = next((_parse(row.get("created_at")) for row in rows if row.get("direction") == "inbound" and not row.get("is_internal")), None)
        base = inbound_at or created_at
        outbound_at = next(
            (
                _parse(row.get("created_at"))
                for row in rows
                if row.get("direction") == "outbound" and not row.get("is_internal") and _parse(row.get("created_at")) and _parse(row.get("created_at")) >= base
            ),
            None,
        )
        if outbound_at:
            first_responses.append((outbound_at - base).total_seconds())

        closed_at = _parse(ticket.get("closed_at"))
        if closed_at and closed_at >= created_at:
            resolutions.append((closed_at - created_at).total_seconds())

    first_avg = sum(first_responses) / len(first_responses) if first_responses else None
    resolution_avg = sum(resolutions) / len(resolutions) if resolutions else None
    return {
        "first_response_seconds": first_avg,
        "first_response_label": _format_duration(first_avg),
        "first_response_samples": len(first_responses),
        "resolution_seconds": resolution_avg,
        "resolution_label": _format_duration(resolution_avg),
        "resolution_samples": len(resolutions),
    }
