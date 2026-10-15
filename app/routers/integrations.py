from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.attachment_service import (
    AttachmentError,
    delete_attachment,
    demo_file_path,
    prepare_attachment,
    save_attachment,
    signed_download_url,
)
from app.services.customer_service import create_customer, find_customer_by_phone, normalize_phone
from app.services.automation_service import ensure_ticket_ai_control, get_ticket_ai_control, persist_ai_reply
from app.services.ai_routing_service import apply_ai_route, normalize_route_code, route_contract
from app.services.dispatch_service import update_dispatch_status
from app.services.audit_service import record_audit
from app.services.demo_store import DEMO_INTEGRATION_EVENTS, DEMO_MESSAGES, DEMO_TICKETS, new_id
from app.services.admin_settings_service import mark_webhook_used, public_whatsapp_channel, validate_any_webhook_secret, validate_webhook
from app.services.whatsapp_window_service import get_whatsapp_service_window
from app.services.integration_service import (
    claim_whatsapp_outbox,
    get_outbox_attachment,
    update_outbox_status,
    update_outbox_status_by_provider_message_id,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WhatsAppInbound(BaseModel):
    phone: str = Field(min_length=8, max_length=30)
    name: str | None = None
    message: str = Field(min_length=1, max_length=10000)
    external_message_id: str | None = Field(default=None, max_length=500)
    # Mantido apenas por compatibilidade de contrato. O backend NÃO baixa URL arbitrária.
    media_url: str | None = None


class OutboxStatusUpdate(BaseModel):
    status: str = Field(min_length=3, max_length=30)
    provider_message_id: str | None = Field(default=None, max_length=500)
    error_message: str | None = Field(default=None, max_length=1000)


class ProviderStatusUpdate(BaseModel):
    provider_message_id: str = Field(min_length=1, max_length=500)
    status: str = Field(min_length=3, max_length=30)
    occurred_at: str | int | float | None = None
    recipient_id: str | None = Field(default=None, max_length=120)
    error_message: str | None = Field(default=None, max_length=1000)


class AIReplyInbound(BaseModel):
    ticket_id: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=10000)
    control_version: int = Field(ge=1)
    external_message_id: str | None = Field(default=None, max_length=500)
    route_code: str | None = Field(default=None, max_length=20)
    delivery_mode: str = Field(default="outbox", pattern="^(outbox|inline_make)$")


class DispatchStatusUpdate(BaseModel):
    status: str = Field(min_length=3, max_length=30)
    provider_message_id: str | None = Field(default=None, max_length=500)
    error_message: str | None = Field(default=None, max_length=1000)


def _hash_payload(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provider_status_time(value: str | int | float | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().replace(".", "", 1).isdigit()):
            numeric = float(value)
            if numeric > 10_000_000_000:
                numeric /= 1000.0
            return datetime.fromtimestamp(numeric, tz=timezone.utc).isoformat()
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _provider_status_event_id(provider_message_id: str, status_value: str) -> str:
    return f"provider-status:{provider_message_id}:{status_value}"[:500]


def _remember_provider_status_pending(*, external_id: str, payload: dict) -> None:
    settings = get_settings()
    if settings.demo_mode:
        existing = DEMO_INTEGRATION_EVENTS.get(external_id) or {}
        DEMO_INTEGRATION_EVENTS[external_id] = {
            **existing,
            "provider": "whatsapp",
            "event_type": "message.status",
            "status": "received",
            "payload": payload,
            "entity_type": None,
            "entity_id": None,
            "error_message": None,
            "created_at": existing.get("created_at") or _now(),
            "processed_at": None,
        }
        return
    admin = get_admin_client()
    existing = (
        admin.table("integration_events")
        .select("id,status")
        .eq("provider", "whatsapp")
        .eq("external_id", external_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    values = {
        "event_type": "message.status",
        "status": "received",
        "payload": payload,
        "entity_type": None,
        "entity_id": None,
        "error_message": None,
        "processed_at": None,
    }
    if existing:
        if existing[0].get("status") in {"processed", "ignored"}:
            return
        admin.table("integration_events").update(values).eq("id", existing[0]["id"]).execute()
    else:
        admin.table("integration_events").insert({"provider": "whatsapp", "external_id": external_id, **values}).execute()


def _finish_provider_status_event(*, external_id: str, item: dict, ignored: bool) -> None:
    final_status = "ignored" if ignored else "processed"
    settings = get_settings()
    if settings.demo_mode:
        event = DEMO_INTEGRATION_EVENTS.get(external_id) or {
            "provider": "whatsapp",
            "event_type": "message.status",
            "created_at": _now(),
        }
        event.update({
            "status": final_status,
            "entity_type": "whatsapp_outbox",
            "entity_id": str(item.get("id") or ""),
            "error_message": None,
            "processed_at": _now(),
        })
        DEMO_INTEGRATION_EVENTS[external_id] = event
        return
    admin = get_admin_client()
    rows = (
        admin.table("integration_events")
        .select("id")
        .eq("provider", "whatsapp")
        .eq("external_id", external_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    values = {
        "status": final_status,
        "entity_type": "whatsapp_outbox",
        "entity_id": str(item.get("id") or ""),
        "error_message": None,
        "processed_at": _now(),
    }
    if rows:
        admin.table("integration_events").update(values).eq("id", rows[0]["id"]).execute()


def _reconcile_pending_provider_statuses(provider_message_id: str) -> list[dict]:
    provider_message_id = str(provider_message_id or "").strip()
    if not provider_message_id:
        return []
    settings = get_settings()
    events: list[tuple[str, dict]] = []
    if settings.demo_mode:
        for external_id, event in DEMO_INTEGRATION_EVENTS.items():
            payload = event.get("payload") or {}
            if event.get("provider") == "whatsapp" and event.get("event_type") == "message.status" and event.get("status") == "received" and str(payload.get("provider_message_id") or "") == provider_message_id:
                events.append((external_id, payload))
    else:
        rows = (
            get_admin_client()
            .table("integration_events")
            .select("external_id,payload,status")
            .eq("provider", "whatsapp")
            .eq("event_type", "message.status")
            .eq("status", "received")
            .order("created_at")
            .limit(50)
            .execute()
            .data
            or []
        )
        for row in rows:
            payload = row.get("payload") or {}
            if str(payload.get("provider_message_id") or "") == provider_message_id:
                events.append((str(row.get("external_id") or ""), payload))
    reconciled = []
    for external_id, payload in events:
        try:
            item = update_outbox_status_by_provider_message_id(
                provider_message_id=provider_message_id,
                status=str(payload.get("status") or ""),
                error_message=payload.get("error_message"),
                occurred_at=payload.get("occurred_at"),
            )
        except ValueError:
            continue
        ignored = bool(item.get("status_update_ignored"))
        _finish_provider_status_event(external_id=external_id, item=item, ignored=ignored)
        reconciled.append({"status": item.get("status"), "ignored": ignored})
    return reconciled


def _require_secret(value: str | None) -> None:
    expected = get_settings().make_webhook_secret
    legacy_ok = bool(expected and value and hmac.compare_digest(value, expected))
    configured_webhook = validate_any_webhook_secret(value, kind="whatsapp_text")
    if not (legacy_ok or configured_webhook):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook não autorizado.")


def _event_key(*, phone: str, message: str, external_message_id: str | None, file_hashes: list[str] | None = None) -> tuple[str, str]:
    payload_hash = _hash_payload(
        {
            "phone": normalize_phone(phone),
            "message": message,
            "external_message_id": external_message_id,
            "files": file_hashes or [],
        }
    )
    return external_message_id or payload_hash, payload_hash


def _demo_create_inbound(*, phone: str, name: str | None, message: str, external_message_id: str | None, payload_hash: str) -> dict:
    external_id = external_message_id or payload_hash
    if external_id in DEMO_INTEGRATION_EVENTS and DEMO_INTEGRATION_EVENTS[external_id].get("status") == "processed":
        event = DEMO_INTEGRATION_EVENTS[external_id]
        return {
            "accepted": True,
            "duplicate": True,
            "customer_id": event.get("customer_id"),
            "ticket_id": event.get("ticket_id"),
            "message_id": event.get("message_id"),
            "external_message_id": external_message_id,
        }

    customer = find_customer_by_phone(phone)
    if not customer:
        customer = create_customer(name=name or f"WhatsApp {phone}", phone=phone)

    open_ticket = next(
        (
            ticket
            for ticket in sorted(DEMO_TICKETS, key=lambda row: row.get("whatsapp_active_at") or row.get("updated_at") or "", reverse=True)
            if ticket.get("customer_id") == customer["id"]
            and ticket.get("source") == "whatsapp"
            and ticket.get("status") not in {"finalizado", "cancelado"}
        ),
        None,
    )
    created_ticket = False
    if not open_ticket:
        open_ticket = {
            "id": new_id("ticket"),
            "title": message.strip()[:80] or "Mídia recebida pelo WhatsApp",
            "customer_id": customer["id"],
            "farm_id": None,
            "crop_id": None,
            "category_id": None,
            "assigned_user_id": None,
            "status": "novo",
            "priority": "normal",
            "source": "whatsapp",
            "whatsapp_active_at": _now(),
            "created_at": _now(),
            "updated_at": _now(),
            "closed_at": None,
        }
        DEMO_TICKETS.append(open_ticket)
        created_ticket = True

    message_row = {
        "id": new_id("message"),
        "ticket_id": open_ticket["id"],
        "sender_id": customer["id"],
        "sender_name": customer["name"],
        "body": message.strip(),
        "channel": "whatsapp",
        "direction": "inbound",
        "is_internal": False,
        "external_message_id": external_message_id or f"hash:{external_id}",
        "delivery_status": "received",
        "external_status_updated_at": _now(),
        "created_at": _now(),
    }
    DEMO_MESSAGES.setdefault(open_ticket["id"], []).append(message_row)
    open_ticket["updated_at"] = _now()
    open_ticket["whatsapp_active_at"] = _now()
    DEMO_INTEGRATION_EVENTS[external_id] = {
        "provider": "whatsapp",
        "event_type": "message.inbound",
        "status": "processing",
        "customer_id": customer["id"],
        "ticket_id": open_ticket["id"],
        "message_id": message_row["id"],
        "payload_hash": payload_hash,
        "created_ticket": created_ticket,
        "created_at": _now(),
        "processed_at": None,
    }
    return {
        "accepted": True,
        "duplicate": False,
        "customer_id": customer["id"],
        "ticket_id": open_ticket["id"],
        "message_id": message_row["id"],
        "external_message_id": external_message_id,
        "event_id": external_id,
        "created_ticket": created_ticket,
    }


def _real_create_inbound(*, phone: str, name: str | None, message: str, external_message_id: str | None, payload_hash: str) -> dict:
    admin = get_admin_client()
    external_id = external_message_id or payload_hash
    message_external_id = external_message_id or f"hash:{external_id}"

    existing = (
        admin.table("integration_events")
        .select("id,entity_id,status,payload")
        .eq("provider", "whatsapp")
        .eq("external_id", external_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing and existing[0].get("status") == "processed":
        persisted = (
            admin.table("messages")
            .select("id,ticket_id")
            .eq("external_message_id", message_external_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return {
            "accepted": True,
            "duplicate": True,
            "ticket_id": persisted[0]["ticket_id"] if persisted else existing[0].get("entity_id"),
            "message_id": persisted[0]["id"] if persisted else None,
            "external_message_id": external_message_id,
        }

    persisted_message = (
        admin.table("messages")
        .select("id,ticket_id")
        .eq("external_message_id", message_external_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if persisted_message:
        ticket_id = persisted_message[0]["ticket_id"]
        if existing:
            admin.table("integration_events").update(
                {"status": "processed", "entity_type": "ticket", "entity_id": ticket_id, "error_message": None, "processed_at": _now()}
            ).eq("id", existing[0]["id"]).execute()
        return {
            "accepted": True,
            "duplicate": True,
            "recovered": True,
            "ticket_id": ticket_id,
            "message_id": persisted_message[0]["id"],
            "external_message_id": external_message_id,
        }

    event_payload = {
        "phone": phone,
        "name": name,
        "message": message,
        "external_message_id": external_message_id,
    }
    if existing:
        event = existing[0]
        admin.table("integration_events").update(
            {"status": "processing", "payload_hash": payload_hash, "payload": event_payload, "error_message": None, "processed_at": None}
        ).eq("id", event["id"]).execute()
    else:
        try:
            event = admin.table("integration_events").insert(
                {
                    "provider": "whatsapp",
                    "external_id": external_id,
                    "event_type": "message.inbound",
                    "status": "processing",
                    "payload_hash": payload_hash,
                    "payload": event_payload,
                }
            ).execute().data[0]
        except Exception:
            raced = (
                admin.table("integration_events")
                .select("id,entity_id,status")
                .eq("provider", "whatsapp")
                .eq("external_id", external_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if not raced:
                raise
            if raced[0].get("status") == "processed":
                return {
                    "accepted": True,
                    "duplicate": True,
                    "ticket_id": raced[0].get("entity_id"),
                    "external_message_id": external_message_id,
                }
            event = raced[0]

    try:
        customer = find_customer_by_phone(phone)
        if not customer:
            customer = create_customer(name=name or f"WhatsApp {phone}", phone=phone)

        candidate_rows = (
            admin.table("tickets")
            .select("*")
            .eq("customer_id", customer["id"])
            .eq("source", "whatsapp")
            .order("updated_at", desc=True)
            .limit(10)
            .execute()
            .data
            or []
        )
        ticket = next((row for row in candidate_rows if row.get("status") not in {"finalizado", "cancelado"}), None)
        created_ticket = False
        if not ticket:
            ticket = admin.table("tickets").insert(
                {
                    "title": message.strip()[:80] or "Mídia recebida pelo WhatsApp",
                    "customer_id": customer["id"],
                    "status": "novo",
                    "priority": "normal",
                    "source": "whatsapp",
                }
            ).execute().data[0]
            created_ticket = True

        message_row = admin.table("messages").insert(
            {
                "ticket_id": ticket["id"],
                "sender_id": None,
                "body": message.strip(),
                "channel": "whatsapp",
                "direction": "inbound",
                "is_internal": False,
                "external_message_id": message_external_id,
                "delivery_status": "received",
                "external_status_updated_at": _now(),
            }
        ).execute().data[0]
        admin.table("tickets").update({"updated_at": _now()}).eq("id", ticket["id"]).execute()
        return {
            "accepted": True,
            "duplicate": False,
            "customer_id": customer["id"],
            "ticket_id": ticket["id"],
            "message_id": message_row["id"],
            "external_message_id": external_message_id,
            "event_db_id": event["id"],
            "created_ticket": created_ticket,
        }
    except Exception as exc:
        admin.table("integration_events").update(
            {"status": "failed", "error_message": str(exc)[:1000], "processed_at": _now()}
        ).eq("id", event["id"]).execute()
        raise


def _finish_inbound(result: dict, *, attachment_count: int) -> None:
    if result.get("duplicate"):
        return
    settings = get_settings()
    if settings.demo_mode:
        event_id = result.get("event_id")
        if event_id and event_id in DEMO_INTEGRATION_EVENTS:
            DEMO_INTEGRATION_EVENTS[event_id].update(
                {"status": "processed", "attachment_count": attachment_count, "processed_at": _now()}
            )
        return
    event_id = result.get("event_db_id")
    if event_id:
        get_admin_client().table("integration_events").update(
            {
                "status": "processed",
                "entity_type": "ticket",
                "entity_id": result.get("ticket_id"),
                "error_message": None,
                "processed_at": _now(),
            }
        ).eq("id", event_id).execute()


def _fail_inbound(result: dict, exc: Exception) -> None:
    settings = get_settings()
    if settings.demo_mode:
        event_id = result.get("event_id")
        if event_id and event_id in DEMO_INTEGRATION_EVENTS:
            DEMO_INTEGRATION_EVENTS[event_id].update(
                {"status": "failed", "error_message": str(exc)[:1000], "processed_at": _now()}
            )
        return
    event_id = result.get("event_db_id")
    if event_id:
        get_admin_client().table("integration_events").update(
            {"status": "failed", "error_message": str(exc)[:1000], "processed_at": _now()}
        ).eq("id", event_id).execute()


def _rollback_inbound(result: dict, saved_attachments: list[dict]) -> None:
    if result.get("duplicate"):
        return
    for attachment in reversed(saved_attachments):
        try:
            delete_attachment(attachment)
        except Exception:
            logger.exception("Falha no rollback de anexo recebido do WhatsApp")

    ticket_id = str(result.get("ticket_id") or "")
    message_id = str(result.get("message_id") or "")
    if not ticket_id or not message_id:
        return
    settings = get_settings()
    if settings.demo_mode:
        DEMO_MESSAGES[ticket_id] = [row for row in DEMO_MESSAGES.get(ticket_id, []) if str(row.get("id")) != message_id]
        if result.get("created_ticket"):
            DEMO_TICKETS[:] = [row for row in DEMO_TICKETS if str(row.get("id")) != ticket_id]
        return

    admin = get_admin_client()
    admin.table("messages").delete().eq("id", message_id).eq("ticket_id", ticket_id).execute()
    if result.get("created_ticket"):
        remaining = admin.table("messages").select("id", count="exact").eq("ticket_id", ticket_id).limit(1).execute()
        if not (remaining.data or []):
            admin.table("tickets").delete().eq("id", ticket_id).execute()


def _create_inbound(*, phone: str, name: str | None, message: str, external_message_id: str | None, payload_hash: str) -> dict:
    return (
        _demo_create_inbound(phone=phone, name=name, message=message, external_message_id=external_message_id, payload_hash=payload_hash)
        if get_settings().demo_mode
        else _real_create_inbound(phone=phone, name=name, message=message, external_message_id=external_message_id, payload_hash=payload_hash)
    )




def _record_generic_configured_event(*, webhook: dict, payload: dict, external_id: str | None) -> dict:
    payload_hash = _hash_payload(payload)
    event_external_id = (external_id or payload_hash)[:500]
    provider = f"configured:{webhook.get('public_id')}"
    settings = get_settings()
    if settings.demo_mode:
        key = f"{provider}:{event_external_id}"
        duplicate = key in DEMO_INTEGRATION_EVENTS
        if not duplicate:
            DEMO_INTEGRATION_EVENTS[key] = {
                "provider": provider,
                "event_type": "configured.generic",
                "status": "processed",
                "payload_hash": payload_hash,
                "payload": payload,
                "created_at": _now(),
                "processed_at": _now(),
            }
        return {"accepted": True, "duplicate": duplicate, "external_id": event_external_id}

    admin = get_admin_client()
    existing = (
        admin.table("integration_events")
        .select("id,status")
        .eq("provider", provider)
        .eq("external_id", event_external_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        return {"accepted": True, "duplicate": True, "external_id": event_external_id}
    admin.table("integration_events").insert(
        {
            "provider": provider,
            "external_id": event_external_id,
            "event_type": "configured.generic",
            "status": "processed",
            "payload_hash": payload_hash,
            "payload": payload,
            "processed_at": _now(),
        }
    ).execute()
    return {"accepted": True, "duplicate": False, "external_id": event_external_id}


def _attach_ai_control(result: dict) -> dict:
    ticket_id = result.get("ticket_id")
    if not ticket_id:
        return result
    try:
        result["whatsapp_window"] = get_whatsapp_service_window(str(ticket_id))
    except Exception:
        logger.exception("Falha ao resolver janela do WhatsApp para ticket %s", ticket_id)
        result["whatsapp_window"] = {"applicable": True, "open": False, "send_mode": "template_required", "template_required": True}
    try:
        control = ensure_ticket_ai_control(str(ticket_id))
        control["make_instruction"] = "ROUTE_TO_AI" if control.get("route_to_ai") else "STOP_AT_VENDRA"
        control["ai_reply_path"] = "/webhooks/make/ai/reply"
        control["thread_id"] = f"VENDRA-{ticket_id}"
        result["automation"] = control
    except Exception:
        logger.exception("Falha ao resolver controle da IA para ticket %s", ticket_id)
        result["automation"] = {
            "enabled": False,
            "mode": "human",
            "connected": False,
            "connection_state": "disconnected",
            "route_to_ai": False,
            "should_respond": False,
            "control_version": 1,
            "make_instruction": "STOP_AT_VENDRA",
            "ai_reply_path": "/webhooks/make/ai/reply",
            "thread_id": f"VENDRA-{ticket_id}",
        }
    return result


@router.post("/configurados/{public_id}", status_code=202)
async def configured_webhook(
    public_id: str,
    request: Request,
    x_vendra_webhook_secret: str | None = Header(default=None, alias="X-Vendra-Webhook-Secret"),
    x_event_id: str | None = Header(default=None),
):
    webhook = validate_webhook(public_id, x_vendra_webhook_secret)
    if not webhook:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook não autorizado.")
    raw_body = await request.body()
    if len(raw_body) > 1024 * 1024:
        mark_webhook_used(webhook, "payload_too_large")
        raise HTTPException(status_code=413, detail="Payload JSON excede o limite de 1 MB.")
    try:
        payload = json.loads(raw_body)
    except Exception as exc:
        mark_webhook_used(webhook, "invalid_json")
        raise HTTPException(status_code=422, detail="O webhook exige corpo JSON válido.") from exc
    if not isinstance(payload, dict):
        mark_webhook_used(webhook, "invalid_payload")
        raise HTTPException(status_code=422, detail="O corpo JSON precisa ser um objeto.")

    kind = webhook.get("kind")
    try:
        if kind == "whatsapp_text":
            parsed = WhatsAppInbound.model_validate(payload)
            if not normalize_phone(parsed.phone):
                raise HTTPException(status_code=422, detail="Telefone inválido.")
            external_id, payload_hash = _event_key(
                phone=parsed.phone,
                message=parsed.message,
                external_message_id=parsed.external_message_id,
            )
            result = _create_inbound(
                phone=parsed.phone,
                name=parsed.name,
                message=parsed.message,
                external_message_id=parsed.external_message_id or (None if external_id == payload_hash else external_id),
                payload_hash=payload_hash,
            )
            _finish_inbound(result, attachment_count=0)
            _attach_ai_control(result)
            result["webhook_id"] = str(webhook.get("id"))
            mark_webhook_used(webhook, "processed")
            return result
        if kind == "generic_json":
            result = _record_generic_configured_event(webhook=webhook, payload=payload, external_id=x_event_id)
            result["webhook_id"] = str(webhook.get("id"))
            mark_webhook_used(webhook, "duplicate" if result.get("duplicate") else "processed")
            return result
        mark_webhook_used(webhook, "unsupported_kind")
        raise HTTPException(status_code=422, detail="Tipo de webhook não suportado.")
    except HTTPException:
        raise
    except Exception as exc:
        mark_webhook_used(webhook, "failed")
        logger.exception("Falha ao processar webhook configurado")
        raise HTTPException(status_code=500, detail="Falha ao processar o webhook.") from exc


@router.post("/configurados/{public_id}/media", status_code=202)
async def configured_whatsapp_media_webhook(
    public_id: str,
    phone: str = Form(...),
    name: str = Form(""),
    message: str = Form(""),
    external_message_id: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    x_vendra_webhook_secret: str | None = Header(default=None, alias="X-Vendra-Webhook-Secret"),
):
    webhook = validate_webhook(public_id, x_vendra_webhook_secret)
    if not webhook:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook não autorizado.")
    if webhook.get("kind") != "whatsapp_text":
        mark_webhook_used(webhook, "unsupported_media")
        raise HTTPException(status_code=422, detail="Este webhook não aceita mídia de WhatsApp.")
    if not normalize_phone(phone):
        mark_webhook_used(webhook, "invalid_phone")
        raise HTTPException(status_code=422, detail="Telefone inválido.")
    selected = [upload for upload in files if upload.filename]
    if not selected:
        raise HTTPException(status_code=422, detail="Envie ao menos um arquivo de mídia.")
    if len(selected) > 6:
        raise HTTPException(status_code=422, detail="Envie no máximo 6 arquivos por evento.")

    prepared = []
    try:
        for upload in selected:
            content = await upload.read()
            prepared.append(prepare_attachment(upload.filename, upload.content_type, content))
            await upload.close()
    except AttachmentError as exc:
        mark_webhook_used(webhook, "invalid_media")
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    external_value = external_message_id.strip() or None
    _, payload_hash = _event_key(
        phone=phone,
        message=message,
        external_message_id=external_value,
        file_hashes=[item.checksum_sha256 for item in prepared],
    )
    result = _create_inbound(
        phone=phone,
        name=name.strip() or None,
        message=message,
        external_message_id=external_value,
        payload_hash=payload_hash,
    )
    if result.get("duplicate"):
        _attach_ai_control(result)
        mark_webhook_used(webhook, "duplicate")
        return result

    saved: list[dict] = []
    try:
        for item in prepared:
            saved.append(
                save_attachment(
                    ticket_id=str(result["ticket_id"]),
                    message_id=str(result["message_id"]),
                    uploaded_by=None,
                    prepared=item,
                )
            )
        _finish_inbound(result, attachment_count=len(saved))
        mark_webhook_used(webhook, "processed")
    except Exception as exc:
        logger.exception("Falha ao persistir mídia de webhook configurado")
        _rollback_inbound(result, saved)
        _fail_inbound(result, exc)
        mark_webhook_used(webhook, "failed")
        raise HTTPException(status_code=500, detail="Não foi possível persistir a mídia recebida.") from exc

    result["attachments"] = len(saved)
    _attach_ai_control(result)
    result["webhook_id"] = str(webhook.get("id"))
    return result


@router.post("/make/whatsapp", status_code=202)
def make_whatsapp_webhook(payload: WhatsAppInbound, x_webhook_secret: str | None = Header(default=None)):
    _require_secret(x_webhook_secret)
    if not normalize_phone(payload.phone):
        raise HTTPException(status_code=422, detail="Telefone inválido.")
    external_id, payload_hash = _event_key(
        phone=payload.phone,
        message=payload.message,
        external_message_id=payload.external_message_id,
    )
    result = _create_inbound(
        phone=payload.phone,
        name=payload.name,
        message=payload.message,
        external_message_id=payload.external_message_id or (None if external_id == payload_hash else external_id),
        payload_hash=payload_hash,
    )
    _finish_inbound(result, attachment_count=0)
    result["media_url_ignored"] = bool(payload.media_url)
    if payload.media_url:
        result["media_instruction"] = "Para mídia, o cenário Make deve enviar o arquivo para /webhooks/make/whatsapp/media; o backend não baixa URL arbitrária."
    _attach_ai_control(result)
    return result


@router.post("/make/whatsapp/media", status_code=202)
async def make_whatsapp_media_webhook(
    phone: str = Form(...),
    name: str = Form(""),
    message: str = Form(""),
    external_message_id: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    x_webhook_secret: str | None = Header(default=None),
):
    _require_secret(x_webhook_secret)
    if not normalize_phone(phone):
        raise HTTPException(status_code=422, detail="Telefone inválido.")
    selected = [upload for upload in files if upload.filename]
    if not selected:
        raise HTTPException(status_code=422, detail="Envie ao menos um arquivo de mídia.")
    if len(selected) > 6:
        raise HTTPException(status_code=422, detail="Envie no máximo 6 arquivos por evento.")

    prepared = []
    try:
        for upload in selected:
            content = await upload.read()
            prepared.append(prepare_attachment(upload.filename, upload.content_type, content))
            await upload.close()
    except AttachmentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    external_value = external_message_id.strip() or None
    _, payload_hash = _event_key(
        phone=phone,
        message=message,
        external_message_id=external_value,
        file_hashes=[item.checksum_sha256 for item in prepared],
    )
    result = _create_inbound(
        phone=phone,
        name=name.strip() or None,
        message=message,
        external_message_id=external_value,
        payload_hash=payload_hash,
    )
    if result.get("duplicate"):
        _attach_ai_control(result)
        return result

    saved: list[dict] = []
    try:
        for item in prepared:
            saved.append(
                save_attachment(
                    ticket_id=str(result["ticket_id"]),
                    message_id=str(result["message_id"]),
                    uploaded_by=None,
                    prepared=item,
                )
            )
        _finish_inbound(result, attachment_count=len(saved))
    except Exception as exc:
        logger.exception("Falha ao persistir mídia recebida do WhatsApp")
        _rollback_inbound(result, saved)
        _fail_inbound(result, exc)
        raise HTTPException(status_code=500, detail="Não foi possível persistir a mídia recebida.") from exc

    result["attachments"] = len(saved)
    _attach_ai_control(result)
    return result


@router.get("/make/ai/control/{ticket_id}")
def make_ai_control(ticket_id: str, x_webhook_secret: str | None = Header(default=None)):
    _require_secret(x_webhook_secret)
    try:
        control = get_ticket_ai_control(ticket_id)
        control["make_instruction"] = "ROUTE_TO_AI" if control.get("route_to_ai") else "STOP_AT_VENDRA"
        control["ai_reply_path"] = "/webhooks/make/ai/reply"
        control["thread_id"] = f"VENDRA-{ticket_id}"
        return {"ticket_id": str(ticket_id), "automation": control, "routing": route_contract()}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/make/ai/reply", status_code=202)
def make_ai_reply(payload: AIReplyInbound, x_webhook_secret: str | None = Header(default=None)):
    _require_secret(x_webhook_secret)
    try:
        result = persist_ai_reply(
            ticket_id=payload.ticket_id,
            message=payload.message,
            control_version=payload.control_version,
            external_message_id=payload.external_message_id,
            delivery_mode=payload.delivery_mode,
        )
        route_code = normalize_route_code(payload.route_code)
        if not result.get("suppressed") and not result.get("duplicate") and route_code:
            try:
                routing = apply_ai_route(ticket_id=payload.ticket_id, route_code=route_code)
            except Exception as route_exc:
                logger.exception("Falha ao aplicar rota comercial da IA")
                routing = {"applied": False, "reason": "routing_exception", "route_code": route_code, "error": str(route_exc)[:300]}
            result["routing"] = routing
            record_audit(
                actor_id=None,
                entity_type="ticket",
                entity_id=str(payload.ticket_id),
                action="ai_route_received",
                payload={"route_code": route_code, "routing": routing},
            )
        elif route_code:
            result["routing"] = {"applied": False, "reason": "reply_suppressed_or_duplicate", "route_code": route_code}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@router.post("/make/disparos/{dispatch_id}/status")
def make_dispatch_status(
    dispatch_id: str,
    payload: DispatchStatusUpdate,
    x_webhook_secret: str | None = Header(default=None),
):
    _require_secret(x_webhook_secret)
    try:
        row = update_dispatch_status(
            dispatch_id=dispatch_id,
            status=payload.status,
            provider_message_id=payload.provider_message_id,
            error_message=payload.error_message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"updated": True, "id": str(row.get("id")), "status": row.get("status")}


@router.post("/make/whatsapp/provider-status")
def make_whatsapp_provider_status(
    payload: ProviderStatusUpdate,
    x_webhook_secret: str | None = Header(default=None),
):
    _require_secret(x_webhook_secret)
    provider_message_id = payload.provider_message_id.strip()
    status_value = payload.status.strip().lower()
    if status_value not in {"sent", "delivered", "read", "failed"}:
        raise HTTPException(status_code=422, detail="Status do provedor inválido.")
    occurred_at = _provider_status_time(payload.occurred_at)
    event_payload = {
        "provider_message_id": provider_message_id,
        "status": status_value,
        "occurred_at": occurred_at,
        "recipient_id": payload.recipient_id,
        "error_message": payload.error_message,
    }
    external_id = _provider_status_event_id(provider_message_id, status_value)
    _remember_provider_status_pending(external_id=external_id, payload=event_payload)
    try:
        item = update_outbox_status_by_provider_message_id(
            provider_message_id=provider_message_id,
            status=status_value,
            error_message=payload.error_message,
            occurred_at=occurred_at,
        )
    except ValueError:
        return {
            "accepted": True,
            "updated": False,
            "pending_match": True,
            "provider_message_id": provider_message_id,
            "status": status_value,
        }
    ignored = bool(item.get("status_update_ignored"))
    _finish_provider_status_event(external_id=external_id, item=item, ignored=ignored)
    if not ignored:
        record_audit(
            actor_id=None,
            entity_type="whatsapp_outbox",
            entity_id=str(item.get("id") or ""),
            action="whatsapp_provider_status",
            payload={
                "provider_message_id": provider_message_id,
                "status": status_value,
                "occurred_at": occurred_at,
                "recipient_id": payload.recipient_id,
                "error_message": payload.error_message,
            },
        )
    return {
        "accepted": True,
        "updated": not ignored,
        "ignored": ignored,
        "pending_match": False,
        "id": str(item.get("id") or ""),
        "provider_message_id": provider_message_id,
        "status": item.get("status"),
    }


@router.get("/make/whatsapp/outbox")
def make_whatsapp_outbox(
    limit: int = 10,
    worker_id: str | None = None,
    x_webhook_secret: str | None = Header(default=None),
):
    _require_secret(x_webhook_secret)
    return {"sender": public_whatsapp_channel(), "items": claim_whatsapp_outbox(limit=limit, worker_id=worker_id)}


@router.post("/make/whatsapp/outbox/{outbox_id}/status")
def make_whatsapp_outbox_status(
    outbox_id: str,
    payload: OutboxStatusUpdate,
    x_webhook_secret: str | None = Header(default=None),
):
    _require_secret(x_webhook_secret)
    try:
        item = update_outbox_status(
            outbox_id=outbox_id,
            status=payload.status,
            provider_message_id=payload.provider_message_id,
            error_message=payload.error_message,
        )
        if payload.provider_message_id:
            _reconcile_pending_provider_statuses(payload.provider_message_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"updated": not bool(item.get("status_update_ignored")), "ignored": bool(item.get("status_update_ignored")), "id": str(item.get("id")), "status": item.get("status")}


@router.get("/make/whatsapp/outbox/{outbox_id}/attachments/{attachment_id}")
def make_whatsapp_outbox_attachment(
    outbox_id: str,
    attachment_id: str,
    x_webhook_secret: str | None = Header(default=None),
):
    _require_secret(x_webhook_secret)
    attachment = get_outbox_attachment(outbox_id, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Anexo não encontrado para este item de saída.")
    settings = get_settings()
    if settings.demo_mode:
        path = demo_file_path(attachment)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Arquivo não encontrado no armazenamento local.")
        return FileResponse(
            path=path,
            media_type=attachment.get("mime_type") or "application/octet-stream",
            filename=attachment.get("file_name") or "arquivo",
        )
    try:
        return RedirectResponse(url=signed_download_url(attachment, expires_seconds=180), status_code=307)
    except AttachmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
