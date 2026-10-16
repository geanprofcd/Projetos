from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.customer_service import get_customer, get_farm
from app.services.attachment_service import enrich_attachment, list_attachments_for_messages
from app.services.metadata_service import list_internal_users
from app.services.demo_store import (
    DEMO_AUDIT_LOG,
    DEMO_CATEGORIES,
    DEMO_CROPS,
    DEMO_CUSTOMERS,
    DEMO_FARMS,
    DEMO_INTERNAL_USERS,
    DEMO_MESSAGES,
    DEMO_TICKETS,
    DEMO_WHATSAPP_OUTBOX,
    new_id,
)

TICKET_STATUSES = (
    "novo",
    "em_atendimento",
    "aguardando_cliente",
    "aguardando_interno",
    "aguardando_orcamento",
    "finalizado",
    "cancelado",
)

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "novo": {"em_atendimento", "cancelado"},
    "em_atendimento": {"aguardando_cliente", "aguardando_interno", "aguardando_orcamento", "finalizado", "cancelado"},
    "aguardando_cliente": {"em_atendimento", "finalizado", "cancelado"},
    "aguardando_interno": {"em_atendimento", "aguardando_orcamento", "finalizado", "cancelado"},
    "aguardando_orcamento": {"em_atendimento", "finalizado", "cancelado"},
    "finalizado": {"em_atendimento"},
    "cancelado": {"novo"},
}


def status_options(current: str) -> list[str]:
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    return [value for value in TICKET_STATUSES if value == current or value in allowed]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _demo_map(rows: list[dict]) -> dict[str, str]:
    return {row["id"]: row.get("name") or row.get("full_name") or row["id"] for row in rows}


def _customer_rows(ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    if get_settings().demo_mode:
        return {row["id"]: row["name"] for row in DEMO_CUSTOMERS if row["id"] in ids}
    response = get_admin_client().table("customers").select("id,name").in_("id", list(ids)).execute()
    return {row["id"]: row["name"] for row in (response.data or [])}


def _profile_names(ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    if get_settings().demo_mode:
        return {row["id"]: row["full_name"] for row in DEMO_INTERNAL_USERS if row["id"] in ids}
    response = get_admin_client().table("profiles").select("id,full_name").in_("id", list(ids)).execute()
    return {row["id"]: row["full_name"] for row in (response.data or [])}


def _farm_names(ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    if get_settings().demo_mode:
        return {row["id"]: row["name"] for row in DEMO_FARMS if row["id"] in ids}
    return {}  # No farms table in the clean VENDRA schema.


def _crop_names(ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    if get_settings().demo_mode:
        return {row["id"]: row["name"] for row in DEMO_CROPS if row["id"] in ids}
    return {}  # No crops table in the clean VENDRA schema.


def _category_names(ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    if get_settings().demo_mode:
        return {row["id"]: row["name"] for row in DEMO_CATEGORIES if row["id"] in ids}
    return {}  # No categories table in the clean VENDRA schema.


def _customer_ids_for_user(user: dict) -> list[str]:
    if user.get("role") != "agronomo":
        return []
    if get_settings().demo_mode:
        return [row["id"] for row in DEMO_CUSTOMERS if row.get("profile_id") == user.get("id")]
    rows = get_admin_client().table("customers").select("id").eq("profile_id", user["id"]).execute().data or []
    return [row["id"] for row in rows]


def _enrich(rows: list[dict]) -> list[dict]:
    customer_ids = {r["customer_id"] for r in rows if r.get("customer_id")}
    profile_ids = {r["assigned_user_id"] for r in rows if r.get("assigned_user_id")}
    farm_ids = {r["farm_id"] for r in rows if r.get("farm_id")}
    crop_ids = {r["crop_id"] for r in rows if r.get("crop_id")}
    category_ids = {r["category_id"] for r in rows if r.get("category_id")}
    customers = _customer_rows(customer_ids)
    profiles = _profile_names(profile_ids)
    farms = _farm_names(farm_ids)
    crops = _crop_names(crop_ids)
    categories = _category_names(category_ids)
    for row in rows:
        row["customer_name"] = customers.get(row.get("customer_id"), "Cliente")
        row["assigned_name"] = profiles.get(row.get("assigned_user_id"))
        row["farm_name"] = farms.get(row.get("farm_id"), "—")
        row["crop_name"] = crops.get(row.get("crop_id"), "—")
        row["category_name"] = categories.get(row.get("category_id"), "—")
    return rows


def list_tickets(user: dict, limit: int = 100) -> list[dict]:
    from app.services.conversation_order_service import list_ticket_rows
    customer_ids = _customer_ids_for_user(user) if user.get('role')=='agronomo' else None
    if customer_ids == []:
        return []
    return _enrich(list_ticket_rows(customer_ids=customer_ids,limit=limit))


def list_tickets_for_customer(customer_id: str, user: dict, limit: int = 30) -> list[dict]:
    if user.get("role") == "agronomo" and customer_id not in set(_customer_ids_for_user(user)):
        return []
    from app.services.conversation_order_service import list_ticket_rows
    return _enrich(list_ticket_rows(customer_ids=[customer_id],limit=limit))


def get_ticket(ticket_id: str, user: dict) -> dict | None:
    if get_settings().demo_mode:
        row = next((t.copy() for t in DEMO_TICKETS if t["id"] == ticket_id), None)
    else:
        data = get_admin_client().table("tickets").select("*").eq("id", ticket_id).limit(1).execute().data or []
        row = data[0] if data else None
    if not row:
        return None
    if user.get("role") == "agronomo" and row.get("customer_id") not in set(_customer_ids_for_user(user)):
        return None
    return _enrich([row])[0]


def _audit(actor_id: str | None, entity_type: str, entity_id: str, action: str, payload: dict) -> None:
    record = {"actor_id": actor_id, "entity_type": entity_type, "entity_id": entity_id, "action": action, "payload": payload, "created_at": _now()}
    if get_settings().demo_mode:
        DEMO_AUDIT_LOG.append(record)
        return
    try:
        get_admin_client().table("audit_log").insert(record).execute()
    except Exception:
        # Auditoria nunca deve impedir o fluxo operacional; a ausência da migration aparece no health/validação.
        pass


def _validate_assignee(assigned_user_id: str | None) -> None:
    if not assigned_user_id:
        return
    eligible = {row["id"] for row in list_internal_users(active_only=True)}
    if assigned_user_id not in eligible:
        raise ValueError("Responsável selecionado não é um usuário interno ativo.")


def create_ticket(*, user: dict, title: str, customer_id: str, farm_id: str | None, crop_id: str | None, category_id: str | None, assigned_user_id: str | None, status: str, priority: str, source: str) -> dict:
    if user.get("role") not in {"responsavel", "administrador"}:
        raise PermissionError("Somente a equipe interna pode criar atendimentos.")
    customer = get_customer(customer_id)
    if not customer:
        raise ValueError("Cliente não encontrado.")
    if not get_settings().demo_mode and (farm_id or crop_id or category_id):
        raise ValueError("Campos agronômicos não são utilizados no VENDRA-STAGING.")
    if farm_id:
        farm = get_farm(farm_id)
        if not farm or farm.get("customer_id") != customer_id:
            raise ValueError("A propriedade não pertence ao cliente selecionado.")
    _validate_assignee(assigned_user_id)
    if status not in TICKET_STATUSES:
        raise ValueError("Status inválido.")
    if priority not in {"baixa", "normal", "alta", "urgente"}:
        raise ValueError("Prioridade inválida.")
    if source not in {"portal", "whatsapp", "interno"}:
        raise ValueError("Origem inválida.")
    payload = {
        "title": title.strip(), "customer_id": customer_id, "farm_id": farm_id or None, "crop_id": crop_id or None,
        "category_id": category_id or None, "assigned_user_id": assigned_user_id or None, "status": status,
        "priority": priority, "source": source, "updated_at": _now(), "closed_at": _now() if status in {"finalizado", "cancelado"} else None,
    }
    if not payload["title"]:
        raise ValueError("Assunto do atendimento é obrigatório.")
    if get_settings().demo_mode:
        payload.update({"id": new_id("ticket"), "created_at": _now()})
        DEMO_TICKETS.append(payload)
        ticket = payload.copy()
    else:
        ticket = get_admin_client().table("tickets").insert(payload).execute().data[0]
    _audit(user.get("id"), "ticket", ticket["id"], "created", {"status": status, "assigned_user_id": assigned_user_id})
    return _enrich([ticket])[0]



def claim_ticket_on_open(ticket_id: str, user: dict) -> dict:
    """Assign an unowned ticket to the first internal user who opens it.

    The claim is write-once while ``assigned_user_id`` is empty. A second user
    opening the same attendance never steals ownership. In real mode the update
    is conditional on ``assigned_user_id IS NULL`` so concurrent opens are safe.
    """
    if user.get("role") not in {"responsavel", "administrador"}:
        ticket = get_ticket(ticket_id, user)
        if not ticket:
            raise ValueError("Atendimento não encontrado.")
        return ticket

    ticket = get_ticket(ticket_id, user)
    if not ticket:
        raise ValueError("Atendimento não encontrado.")
    if ticket.get("assigned_user_id"):
        return ticket

    assigned_user_id = str(user.get("id") or "").strip()
    if not assigned_user_id:
        return ticket
    _validate_assignee(assigned_user_id)

    payload = {"assigned_user_id": assigned_user_id, "updated_at": _now()}
    if ticket.get("status") == "novo":
        payload["status"] = "em_atendimento"

    changed = False
    if get_settings().demo_mode:
        target = next((t for t in DEMO_TICKETS if str(t.get("id")) == str(ticket_id)), None)
        if not target:
            raise ValueError("Atendimento não encontrado.")
        if not target.get("assigned_user_id"):
            target.update(payload)
            changed = True
            result = target.copy()
        else:
            result = target.copy()
    else:
        admin = get_admin_client()
        updated = (
            admin.table("tickets")
            .update(payload)
            .eq("id", ticket_id)
            .is_("assigned_user_id", "null")
            .execute()
            .data
            or []
        )
        if updated:
            changed = True
            result = updated[0]
        else:
            current = admin.table("tickets").select("*").eq("id", ticket_id).limit(1).execute().data or []
            if not current:
                raise ValueError("Atendimento não encontrado.")
            result = current[0]

    if changed:
        _audit(user.get("id"), "ticket", ticket_id, "auto_assigned_on_open", payload)
    return _enrich([result])[0]

def assign_ticket(ticket_id: str, user: dict, assigned_user_id: str | None) -> dict:
    if user.get("role") not in {"responsavel", "administrador"}:
        raise PermissionError("Sem permissão para atribuir atendimento.")
    ticket = get_ticket(ticket_id, user)
    if not ticket:
        raise ValueError("Atendimento não encontrado.")
    _validate_assignee(assigned_user_id)
    new_status = "em_atendimento" if assigned_user_id and ticket["status"] == "novo" else ticket["status"]
    payload = {"assigned_user_id": assigned_user_id or None, "status": new_status, "updated_at": _now()}
    if get_settings().demo_mode:
        target = next(t for t in DEMO_TICKETS if t["id"] == ticket_id)
        target.update(payload)
        result = target.copy()
    else:
        result = get_admin_client().table("tickets").update(payload).eq("id", ticket_id).execute().data[0]
    _audit(user.get("id"), "ticket", ticket_id, "assigned", payload)
    return _enrich([result])[0]


def change_status(ticket_id: str, user: dict, new_status: str) -> dict:
    if user.get("role") not in {"responsavel", "administrador"}:
        raise PermissionError("Sem permissão para alterar status.")
    ticket = get_ticket(ticket_id, user)
    if not ticket:
        raise ValueError("Atendimento não encontrado.")
    current = ticket["status"]
    if new_status == current:
        return ticket
    if new_status not in TICKET_STATUSES or new_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Transição de {current.replace('_', ' ')} para {new_status.replace('_', ' ')} não permitida.")
    payload = {"status": new_status, "updated_at": _now(), "closed_at": _now() if new_status in {"finalizado", "cancelado"} else None}
    if get_settings().demo_mode:
        target = next(t for t in DEMO_TICKETS if t["id"] == ticket_id)
        target.update(payload)
        result = target.copy()
    else:
        result = get_admin_client().table("tickets").update(payload).eq("id", ticket_id).execute().data[0]
    _audit(user.get("id"), "ticket", ticket_id, "status_changed", {"from": current, "to": new_status})
    return _enrich([result])[0]


def list_messages(ticket_id: str, user: dict) -> list[dict]:
    hide_internal = user.get("role") == "agronomo"
    if get_settings().demo_mode:
        rows = [row.copy() for row in DEMO_MESSAGES.get(ticket_id, []) if not (hide_internal and row.get("is_internal"))]
    else:
        fields = "id,sender_id,body,channel,direction,is_internal,external_message_id,delivery_status,external_status_updated_at,created_at"
        if getattr(get_settings(), 'whatsapp_persistent_control_enabled', False):
            fields += ',sender_kind'
        query = get_admin_client().table("messages").select(fields).eq("ticket_id", ticket_id)
        if hide_internal:
            query = query.eq("is_internal", False)
        rows = query.order("created_at").execute().data or []
        profiles = _profile_names({r["sender_id"] for r in rows if r.get("sender_id")})
        customer_ids = {r["sender_id"] for r in rows if r.get("sender_id") and r["sender_id"] not in profiles}
        customers = _customer_rows(customer_ids)
        ticket_rows = get_admin_client().table("tickets").select("customer_id").eq("id", ticket_id).limit(1).execute().data or []
        ticket_customer = None
        if ticket_rows and ticket_rows[0].get("customer_id"):
            ticket_customer = _customer_rows({ticket_rows[0]["customer_id"]}).get(ticket_rows[0]["customer_id"])
        for row in rows:
            if row.get('sender_kind') == 'ai':
                row['sender_name'] = 'Assistente de IA'
            else:
                row["sender_name"] = profiles.get(row.get("sender_id")) or customers.get(row.get("sender_id")) or (
                    'Equipe' if row.get('direction') == 'outbound' and getattr(
                        get_settings(), 'whatsapp_persistent_control_enabled', False) else ticket_customer or 'WhatsApp/Cliente')

    message_ids = [str(row["id"]) for row in rows if row.get("id")]
    delivery_errors: dict[str, str] = {}
    if message_ids:
        if get_settings().demo_mode:
            for item in DEMO_WHATSAPP_OUTBOX:
                message_id = str(item.get("message_id") or "")
                if message_id in message_ids and item.get("last_error"):
                    delivery_errors[message_id] = str(item.get("last_error"))[:1000]
        else:
            outbox_rows = (
                get_admin_client()
                .table("whatsapp_outbox")
                .select("message_id,last_error,status")
                .in_("message_id", message_ids)
                .execute()
                .data
                or []
            )
            for item in outbox_rows:
                if item.get("last_error"):
                    delivery_errors[str(item.get("message_id"))] = str(item.get("last_error"))[:1000]

    attachment_map = list_attachments_for_messages(message_ids)
    for row in rows:
        message_id = str(row.get("id") or "")
        row["delivery_error"] = delivery_errors.get(message_id)
        row["attachments"] = [enrich_attachment(item, ticket_id) for item in attachment_map.get(message_id, [])]
    return rows


def add_message(ticket_id: str, user: dict, body: str, is_internal: bool = False, allow_empty: bool = False) -> dict:
    body = body.strip()
    if not body and not allow_empty:
        raise ValueError("Digite uma mensagem ou selecione ao menos um anexo.")
    ticket = get_ticket(ticket_id, user)
    if not ticket:
        raise ValueError("Atendimento não encontrado.")
    payload = {"ticket_id": ticket_id, "sender_id": user["id"], "body": body, "channel": "internal", "direction": "outbound" if user.get("role") != "agronomo" else "inbound", "is_internal": is_internal, "created_at": _now()}
    if (not get_settings().demo_mode and getattr(get_settings(), 'whatsapp_persistent_control_enabled', False)
            and ticket.get('source') == 'whatsapp' and not is_internal):
        payload.update(channel='whatsapp',sender_kind='human')
    if get_settings().demo_mode:
        payload.update({"id": new_id("message"), "sender_name": user["full_name"]})
        DEMO_MESSAGES.setdefault(ticket_id, []).append(payload)
        next(t for t in DEMO_TICKETS if t["id"] == ticket_id)["updated_at"] = _now()
        message = payload.copy()
    else:
        message = get_admin_client().table("messages").insert({k: v for k, v in payload.items() if k != "created_at"}).execute().data[0]
        get_admin_client().table("tickets").update({"updated_at": _now()}).eq("id", ticket_id).execute()
    _audit(user.get("id"), "ticket", ticket_id, "internal_note" if is_internal else "message_sent", {"has_body": bool(body)})
    return message


def dashboard_metrics(user: dict) -> dict:
    tickets = list_tickets(user)
    counts = Counter(t["status"] for t in tickets)
    return {
        "total": len(tickets),
        "novos": counts.get("novo", 0),
        "em_atendimento": counts.get("em_atendimento", 0),
        "aguardando": counts.get("aguardando_cliente", 0) + counts.get("aguardando_interno", 0) + counts.get("aguardando_orcamento", 0),
        "recent": tickets[:5],
    }


def delete_message_after_failed_upload(ticket_id: str, message_id: str) -> None:
    """Rollback técnico usado apenas quando o upload falha após criar a mensagem."""
    if get_settings().demo_mode:
        DEMO_MESSAGES[ticket_id] = [row for row in DEMO_MESSAGES.get(ticket_id, []) if str(row.get("id")) != str(message_id)]
        return
    get_admin_client().table("messages").delete().eq("id", message_id).eq("ticket_id", ticket_id).execute()
