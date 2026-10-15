from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import get_settings
from app.services.admin_settings_service import get_whatsapp_settings, list_webhooks
from app.db.supabase import get_admin_client
from app.services.attachment_service import get_attachment, list_attachments_for_messages
from app.services.customer_service import get_customer, normalize_phone
from app.services.outbox_wake_service import notify_make_outbox_async
from app.services.whatsapp_window_service import get_whatsapp_service_window, require_freeform_window
from app.services.demo_store import (
    DEMO_INTEGRATION_EVENTS,
    DEMO_MESSAGES,
    DEMO_TICKETS,
    DEMO_WHATSAPP_OUTBOX,
    new_id,
)

OUTBOX_STATUSES = {"pending", "claimed", "sent", "delivered", "read", "failed", "cancelled"}
FINAL_DELIVERY_STATUSES = {"delivered", "read", "cancelled"}


_DELIVERY_RANK = {"pending": 0, "claimed": 1, "sent": 2, "delivered": 3, "read": 4}

def _should_apply_delivery_status(current: str | None, incoming: str) -> bool:
    current = (current or "pending").lower()
    if current in {"read", "cancelled"}:
        return False
    if incoming == "cancelled":
        return current not in {"delivered", "read"}
    if incoming == "failed":
        return current not in {"delivered", "read"}
    if current == "failed":
        return incoming in {"sent", "delivered", "read"}
    if current == "cancelled":
        return False
    return _DELIVERY_RANK.get(incoming, -1) > _DELIVERY_RANK.get(current, -1)


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def queue_whatsapp_outbound(*, ticket_id: str, message_id: str) -> dict | None:
    """Create one durable outbound job for a non-internal reply to a WhatsApp ticket."""
    settings = get_settings()

    if settings.demo_mode:
        ticket = next((row for row in DEMO_TICKETS if str(row.get("id")) == str(ticket_id)), None)
        message = next((row for row in DEMO_MESSAGES.get(str(ticket_id), []) if str(row.get("id")) == str(message_id)), None)
        if not ticket or not message or ticket.get("source") != "whatsapp" or message.get("is_internal"):
            return None
        require_freeform_window(str(ticket_id))
        existing = next((row for row in DEMO_WHATSAPP_OUTBOX if str(row.get("message_id")) == str(message_id)), None)
        if existing:
            return existing.copy()
        customer = get_customer(str(ticket.get("customer_id")))
        phone = normalize_phone(customer.get("phone") if customer else None)
        if not phone:
            raise ValueError("O cliente deste atendimento não possui telefone válido para envio pelo WhatsApp.")
        row = {
            "id": new_id("outbox"),
            "ticket_id": str(ticket_id),
            "message_id": str(message_id),
            "customer_id": str(ticket.get("customer_id")),
            "phone": phone,
            "body": message.get("body") or "",
            "status": "pending",
            "attempt_count": 0,
            "claimed_at": None,
            "claimed_by": None,
            "provider_message_id": None,
            "last_error": None,
            "created_at": _now(),
            "updated_at": _now(),
        }
        DEMO_WHATSAPP_OUTBOX.append(row)
        message["delivery_status"] = "pending"
        ticket["whatsapp_active_at"] = _now()
        ticket["updated_at"] = _now()
        notify_make_outbox_async(row)
        return row.copy()

    admin = get_admin_client()
    ticket_rows = admin.table("tickets").select("id,customer_id,source").eq("id", ticket_id).limit(1).execute().data or []
    if not ticket_rows or ticket_rows[0].get("source") != "whatsapp":
        return None
    message_rows = admin.table("messages").select("id,body,is_internal,direction").eq("id", message_id).eq("ticket_id", ticket_id).limit(1).execute().data or []
    if not message_rows or message_rows[0].get("is_internal") or message_rows[0].get("direction") != "outbound":
        return None
    require_freeform_window(str(ticket_id))
    existing = admin.table("whatsapp_outbox").select("*").eq("message_id", message_id).limit(1).execute().data or []
    if existing:
        return existing[0]
    customer = get_customer(str(ticket_rows[0].get("customer_id")))
    phone = normalize_phone(customer.get("phone") if customer else None)
    if not phone:
        raise ValueError("O cliente deste atendimento não possui telefone válido para envio pelo WhatsApp.")
    row = admin.table("whatsapp_outbox").insert(
        {
            "ticket_id": ticket_id,
            "message_id": message_id,
            "customer_id": ticket_rows[0]["customer_id"],
            "phone": phone,
            "body": message_rows[0].get("body") or "",
            "status": "pending",
        }
    ).execute().data[0]
    admin.table("messages").update({"delivery_status": "pending", "external_status_updated_at": _now()}).eq("id", message_id).execute()
    notify_make_outbox_async(row)
    return row


def _eligible_demo_outbox() -> list[dict]:
    ttl = timedelta(seconds=max(30, get_settings().integration_claim_ttl_seconds))
    cutoff = _now_dt() - ttl
    rows = []
    for row in DEMO_WHATSAPP_OUTBOX:
        if row.get("status") == "pending":
            rows.append(row)
            continue
        if row.get("status") == "claimed":
            claimed_at = _parse_dt(row.get("claimed_at"))
            if not claimed_at or claimed_at < cutoff:
                rows.append(row)
    return rows


def claim_whatsapp_outbox(*, limit: int = 10, worker_id: str | None = None) -> list[dict]:
    limit = min(max(int(limit), 1), 50)
    worker = (worker_id or get_settings().make_worker_name or "make-whatsapp")[:120]
    settings = get_settings()
    if settings.demo_mode:
        rows = sorted(_eligible_demo_outbox(), key=lambda row: row.get("created_at") or "")[:limit]
        claimed = []
        for row in rows:
            row.update(
                {
                    "status": "claimed",
                    "claimed_at": _now(),
                    "claimed_by": worker,
                    "attempt_count": int(row.get("attempt_count") or 0) + 1,
                    "updated_at": _now(),
                    "last_error": None,
                }
            )
            claimed.append(_outbox_payload(row))
        return claimed

    response = get_admin_client().rpc(
        "claim_whatsapp_outbox",
        {
            "p_limit": limit,
            "p_claimed_by": worker,
            "p_claim_ttl_seconds": max(30, settings.integration_claim_ttl_seconds),
        },
    ).execute()
    return [_outbox_payload(row) for row in (response.data or [])]


def _outbox_payload(row: dict) -> dict:
    message_id = str(row.get("message_id") or "")
    ticket_id = str(row.get("ticket_id") or "")
    attachments = list_attachments_for_messages([message_id]).get(message_id, []) if message_id else []
    window = get_whatsapp_service_window(ticket_id) if ticket_id else {"applicable": False, "open": False, "send_mode": "not_applicable", "template_required": False}
    return {
        "id": str(row.get("id")),
        "ticket_id": ticket_id,
        "message_id": message_id,
        "phone": row.get("phone"),
        "body": row.get("body") or "",
        "status": row.get("status"),
        "attempt_count": int(row.get("attempt_count") or 0),
        "delivery_policy": {
            "send_mode": window.get("send_mode"),
            "window_open": bool(window.get("open")),
            "template_required": bool(window.get("template_required")),
            "last_customer_message_at": window.get("last_customer_message_at"),
            "window_expires_at": window.get("expires_at"),
            "remaining_seconds": int(window.get("remaining_seconds") or 0),
            "authorized_to_send": bool(window.get("open")) or not bool(window.get("applicable")),
        },
        "attachments": [
            {
                "id": str(item.get("id")),
                "file_name": item.get("file_name"),
                "mime_type": item.get("mime_type"),
                "size_bytes": item.get("size_bytes"),
                "download_path": f"/webhooks/make/whatsapp/outbox/{row.get('id')}/attachments/{item.get('id')}",
            }
            for item in attachments
        ],
    }


def reserve_whatsapp_outbox(outbox_id: str, *, worker_id: str = "make-ai-inline") -> dict:
    """Reserve a specific pending outbox item for immediate Make/Meta delivery.

    This avoids the generic outbox worker claiming the same item while the
    current Make scenario is sending the AI reply inline.
    """
    settings = get_settings()
    worker = str(worker_id or "make-ai-inline")[:120]
    if settings.demo_mode:
        row = next((row for row in DEMO_WHATSAPP_OUTBOX if str(row.get("id")) == str(outbox_id)), None)
        if not row:
            raise ValueError("Item de saída não encontrado.")
        require_freeform_window(str(row.get("ticket_id") or ""))
        if row.get("status") not in {"pending", "claimed"}:
            return _outbox_payload(row)
        row.update({
            "status": "claimed",
            "claimed_at": _now(),
            "claimed_by": worker,
            "attempt_count": int(row.get("attempt_count") or 0) + (0 if row.get("status") == "claimed" else 1),
            "updated_at": _now(),
            "last_error": None,
        })
        return _outbox_payload(row)

    admin = get_admin_client()
    rows = admin.table("whatsapp_outbox").select("*").eq("id", outbox_id).limit(1).execute().data or []
    if not rows:
        raise ValueError("Item de saída não encontrado.")
    current = rows[0]
    require_freeform_window(str(current.get("ticket_id") or ""))
    if current.get("status") not in {"pending", "claimed"}:
        return _outbox_payload(current)
    payload = {
        "status": "claimed",
        "claimed_at": _now(),
        "claimed_by": worker,
        "attempt_count": int(current.get("attempt_count") or 0) + (0 if current.get("status") == "claimed" else 1),
        "updated_at": _now(),
        "last_error": None,
    }
    updated = admin.table("whatsapp_outbox").update(payload).eq("id", outbox_id).execute().data or []
    return _outbox_payload(updated[0] if updated else current)


def get_outbox_item(outbox_id: str) -> dict | None:
    if get_settings().demo_mode:
        row = next((row for row in DEMO_WHATSAPP_OUTBOX if str(row.get("id")) == str(outbox_id)), None)
        return row.copy() if row else None
    rows = get_admin_client().table("whatsapp_outbox").select("*").eq("id", outbox_id).limit(1).execute().data or []
    return rows[0] if rows else None


def get_outbox_attachment(outbox_id: str, attachment_id: str) -> dict | None:
    item = get_outbox_item(outbox_id)
    if not item:
        return None
    attachment = get_attachment(attachment_id)
    if not attachment or str(attachment.get("message_id")) != str(item.get("message_id")):
        return None
    return attachment


def update_outbox_status(*, outbox_id: str, status: str, provider_message_id: str | None = None, error_message: str | None = None, occurred_at: str | None = None) -> dict:
    status = status.strip().lower()
    if status not in OUTBOX_STATUSES - {"pending", "claimed"}:
        raise ValueError("Status de entrega inválido.")
    settings = get_settings()
    if settings.demo_mode:
        row = next((row for row in DEMO_WHATSAPP_OUTBOX if str(row.get("id")) == str(outbox_id)), None)
        if not row:
            raise ValueError("Item de saída não encontrado.")
        if not _should_apply_delivery_status(row.get("status"), status):
            result = row.copy()
            result["status_update_ignored"] = True
            return result
        row.update(
            {
                "status": status,
                "provider_message_id": provider_message_id or row.get("provider_message_id"),
                "last_error": (error_message or "")[:1000] or None,
                "updated_at": _now(),
            }
        )
        for message in DEMO_MESSAGES.get(str(row.get("ticket_id")), []):
            if str(message.get("id")) == str(row.get("message_id")):
                message["delivery_status"] = status
                message["external_message_id"] = provider_message_id or message.get("external_message_id")
                message["external_status_updated_at"] = occurred_at or _now()
                break
        return row.copy()

    admin = get_admin_client()
    rows = admin.table("whatsapp_outbox").select("*").eq("id", outbox_id).limit(1).execute().data or []
    if not rows:
        raise ValueError("Item de saída não encontrado.")
    current = rows[0]
    if not _should_apply_delivery_status(current.get("status"), status):
        result = current.copy()
        result["status_update_ignored"] = True
        return result
    update = {
        "status": status,
        "provider_message_id": provider_message_id or current.get("provider_message_id"),
        "last_error": (error_message or "")[:1000] or None,
        "updated_at": _now(),
    }
    result = admin.table("whatsapp_outbox").update(update).eq("id", outbox_id).execute().data[0]
    message_update: dict[str, Any] = {"delivery_status": status, "external_status_updated_at": occurred_at or _now()}
    if provider_message_id:
        message_update["external_message_id"] = provider_message_id
    admin.table("messages").update(message_update).eq("id", current["message_id"]).execute()
    return result


def get_outbox_by_provider_message_id(provider_message_id: str) -> dict | None:
    provider_message_id = str(provider_message_id or "").strip()
    if not provider_message_id:
        return None
    if get_settings().demo_mode:
        row = next((row for row in DEMO_WHATSAPP_OUTBOX if str(row.get("provider_message_id") or "") == provider_message_id), None)
        return row.copy() if row else None
    rows = (
        get_admin_client()
        .table("whatsapp_outbox")
        .select("*")
        .eq("provider_message_id", provider_message_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def update_outbox_status_by_provider_message_id(
    *,
    provider_message_id: str,
    status: str,
    error_message: str | None = None,
    occurred_at: str | None = None,
) -> dict:
    item = get_outbox_by_provider_message_id(provider_message_id)
    if not item:
        raise ValueError("Mensagem do provedor ainda não vinculada a uma saída do VENDRA.")
    return update_outbox_status(
        outbox_id=str(item.get("id")),
        status=status,
        provider_message_id=provider_message_id,
        error_message=error_message,
        occurred_at=occurred_at,
    )


def requeue_outbox(outbox_id: str) -> dict:
    settings = get_settings()
    if settings.demo_mode:
        row = next((row for row in DEMO_WHATSAPP_OUTBOX if str(row.get("id")) == str(outbox_id)), None)
        if not row:
            raise ValueError("Item de saída não encontrado.")
        if row.get("status") not in {"failed", "claimed"}:
            raise ValueError("Somente saídas com falha ou claim travado podem ser reenfileiradas com segurança.")
        if row.get("status") == "claimed":
            claimed_at = _parse_dt(row.get("claimed_at"))
            ttl = timedelta(seconds=max(30, settings.integration_claim_ttl_seconds))
            if claimed_at and claimed_at >= _now_dt() - ttl:
                raise ValueError("Este claim ainda está ativo; aguarde o TTL antes de reenfileirar para evitar envio duplicado.")
        row.update({"status": "pending", "claimed_at": None, "claimed_by": None, "last_error": None, "updated_at": _now()})
        return row.copy()

    admin = get_admin_client()
    rows = admin.table("whatsapp_outbox").select("*").eq("id", outbox_id).limit(1).execute().data or []
    if not rows:
        raise ValueError("Item de saída não encontrado.")
    if rows[0].get("status") not in {"failed", "claimed"}:
        raise ValueError("Somente saídas com falha ou claim travado podem ser reenfileiradas com segurança.")
    if rows[0].get("status") == "claimed":
        claimed_at = _parse_dt(rows[0].get("claimed_at"))
        ttl = timedelta(seconds=max(30, settings.integration_claim_ttl_seconds))
        if claimed_at and claimed_at >= _now_dt() - ttl:
            raise ValueError("Este claim ainda está ativo; aguarde o TTL antes de reenfileirar para evitar envio duplicado.")
    return admin.table("whatsapp_outbox").update(
        {"status": "pending", "claimed_at": None, "claimed_by": None, "last_error": None, "updated_at": _now()}
    ).eq("id", outbox_id).execute().data[0]


def list_recent_outbox(limit: int = 30) -> list[dict]:
    if get_settings().demo_mode:
        return [row.copy() for row in sorted(DEMO_WHATSAPP_OUTBOX, key=lambda row: row.get("created_at") or "", reverse=True)[:limit]]
    return get_admin_client().table("whatsapp_outbox").select("*").order("created_at", desc=True).limit(limit).execute().data or []


def list_recent_integration_events(limit: int = 30) -> list[dict]:
    if get_settings().demo_mode:
        rows = [dict(value, external_id=key) for key, value in DEMO_INTEGRATION_EVENTS.items()]
        rows.sort(key=lambda row: row.get("processed_at") or row.get("created_at") or "", reverse=True)
        return rows[:limit]
    return get_admin_client().table("integration_events").select("*").order("created_at", desc=True).limit(limit).execute().data or []


def integration_counts() -> dict:
    outbox = list_recent_outbox(500)
    return {
        "pending": sum(1 for row in outbox if row.get("status") in {"pending", "claimed"}),
        "failed": sum(1 for row in outbox if row.get("status") == "failed"),
        "sent": sum(1 for row in outbox if row.get("status") in {"sent", "delivered", "read"}),
    }



def whatsapp_homologation_status() -> dict:
    """Safe, non-secret checklist for the real WhatsApp/Make homologation."""
    settings = get_settings()
    try:
        channel = get_whatsapp_settings()
    except Exception:
        channel = {}
    try:
        hooks = list_webhooks()
    except Exception:
        hooks = []
    events = list_recent_integration_events(500)
    outbox = list_recent_outbox(500)

    active_whatsapp_hooks = [
        row for row in hooks if row.get("active") and row.get("kind") == "whatsapp_text"
    ]
    processed_events = [row for row in events if (row.get("status") or "processed") == "processed"]
    inbound_seen = any((row.get("event_type") or "message.inbound") == "message.inbound" for row in processed_events)
    outbound_claimed = any(row.get("status") in {"claimed", "sent", "delivered", "read", "failed", "cancelled"} for row in outbox)
    outbound_sent = any(row.get("status") in {"sent", "delivered", "read"} for row in outbox)
    callback_seen = any(row.get("status") in {"delivered", "read", "failed", "cancelled"} for row in outbox)

    channel_enabled = bool(channel.get("enabled"))
    phone_configured = bool(str(channel.get("display_phone_number") or "").strip())
    provider_ids = bool(str(channel.get("phone_number_id") or "").strip())
    webhook_ready = bool(active_whatsapp_hooks or settings.make_webhook_secret)

    steps = [
        {"key": "channel", "label": "Canal WhatsApp ativo", "ok": channel_enabled and phone_configured},
        {"key": "provider", "label": "ID do número/provedor informado", "ok": provider_ids},
        {"key": "webhook", "label": "Webhook WhatsApp autenticado ativo", "ok": webhook_ready},
        {"key": "inbound", "label": "Entrada de texto processada", "ok": inbound_seen},
        {"key": "outbound_claim", "label": "Outbox reclamada pelo worker", "ok": outbound_claimed},
        {"key": "outbound_sent", "label": "Envio externo confirmado", "ok": outbound_sent},
        {"key": "callbacks", "label": "Callback externo recebido", "ok": callback_seen},
    ]
    completed = sum(1 for step in steps if step["ok"])
    return {
        "provider_key": channel.get("provider_key") or "meta_cloud",
        "provider": channel.get("provider") or None,
        "steps": steps,
        "completed": completed,
        "total": len(steps),
        "ready_for_provider_test": channel_enabled and phone_configured and provider_ids and webhook_ready,
        "bridge_homologated": all(step["ok"] for step in steps),
        "mode": "demo" if settings.demo_mode else "real",
    }

def supabase_readiness() -> dict:
    """Non-secret readiness report. Does real connectivity checks only outside demo mode."""
    settings = get_settings()
    configured = settings.supabase_configured
    report = {
        "mode": "demo" if settings.demo_mode else "real",
        "configured": configured,
        "database": "not_checked",
        "storage": "not_checked",
        "make_secret": bool(settings.make_webhook_secret),
        "configured_webhooks": 0,
        "whatsapp_channel": False,
        "errors": [],
    }
    try:
        report["configured_webhooks"] = sum(1 for row in list_webhooks() if row.get("active"))
        report["whatsapp_channel"] = bool(get_whatsapp_settings().get("enabled"))
    except Exception as exc:
        report["errors"].append(f"Configurações administrativas: {str(exc)[:240]}")
    if settings.demo_mode:
        report["database"] = "demo"
        report["storage"] = "demo"
        return report
    if not configured:
        report["database"] = "missing_configuration"
        report["storage"] = "missing_configuration"
        return report

    try:
        admin = get_admin_client()
        for table in ("profiles", "customers", "farms", "tickets", "messages", "attachments", "integration_events", "whatsapp_outbox", "integration_settings", "configured_webhooks"):
            admin.table(table).select("*", count="exact").limit(1).execute()
        report["database"] = "ok"
    except Exception as exc:
        report["database"] = "error"
        report["errors"].append(f"Banco/migrations: {str(exc)[:240]}")

    try:
        buckets = get_admin_client().storage.list_buckets()
        names = {getattr(item, "name", None) or (item.get("name") if isinstance(item, dict) else None) for item in (buckets or [])}
        report["storage"] = "ok" if settings.attachment_bucket in names else "bucket_missing"
    except Exception as exc:
        report["storage"] = "error"
        report["errors"].append(f"Storage: {str(exc)[:240]}")
    return report
