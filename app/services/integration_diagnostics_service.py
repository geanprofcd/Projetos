from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.services.admin_settings_service import get_ai_settings, get_ai_routing_settings, get_dispatch_settings
from app.services.demo_store import DEMO_DISPATCHES, DEMO_INTEGRATION_EVENTS, DEMO_TICKETS


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _post_json(url: str, payload: dict[str, Any], *, timeout: float = 7.0) -> tuple[int, str]:
    if get_settings().app_env == "staging":
        raise RuntimeError("Ambiente de homologação: teste externo bloqueado.")
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "VENDRA-Integration-Test/0.0.8"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(1024).decode("utf-8", errors="replace")
        return int(getattr(response, "status", 200)), body


def _record_diagnostic(*, channel: str, status: str, payload: dict[str, Any], status_code: int | None = None, response: str | None = None, error: str | None = None) -> dict[str, Any]:
    row = {
        "provider": "make",
        "event_type": f"diagnostic.{channel}",
        "status": status,
        "entity_type": "integration_test",
        "entity_id": channel,
        "payload": payload,
        "status_code": status_code,
        "response": (response or "")[:1000] or None,
        "error_message": (error or "")[:1000] or None,
        "created_at": _now(),
        "processed_at": _now(),
    }
    if get_settings().demo_mode:
        DEMO_INTEGRATION_EVENTS[f"diagnostic:{channel}:{uuid4().hex}"] = row
    return row


def _probe(*, channel: str, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not str(url or "").strip():
        raise ValueError("Nenhum webhook foi configurado para este canal.")
    try:
        status_code, sample = _post_json(str(url).strip(), payload)
        ok = 200 <= status_code < 300
        row = _record_diagnostic(
            channel=channel,
            status="processed" if ok else "failed",
            payload=payload,
            status_code=status_code,
            response=sample,
            error=None if ok else f"Make respondeu HTTP {status_code}.",
        )
        return {
            "ok": ok,
            "channel": channel,
            "status_code": status_code,
            "response": sample[:1000],
            "event": row,
        }
    except urllib.error.HTTPError as exc:
        sample = exc.read(1024).decode("utf-8", errors="replace")
        row = _record_diagnostic(
            channel=channel,
            status="failed",
            payload=payload,
            status_code=int(exc.code),
            response=sample,
            error=f"Make respondeu HTTP {exc.code}.",
        )
        return {"ok": False, "channel": channel, "status_code": int(exc.code), "response": sample[:1000], "event": row}
    except Exception as exc:
        row = _record_diagnostic(channel=channel, status="failed", payload=payload, error=str(exc))
        return {"ok": False, "channel": channel, "status_code": None, "response": None, "error": str(exc)[:1000], "event": row}


def test_ai_control_webhook() -> dict[str, Any]:
    config = get_ai_settings()
    url = str(config.get("control_webhook_url") or "").strip()
    if not url:
        raise ValueError("Configure a URL do webhook de controle da IA antes de testar.")
    payload = {
        "event": "vendra.integration.test",
        "channel": "ai_control",
        "test_only": True,
        "source": "vendra",
        "version": "0.0.8",
        "sent_at": _now(),
        "note": "Teste de conectividade. Não representa mudança de atendimento e não deve enviar mensagem ao cliente.",
    }
    return _probe(channel="ai_control", url=url, payload=payload)


def test_dispatch_webhook() -> dict[str, Any]:
    config = get_dispatch_settings()
    url = str(config.get("webhook_url") or "").strip()
    if not url:
        raise ValueError("Configure a URL do webhook de Disparos antes de testar.")
    payload = {
        "event": "vendra.integration.test",
        "channel": "dispatches",
        "test_only": True,
        "source": "vendra",
        "version": "0.0.8",
        "sent_at": _now(),
        "note": "Teste de conectividade. Não contém telefone e não deve disparar mensagem no Meta.",
    }
    return _probe(channel="dispatches", url=url, payload=payload)


def list_diagnostic_events(limit: int = 20) -> list[dict[str, Any]]:
    if not get_settings().demo_mode:
        return []
    rows: list[dict[str, Any]] = []
    for key, value in DEMO_INTEGRATION_EVENTS.items():
        if str(value.get("event_type") or "").startswith("diagnostic."):
            rows.append(dict(value, external_id=key))
    rows.sort(key=lambda row: row.get("created_at") or "", reverse=True)
    return rows[: max(1, min(int(limit), 100))]


def integration_channel_overview() -> dict[str, Any]:
    ai = get_ai_settings()
    ai_routing = get_ai_routing_settings()
    dispatches = get_dispatch_settings()

    if get_settings().demo_mode:
        whatsapp_tickets = [row for row in DEMO_TICKETS if row.get("source") == "whatsapp" and row.get("status") not in {"finalizado", "cancelado"}]
        ai_mode = 0
        human_mode = 0
        for ticket in whatsapp_tickets:
            mode = str(ticket.get("automation_mode") or ai.get("default_mode") or "ai") if ai.get("enabled") else "human"
            if mode == "ai":
                ai_mode += 1
            else:
                human_mode += 1
        dispatch_counts = {
            "total": len(DEMO_DISPATCHES),
            "submitted": sum(1 for row in DEMO_DISPATCHES if row.get("status") in {"submitted", "sent", "delivered", "read"}),
            "failed": sum(1 for row in DEMO_DISPATCHES if row.get("status") == "failed"),
        }
    else:
        ai_mode = human_mode = 0
        dispatch_counts = {"total": 0, "submitted": 0, "failed": 0}

    return {
        "ai": {
            "enabled": bool(ai.get("enabled")),
            "assistant_name": ai.get("assistant_name") or "Assistente de IA",
            "default_mode": ai.get("default_mode") or "ai",
            "control_webhook_configured": bool(str(ai.get("control_webhook_url") or "").strip()),
            "control_webhook_enabled": bool(ai.get("control_webhook_enabled")),
            "tickets_ai": ai_mode,
            "tickets_human": human_mode,
            "routing_enabled": bool(ai_routing.get("enabled")),
            "routing_routes": ai_routing.get("routes") or {},
        },
        "dispatches": {
            "enabled": bool(dispatches.get("enabled")),
            "webhook_configured": bool(str(dispatches.get("webhook_url") or "").strip()),
            "template_key": dispatches.get("template_key") or "",
            **dispatch_counts,
        },
    }


def contract_examples(base_url: str) -> dict[str, Any]:
    base = str(base_url or "").rstrip("/")
    return {
        "inbound": {
            "method": "POST",
            "path": "/webhooks/make/whatsapp",
            "url": f"{base}/webhooks/make/whatsapp",
            "payload": '{\n  "phone": "5587999999999",\n  "name": "Cliente Exemplo",\n  "message": "Olá",\n  "external_message_id": "wamid..."\n}',
            "response": '{\n  "ticket_id": "ticket-123",\n  "automation": {\n    "route_to_ai": true,\n    "control_version": 4,\n    "make_instruction": "ROUTE_TO_AI"\n  }\n}',
        },
        "ai_control": {
            "method": "GET",
            "path": "/webhooks/make/ai/control/{ticket_id}",
            "url": f"{base}/webhooks/make/ai/control/{{ticket_id}}",
            "payload": "Header: X-Webhook-Secret: <segredo do bridge>",
            "response": '{\n  "automation": {\n    "connection_state": "connected|disconnected",\n    "route_to_ai": true,\n    "control_version": 4\n  }\n}',
        },
        "ai_reply": {
            "method": "POST",
            "path": "/webhooks/make/ai/reply",
            "url": f"{base}/webhooks/make/ai/reply",
            "payload": '{\n  "ticket_id": "ticket-123",\n  "message": "Resposta da IA",\n  "control_version": 4,\n  "external_message_id": "ai-run-123"\n}',
        },
        "outbox": {
            "method": "GET",
            "path": "/webhooks/make/whatsapp/outbox",
            "url": f"{base}/webhooks/make/whatsapp/outbox",
            "payload": "Header: X-Webhook-Secret: <segredo do bridge>",
        },
        "outbox_status": {
            "method": "POST",
            "path": "/webhooks/make/whatsapp/outbox/{outbox_id}/status",
            "url": f"{base}/webhooks/make/whatsapp/outbox/{{outbox_id}}/status",
            "payload": '{\n  "status": "sent",\n  "provider_message_id": "wamid..."\n}',
        },
        "provider_status": {
            "method": "POST",
            "path": "/webhooks/make/whatsapp/provider-status",
            "url": f"{base}/webhooks/make/whatsapp/provider-status",
            "payload": '{\n  "provider_message_id": "wamid...",\n  "status": "delivered|read|failed",\n  "occurred_at": "timestamp do Meta",\n  "recipient_id": "5587..."\n}',
            "response": '{\n  "accepted": true,\n  "updated": true,\n  "ignored": false,\n  "status": "delivered"\n}',
        },
        "dispatch_status": {
            "method": "POST",
            "path": "/webhooks/make/disparos/{dispatch_id}/status",
            "url": f"{base}/webhooks/make/disparos/{{dispatch_id}}/status",
            "payload": '{\n  "status": "sent",\n  "provider_message_id": "wamid..."\n}',
        },
    }
