from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any
from threading import RLock

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.admin_settings_service import get_ai_settings
from app.services.demo_store import DEMO_INTEGRATION_EVENTS, DEMO_MESSAGES, DEMO_TICKETS, new_id
from app.services.integration_service import queue_whatsapp_outbound, reserve_whatsapp_outbox
from app.services.message_formatting_service import normalize_ai_message
from app.services.whatsapp_window_service import get_whatsapp_service_window

logger = logging.getLogger(__name__)

AI_MODES = {"ai", "human"}
_CONTROL_LOCK = RLock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_name(config: dict) -> str:
    raw = str(config.get("assistant_name") or "Assistente de IA").strip()
    if raw.casefold() in {"assistente ia", "assistente de ia"}:
        return "Assistente de IA"
    return raw or "Assistente de IA"


def _default_mode(ticket: dict | None) -> str:
    config = get_ai_settings()
    if not config.get("enabled"):
        return "human"
    if not ticket or ticket.get("source") != "whatsapp":
        return "human"
    configured = str(config.get("default_mode") or "ai").strip().lower()
    return configured if configured in AI_MODES else "ai"


def _demo_ticket(ticket_id: str) -> dict | None:
    return next((row for row in DEMO_TICKETS if str(row.get("id")) == str(ticket_id)), None)


def _normalize_ticket_control(ticket: dict) -> dict:
    if ticket.get("automation_mode") not in AI_MODES:
        ticket["automation_mode"] = _default_mode(ticket)
    try:
        version = int(ticket.get("automation_version") or 1)
    except (TypeError, ValueError):
        version = 1
    ticket["automation_version"] = max(version, 1)
    return ticket


def get_ticket_ai_control(ticket_id: str) -> dict[str, Any]:
    config = get_ai_settings()
    if get_settings().demo_mode:
        ticket = _demo_ticket(ticket_id)
        if not ticket:
            raise ValueError("Atendimento não encontrado.")
        _normalize_ticket_control(ticket)
        mode = ticket.get("automation_mode") or "human"
        enabled = bool(config.get("enabled")) and ticket.get("source") == "whatsapp"
        connected = bool(enabled and mode == "ai")
        return {
            "enabled": enabled,
            "mode": mode,
            "mode_label": "Conectado à IA" if connected else "IA desconectada deste atendimento",
            "connected": connected,
            "connection_state": "connected" if connected else "disconnected",
            "route_to_ai": connected,
            "should_respond": connected,
            "control_version": int(ticket.get("automation_version") or 1),
            "paused_at": ticket.get("ai_paused_at"),
            "paused_by": ticket.get("ai_paused_by"),
            "resumed_at": ticket.get("ai_resumed_at"),
            "resumed_by": ticket.get("ai_resumed_by"),
            "assistant_name": _assistant_name(config),
        }

    if getattr(get_settings(), 'whatsapp_persistent_control_enabled', False):
        from app.services.whatsapp_control_service import read_control
        return read_control(ticket_id, assistant_name=_assistant_name(config))

    # O Supabase real permanece fora da linha ativa atual. Quando a migration
    # de controle da IA for homologada, estes campos passam a ser lidos da
    # tabela tickets. Enquanto isso, retornamos modo humano por segurança.
    rows = get_admin_client().table("tickets").select("id,source").eq("id", ticket_id).limit(1).execute().data or []
    if not rows:
        raise ValueError("Atendimento não encontrado.")
    return {
        "enabled": False,
        "mode": "human",
        "mode_label": "IA desconectada deste atendimento",
        "connected": False,
        "connection_state": "disconnected",
        "route_to_ai": False,
        "should_respond": False,
        "control_version": 1,
        "paused_at": None,
        "paused_by": None,
        "resumed_at": None,
        "resumed_by": None,
        "assistant_name": _assistant_name(config),
        "requires_migration": True,
    }


def set_ticket_ai_mode(ticket_id: str, *, mode: str, actor_id: str | None, source: str = "ui") -> dict[str, Any]:
    mode = str(mode or "").strip().lower()
    if mode not in AI_MODES:
        raise ValueError("Modo de atendimento inválido.")
    if not get_settings().demo_mode:
        if getattr(get_settings(), 'whatsapp_persistent_control_enabled', False):
            from app.services.whatsapp_control_service import change_mode
            return change_mode(ticket_id,mode=mode,actor_id=actor_id,
                assistant_name=_assistant_name(get_ai_settings()))
        raise ValueError("O controle de IA no Supabase real ainda depende da migration de tickets desta camada.")
    with _CONTROL_LOCK:
        ticket = _demo_ticket(ticket_id)
        if not ticket:
            raise ValueError("Atendimento não encontrado.")
        if ticket.get("source") != "whatsapp":
            raise ValueError("O controle de IA está disponível somente em atendimentos originados pelo WhatsApp.")
        _normalize_ticket_control(ticket)
        current = ticket.get("automation_mode")
        if current != mode:
            ticket["automation_mode"] = mode
            ticket["automation_version"] = int(ticket.get("automation_version") or 1) + 1
            ticket["updated_at"] = _now()
            if mode == "human":
                ticket["ai_paused_at"] = _now()
                ticket["ai_paused_by"] = actor_id or source
            else:
                ticket["ai_resumed_at"] = _now()
                ticket["ai_resumed_by"] = actor_id or source
        control = get_ticket_ai_control(ticket_id)
    _notify_make_control_async(ticket_id=ticket_id, control=control, source=source)
    return control


def disconnect_ticket_from_ai(ticket_id: str, *, actor_id: str | None, source: str = "ui_disconnect") -> dict[str, Any]:
    """Desconecta somente a rota ticket -> IA; a entrada WhatsApp continua ativa no VENDRA."""
    return set_ticket_ai_mode(ticket_id, mode="human", actor_id=actor_id, source=source)


def connect_ticket_to_ai(ticket_id: str, *, actor_id: str | None, source: str = "ui_reconnect") -> dict[str, Any]:
    """Reconecta o ticket ao fluxo de IA, desde que a automação global esteja habilitada."""
    if not get_settings().demo_mode and getattr(get_settings(), 'whatsapp_persistent_control_enabled', False):
        return set_ticket_ai_mode(ticket_id, mode='ai', actor_id=actor_id, source=source)
    config = get_ai_settings()
    if not config.get("enabled"):
        raise ValueError("Ative a IA em Configurações antes de reconectar este atendimento.")
    return set_ticket_ai_mode(ticket_id, mode="ai", actor_id=actor_id, source=source)


def ensure_ticket_ai_control(ticket_id: str) -> dict[str, Any]:
    """Garante um estado determinístico para ticket recém-criado ou legado."""
    return get_ticket_ai_control(ticket_id)


def ai_reply_allowed(ticket_id: str, control_version: int) -> tuple[bool, str, dict[str, Any]]:
    control = get_ticket_ai_control(ticket_id)
    if not control.get("enabled"):
        return False, "ai_disabled", control
    if control.get("mode") != "ai":
        return False, "human_takeover", control
    if int(control.get("control_version") or 0) != int(control_version):
        return False, "stale_control_version", control
    return True, "ok", control


def _ai_event_key(external_message_id: str | None) -> str | None:
    value = str(external_message_id or "").strip()
    return f"ai_reply:{value}" if value else None


def _find_demo_ai_event(external_message_id: str | None) -> dict | None:
    key = _ai_event_key(external_message_id)
    if not key:
        return None
    event = DEMO_INTEGRATION_EVENTS.get(key)
    return dict(event) if event else None


def persist_ai_reply(
    *,
    ticket_id: str,
    message: str,
    control_version: int,
    external_message_id: str | None = None,
    delivery_mode: str = "outbox",
) -> dict[str, Any]:
    body, body_normalized = normalize_ai_message(str(message or ""))
    if not body:
        raise ValueError("A resposta da IA não pode ser vazia.")
    delivery_mode = str(delivery_mode or "outbox").strip().lower()
    if delivery_mode not in {"outbox", "inline_make"}:
        raise ValueError("Modo de entrega da resposta da IA inválido.")
    with _CONTROL_LOCK:
        whatsapp_window = get_whatsapp_service_window(ticket_id)
        duplicate_event = _find_demo_ai_event(external_message_id) if get_settings().demo_mode else None
        window_allows_freeform = (not whatsapp_window.get("applicable")) or bool(whatsapp_window.get("open"))
        if duplicate_event and duplicate_event.get("status") == "processed":
            duplicate_outbox = None
            duplicate_outbox_id = duplicate_event.get("outbox_id")
            if duplicate_outbox_id and delivery_mode == "inline_make" and window_allows_freeform:
                try:
                    duplicate_outbox = reserve_whatsapp_outbox(str(duplicate_outbox_id), worker_id="make-ai-inline")
                except ValueError:
                    duplicate_outbox = None
            return {
                "accepted": True,
                "authorized": window_allows_freeform,
                "duplicate": True,
                "suppressed": not window_allows_freeform,
                "reason": None if window_allows_freeform else "whatsapp_template_required",
                "template_required": bool(whatsapp_window.get("template_required")),
                "whatsapp_window": whatsapp_window,
                "message_normalized": body_normalized,
                "message_id": duplicate_event.get("message_id"),
                "outbox_id": duplicate_outbox_id,
                "outbox": duplicate_outbox,
                "delivery_mode": delivery_mode,
                "control": get_ticket_ai_control(ticket_id),
            }

        allowed, reason, control = ai_reply_allowed(ticket_id, control_version)
        if not allowed:
            return {"accepted": True, "authorized": False, "suppressed": True, "reason": reason, "control": control, "whatsapp_window": whatsapp_window}
        if whatsapp_window.get("applicable") and not whatsapp_window.get("open"):
            return {
                "accepted": True,
                "authorized": False,
                "suppressed": True,
                "reason": "whatsapp_template_required",
                "template_required": True,
                "whatsapp_window": whatsapp_window,
                "message_normalized": body_normalized,
                "control": control,
            }
        if not get_settings().demo_mode:
            raise ValueError("A persistência de autoria da IA no Supabase real ainda depende da migration desta camada.")

        assistant_name = str(control.get("assistant_name") or "Assistente de IA")
        row = {
            "id": new_id("message"),
            "ticket_id": str(ticket_id),
            "sender_id": None,
            "sender_name": assistant_name,
            "sender_kind": "ai",
            "body": body,
            "channel": "whatsapp",
            "direction": "outbound",
            "is_internal": False,
            "external_message_id": external_message_id,
            "delivery_status": "pending",
            "created_at": _now(),
        }
        DEMO_MESSAGES.setdefault(str(ticket_id), []).append(row)
        ticket = _demo_ticket(ticket_id)
        if ticket:
            ticket["updated_at"] = _now()
        outbox = queue_whatsapp_outbound(ticket_id=str(ticket_id), message_id=str(row["id"]))
        reserved = None
        if outbox and delivery_mode == "inline_make":
            reserved = reserve_whatsapp_outbox(str(outbox.get("id")), worker_id="make-ai-inline")
        event_key = _ai_event_key(external_message_id)
        if event_key:
            DEMO_INTEGRATION_EVENTS[event_key] = {
                "provider": "ai",
                "event_type": "message.ai.outbound",
                "status": "processed",
                "ticket_id": str(ticket_id),
                "message_id": str(row["id"]),
                "outbox_id": str(outbox.get("id")) if outbox else None,
                "control_version": int(control_version),
                "created_at": _now(),
                "processed_at": _now(),
            }
        return {
            "accepted": True,
            "authorized": True,
            "duplicate": False,
            "suppressed": False,
            "template_required": False,
            "whatsapp_window": whatsapp_window,
            "message_normalized": body_normalized,
            "message_id": str(row["id"]),
            "outbox_id": str(outbox.get("id")) if outbox else None,
            "outbox": reserved,
            "delivery_mode": delivery_mode,
            "control": control,
        }


def _post_json(url: str, payload: dict[str, Any], *, timeout: float = 4.0) -> tuple[int, str]:
    if get_settings().app_env == "staging":
        raise RuntimeError("Ambiente de homologação: envio externo bloqueado.")
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "VENDRA-AI-Control/0.0.7"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        sample = response.read(512).decode("utf-8", errors="replace")
        return int(getattr(response, "status", 200)), sample


def send_make_control_event(*, ticket_id: str, control: dict[str, Any], source: str) -> dict[str, Any]:
    config = get_ai_settings()
    url = str(config.get("control_webhook_url") or "").strip()
    if not config.get("control_webhook_enabled") or not url:
        return {"sent": False, "reason": "disabled_or_missing"}
    payload = {
        "event": "ai.control.changed",
        "ticket_id": str(ticket_id),
        "mode": control.get("mode"),
        "connected": bool(control.get("connected")),
        "connection_state": control.get("connection_state"),
        "route_to_ai": bool(control.get("route_to_ai")),
        "should_respond": bool(control.get("should_respond")),
        "control_version": int(control.get("control_version") or 1),
        "source": source,
        "changed_at": _now(),
    }
    try:
        status, sample = _post_json(url, payload)
        return {"sent": 200 <= status < 300, "status_code": status, "response": sample}
    except urllib.error.HTTPError as exc:
        sample = exc.read(512).decode("utf-8", errors="replace")
        return {"sent": False, "status_code": int(exc.code), "response": sample, "reason": "http_error"}
    except Exception as exc:
        return {"sent": False, "reason": "exception", "error": str(exc)[:500]}


def _notify_make_control_async(*, ticket_id: str, control: dict[str, Any], source: str) -> None:
    config = get_ai_settings()
    if not config.get("control_webhook_enabled") or not str(config.get("control_webhook_url") or "").strip():
        return

    def worker() -> None:
        result = send_make_control_event(ticket_id=ticket_id, control=dict(control), source=source)
        if not result.get("sent"):
            logger.warning("Webhook de controle da IA não confirmado para ticket %s: %s", ticket_id, result)

    threading.Thread(target=worker, name=f"vendra-ai-control-{ticket_id}", daemon=True).start()
