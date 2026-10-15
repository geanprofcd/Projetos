from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.services.admin_settings_service import get_ai_routing_settings, get_ai_settings, get_dispatch_settings
from app.services.automation_service import connect_ticket_to_ai, get_ticket_ai_control
from app.services.customer_service import create_customer, find_customer_by_phone, normalize_phone
from app.services.demo_store import DEMO_DISPATCHES, DEMO_INTERNAL_USERS, DEMO_MESSAGES, DEMO_TICKETS, new_id
from app.services.funnel_service import list_funnels
from app.services.opportunity_service import create_opportunity, get_ticket_opportunity

DISPATCH_STATUSES = {"pending", "submitted", "sent", "delivered", "read", "failed", "cancelled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    status = str(result.get("status") or "pending")
    labels = {
        "pending": "Pendente",
        "submitted": "Enviado ao Make",
        "sent": "Enviado",
        "delivered": "Entregue",
        "read": "Lido",
        "failed": "Falhou",
        "cancelled": "Cancelado",
    }
    result["status_label"] = labels.get(status, status)
    return result


def list_dispatches(limit: int = 100) -> list[dict[str, Any]]:
    if not get_settings().demo_mode:
        return []
    rows = sorted(DEMO_DISPATCHES, key=lambda row: row.get("created_at") or "", reverse=True)[: max(1, min(limit, 500))]
    return [_public(row) for row in rows]


def get_dispatch(dispatch_id: str) -> dict[str, Any] | None:
    if not get_settings().demo_mode:
        return None
    row = next((row for row in DEMO_DISPATCHES if str(row.get("id")) == str(dispatch_id)), None)
    return row


def _post_json(url: str, payload: dict[str, Any], *, timeout: float = 7.0) -> tuple[int, str]:
    if get_settings().app_env == "staging":
        raise RuntimeError("Ambiente de homologação: envio externo bloqueado.")
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "VENDRA-Disparos/0.0.9"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        sample = response.read(1024).decode("utf-8", errors="replace")
        return int(getattr(response, "status", 200)), sample


def _new_lead_destination() -> tuple[str, str]:
    """Resolve a etapa inicial do CRM without hardcoding local/demo row IDs.

    Respect a real funnel explicitly named 'Novo Lead' when one exists. In the
    standard VENDRA layout 'Novo lead' is instead a *stage* in 'Funil Comercial'.
    """
    funnels = list_funnels(include_inactive=False)
    named_funnel = next(
        (f for f in funnels if str(f.get("name") or "").strip().casefold() == "novo lead"),
        None,
    )
    if named_funnel:
        active = [stage for stage in named_funnel.get("stages") or [] if stage.get("is_active", True)]
        if not active:
            raise ValueError("O funil 'Novo Lead' não possui etapas ativas para receber Disparos.")
        initial = min(active, key=lambda stage: int(stage.get("position") or 0))
        return str(named_funnel["id"]), str(initial["id"])

    # Default documented mapping: route #1 -> Funil Comercial / Novo lead.
    first_route = ((get_ai_routing_settings().get("routes") or {}).get("1") or {})
    funnel_id, stage_id = str(first_route.get("funnel_id") or ""), str(first_route.get("stage_id") or "")
    for funnel in funnels:
        if str(funnel.get("id")) != funnel_id:
            continue
        for stage in funnel.get("stages") or []:
            if (
                str(stage.get("id")) == stage_id
                and bool(stage.get("is_active", True))
                and str(stage.get("name") or "").strip().casefold() == "novo lead"
            ):
                return funnel_id, stage_id

    matches = [
        (str(funnel["id"]), str(stage["id"]))
        for funnel in funnels
        for stage in funnel.get("stages") or []
        if stage.get("is_active", True)
        and str(stage.get("name") or "").strip().casefold() == "novo lead"
    ]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise ValueError("Há mais de uma etapa 'Novo Lead'. Configure a rota #1 para indicar o funil correto.")
    raise ValueError("Crie uma etapa 'Novo Lead' em um funil ativo antes de realizar Disparos.")


def _ensure_dispatch_new_lead_opportunity(
    *, ticket: dict[str, Any], customer: dict[str, Any], requested_by: str | None,
    funnel_id: str, stage_id: str,
) -> dict[str, Any]:
    """Create the CRM card before Make is called; preserve progressed opportunities."""
    ticket_id = str(ticket["id"])
    existing = get_ticket_opportunity(ticket_id, open_only=True)
    if existing:
        return existing  # Never reset an existing negotiation to the first stage.
    assignee = str(ticket.get("assigned_user_id") or "")
    if not any(str(user.get("id")) == assignee and user.get("status") == "active" for user in DEMO_INTERNAL_USERS):
        assignee = ""
    return create_opportunity(
        title=f"Oportunidade WhatsApp — {customer.get('name') or 'Cliente'}"[:180],
        customer_id=str(customer["id"]),
        ticket_id=ticket_id,
        funnel_id=funnel_id,
        stage_id=stage_id,
        assigned_user_id=assignee or None,
        expected_close_date=None,
        actor_id=requested_by,
        source="dispatch_initial",
    )


def _ensure_demo_whatsapp_ticket(*, customer: dict[str, Any], name: str, requested_by: str | None, template_key: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    open_ticket = next(
        (
            ticket
            for ticket in sorted(DEMO_TICKETS, key=lambda row: row.get("updated_at") or "", reverse=True)
            if str(ticket.get("customer_id")) == str(customer.get("id"))
            and ticket.get("source") == "whatsapp"
            and ticket.get("status") not in {"finalizado", "cancelado"}
        ),
        None,
    )
    now = _now()
    if not open_ticket:
        open_ticket = {
            "id": new_id("ticket"),
            "title": f"Contato iniciado por Disparos — {name}"[:120],
            "customer_id": str(customer.get("id")),
            "farm_id": None,
            "crop_id": None,
            "category_id": None,
            "assigned_user_id": requested_by,
            "status": "novo",
            "priority": "normal",
            "source": "whatsapp",
            "whatsapp_active_at": now,
            "created_at": now,
            "updated_at": now,
            "closed_at": None,
        }
        DEMO_TICKETS.append(open_ticket)
    else:
        open_ticket["updated_at"] = now
        open_ticket["whatsapp_active_at"] = now

    sender = next((u for u in DEMO_INTERNAL_USERS if str(u.get("id")) == str(requested_by)), None)
    template_label = template_key or "mensagem pré-configurada no Make"
    message = {
        "id": new_id("message"),
        "ticket_id": str(open_ticket.get("id")),
        "sender_id": requested_by,
        "sender_name": (sender or {}).get("full_name") or "Disparo VENDRA",
        "sender_kind": "system",
        "body": f"Disparo iniciado pelo VENDRA · {template_label}",
        "channel": "whatsapp",
        "direction": "outbound",
        "is_internal": False,
        "external_message_id": None,
        "delivery_status": "pending",
        "created_at": now,
    }
    DEMO_MESSAGES.setdefault(str(open_ticket.get("id")), []).append(message)
    return open_ticket, message


def create_dispatch(*, name: str, phone: str, requested_by: str | None) -> dict[str, Any]:
    config = get_dispatch_settings()
    if not config.get("enabled"):
        raise ValueError("O canal de Disparos está desativado em Configurações.")
    webhook_url = str(config.get("webhook_url") or "").strip()
    if not webhook_url:
        raise ValueError("Configure o webhook do Make para Disparos antes de enviar.")
    name = str(name or "").strip()[:160]
    normalized = normalize_phone(phone)
    if not name:
        raise ValueError("Informe o nome do cliente.")
    if not normalized:
        raise ValueError("Informe um telefone válido com DDI e DDD.")
    if not get_settings().demo_mode:
        raise ValueError("Disparos no Supabase real ainda dependem da migration desta camada.")

    # Fail before sending to Make if there is no valid initial CRM destination.
    funnel_id, stage_id = _new_lead_destination()

    customer = find_customer_by_phone(phone)
    if not customer:
        customer = create_customer(name=name, phone=phone)

    template_key = str(config.get("template_key") or "").strip() or None
    ticket, message = _ensure_demo_whatsapp_ticket(
        customer=customer,
        name=name,
        requested_by=requested_by,
        template_key=template_key,
    )
    opportunity = _ensure_dispatch_new_lead_opportunity(
        ticket=ticket,
        customer=customer,
        requested_by=requested_by,
        funnel_id=funnel_id,
        stage_id=stage_id,
    )
    # O disparo é o início de uma conversa ativa. Quando a IA global está ligada,
    # este ticket volta a entrar no fluxo automático até um humano desconectá-lo.
    if get_ai_settings().get("enabled"):
        connect_ticket_to_ai(
            str(ticket.get("id")),
            actor_id=requested_by,
            source="dispatch_start",
        )
    now = _now()
    row = {
        "id": new_id("dispatch"),
        "customer_id": str(customer.get("id")),
        "ticket_id": str(ticket.get("id")),
        "message_id": str(message.get("id")),
        "opportunity_id": str(opportunity.get("id")),
        "name": name,
        "phone": normalized,
        "status": "pending",
        "template_key": template_key,
        "idempotency_key": f"vendra-dispatch-{uuid4().hex}",
        "requested_by": requested_by,
        "provider_message_id": None,
        "last_error": None,
        "make_status_code": None,
        "make_response": None,
        "created_at": now,
        "updated_at": now,
    }
    DEMO_DISPATCHES.append(row)

    automation = get_ticket_ai_control(str(ticket.get("id")))
    payload = {
        "event": "whatsapp.dispatch.requested",
        "dispatch_id": str(row["id"]),
        "name": name,
        "phone": normalized,
        "customer_id": str(customer.get("id")),
        "ticket_id": str(ticket.get("id")),
        "template_key": row.get("template_key"),
        "idempotency_key": row["idempotency_key"],
        "requested_at": now,
        "requested_by": requested_by,
        "source": "vendra",
        "automation": {
            "connected": bool(automation.get("connected")),
            "route_to_ai": bool(automation.get("route_to_ai")),
            "control_version": int(automation.get("control_version") or 1),
        },
    }
    try:
        status, sample = _post_json(webhook_url, payload)
        row["make_status_code"] = status
        row["make_response"] = sample[:1000]
        row["updated_at"] = _now()
        if 200 <= status < 300:
            row["status"] = "submitted"
        else:
            row["status"] = "failed"
            row["last_error"] = f"Make respondeu HTTP {status}."
            message["delivery_status"] = "failed"
    except urllib.error.HTTPError as exc:
        sample = exc.read(1024).decode("utf-8", errors="replace")
        row["make_status_code"] = int(exc.code)
        row["make_response"] = sample[:1000]
        row["status"] = "failed"
        row["last_error"] = f"Make respondeu HTTP {exc.code}."
        message["delivery_status"] = "failed"
        row["updated_at"] = _now()
    except Exception as exc:
        row["status"] = "failed"
        row["last_error"] = str(exc)[:1000]
        message["delivery_status"] = "failed"
        row["updated_at"] = _now()
    return _public(row)


def retry_dispatch(dispatch_id: str, *, requested_by: str | None) -> dict[str, Any]:
    row = get_dispatch(dispatch_id)
    if not row:
        raise ValueError("Disparo não encontrado.")
    if row.get("status") not in {"failed", "cancelled"}:
        raise ValueError("Somente disparos com falha ou cancelados podem ser reenviados manualmente.")
    config = get_dispatch_settings()
    webhook_url = str(config.get("webhook_url") or "").strip()
    if not config.get("enabled") or not webhook_url:
        raise ValueError("O canal de Disparos está desativado ou sem webhook configurado.")
    ticket_id = str(row.get("ticket_id") or "")
    if ticket_id:
        ticket = next((item for item in DEMO_TICKETS if str(item.get("id")) == ticket_id), None)
        if ticket:
            ticket["whatsapp_active_at"] = _now()
            ticket["updated_at"] = _now()
        if get_ai_settings().get("enabled"):
            connect_ticket_to_ai(ticket_id, actor_id=requested_by, source="dispatch_retry")
        automation = get_ticket_ai_control(ticket_id)
    else:
        automation = {"connected": False, "route_to_ai": False, "control_version": 1}
    payload = {
        "event": "whatsapp.dispatch.requested",
        "dispatch_id": str(row["id"]),
        "name": row.get("name"),
        "phone": row.get("phone"),
        "customer_id": row.get("customer_id"),
        "ticket_id": row.get("ticket_id"),
        "template_key": row.get("template_key"),
        "idempotency_key": row.get("idempotency_key"),
        "requested_at": row.get("created_at"),
        "requested_by": requested_by,
        "source": "vendra",
        "retry": True,
        "automation": {
            "connected": bool(automation.get("connected")),
            "route_to_ai": bool(automation.get("route_to_ai")),
            "control_version": int(automation.get("control_version") or 1),
        },
    }
    try:
        status, sample = _post_json(webhook_url, payload)
        row["make_status_code"] = status
        row["make_response"] = sample[:1000]
        row["updated_at"] = _now()
        row["last_error"] = None
        row["status"] = "submitted" if 200 <= status < 300 else "failed"
        message_id = str(row.get("message_id") or "")
        ticket_id = str(row.get("ticket_id") or "")
        message = next((item for item in DEMO_MESSAGES.get(ticket_id, []) if str(item.get("id")) == message_id), None) if message_id and ticket_id else None
        if 200 <= status < 300:
            if message:
                message["delivery_status"] = "pending"
        else:
            row["last_error"] = f"Make respondeu HTTP {status}."
            if message:
                message["delivery_status"] = "failed"
    except Exception as exc:
        row["status"] = "failed"
        row["last_error"] = str(exc)[:1000]
        row["updated_at"] = _now()
        message_id = str(row.get("message_id") or "")
        ticket_id = str(row.get("ticket_id") or "")
        message = next((item for item in DEMO_MESSAGES.get(ticket_id, []) if str(item.get("id")) == message_id), None) if message_id and ticket_id else None
        if message:
            message["delivery_status"] = "failed"
    return _public(row)


def update_dispatch_status(*, dispatch_id: str, status: str, provider_message_id: str | None = None, error_message: str | None = None) -> dict[str, Any]:
    status = str(status or "").strip().lower()
    if status not in DISPATCH_STATUSES - {"pending"}:
        raise ValueError("Status de disparo inválido.")
    row = get_dispatch(dispatch_id)
    if not row:
        raise ValueError("Disparo não encontrado.")
    row["status"] = status
    if provider_message_id:
        row["provider_message_id"] = str(provider_message_id)[:500]
    if error_message:
        row["last_error"] = str(error_message)[:1000]
    elif status != "failed":
        row["last_error"] = None
    row["updated_at"] = _now()
    message_id = str(row.get("message_id") or "")
    ticket_id = str(row.get("ticket_id") or "")
    if message_id and ticket_id:
        message = next((item for item in DEMO_MESSAGES.get(ticket_id, []) if str(item.get("id")) == message_id), None)
        if message:
            message["delivery_status"] = status
            if provider_message_id:
                message["external_message_id"] = str(provider_message_id)[:500]
            message["external_status_updated_at"] = _now()
    return _public(row)
