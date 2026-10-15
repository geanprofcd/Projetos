from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.customer_service import get_customer
from app.services.demo_store import (
    DEMO_INTERNAL_USERS,
    DEMO_LOST_REASONS,
    DEMO_OPPORTUNITIES,
    DEMO_OPPORTUNITY_ITEMS,
    DEMO_OPPORTUNITY_STAGE_HISTORY,
    DEMO_TICKETS,
    new_id,
)
from app.services.funnel_service import get_funnel, get_stage
from app.services.metadata_service import list_internal_users
from app.services.product_service import get_product, list_products, money_label, money_storage, parse_money

OPPORTUNITY_STATUSES = {"open": "Aberta", "won": "Ganha", "lost": "Perdida"}
MONEY_QUANT = Decimal("0.01")
QUANTITY_QUANT = Decimal("0.0001")


class OpportunityConflictError(ValueError):
    """A oportunidade mudou depois que o quadro foi carregado."""

    def __init__(self, current: dict):
        super().__init__("Esta oportunidade foi alterada por outra ação. Atualize o funil e tente novamente.")
        self.current = current


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _raw_ticket(ticket_id: str | None) -> dict | None:
    if not ticket_id:
        return None
    if get_settings().demo_mode:
        source = next((row for row in DEMO_TICKETS if str(row.get("id")) == str(ticket_id)), None)
        return source.copy() if source else None
    rows = get_admin_client().table("tickets").select("*").eq("id", ticket_id).limit(1).execute().data or []
    return rows[0] if rows else None


def _assignee(assigned_user_id: str | None) -> dict | None:
    if not assigned_user_id:
        return None
    return next((row for row in list_internal_users(active_only=True) if str(row.get("id")) == str(assigned_user_id)), None)


def _date_or_none(value: str | date | None) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value.isoformat()
    clean = str(value).strip()
    if not clean:
        return None
    try:
        date.fromisoformat(clean)
    except ValueError as exc:
        raise ValueError("Data prevista de fechamento inválida.") from exc
    return clean


def parse_quantity(value) -> Decimal:
    raw = str(value or "").strip().replace(" ", "")
    if not raw:
        raise ValueError("Quantidade é obrigatória.")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        quantity = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Quantidade inválida.") from exc
    if quantity <= 0:
        raise ValueError("Quantidade deve ser maior que zero.")
    return quantity.quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)


def quantity_storage(value) -> str:
    return f"{parse_quantity(value):.4f}"


def quantity_label(value) -> str:
    q = parse_quantity(value)
    normalized = format(q.normalize(), "f")
    return normalized.replace(".", ",")


def _item_rows(opportunity_id: str) -> list[dict]:
    if get_settings().demo_mode:
        rows = [row.copy() for row in DEMO_OPPORTUNITY_ITEMS if str(row.get("opportunity_id")) == str(opportunity_id)]
    else:
        rows = (
            get_admin_client().table("opportunity_items").select("*").eq("opportunity_id", opportunity_id).order("line_position").execute().data or []
        )
    rows.sort(key=lambda row: (int(row.get("line_position") or 0), str(row.get("id"))))
    result = []
    for row in rows:
        item = row.copy()
        item["quantity"] = quantity_storage(item.get("quantity"))
        item["quantity_label"] = quantity_label(item.get("quantity"))
        item["unit_price"] = money_storage(item.get("unit_price"))
        item["unit_price_label"] = money_label(item.get("unit_price"))
        item["subtotal"] = money_storage(item.get("subtotal"))
        item["subtotal_label"] = money_label(item.get("subtotal"))
        product = get_product(str(item.get("product_id"))) if item.get("product_id") else None
        item["product_is_active"] = bool(product and product.get("is_active"))
        result.append(item)
    return result


def _raw_opportunity(opportunity_id: str, *, include_archived: bool = True) -> dict | None:
    if get_settings().demo_mode:
        source = next((row for row in DEMO_OPPORTUNITIES if str(row.get("id")) == str(opportunity_id)), None)
        return source.copy() if source else None
    rows = get_admin_client().table("opportunities").select("*").eq("id", opportunity_id).limit(1).execute().data or []
    return rows[0] if rows else None


def _raw_opportunities(*, include_archived: bool = False) -> list[dict]:
    if get_settings().demo_mode:
        rows = [row.copy() for row in DEMO_OPPORTUNITIES]
    else:
        rows = get_admin_client().table("opportunities").select("*").execute().data or []
    if include_archived:
        return rows
    return [row for row in rows if not row.get("archived_at")]


def _stage_history(opportunity_id: str) -> list[dict]:
    if get_settings().demo_mode:
        rows = [row.copy() for row in DEMO_OPPORTUNITY_STAGE_HISTORY if str(row.get("opportunity_id")) == str(opportunity_id)]
    else:
        rows = (
            get_admin_client().table("opportunity_stage_history").select("*").eq("opportunity_id", opportunity_id).order("moved_at", desc=True).execute().data or []
        )
    stages = {}
    for row in rows:
        for key in ("from_stage_id", "to_stage_id"):
            stage_id = row.get(key)
            if stage_id and stage_id not in stages:
                stages[stage_id] = get_stage(str(stage_id))
    users = {str(u.get("id")): u for u in list_internal_users(active_only=False)}
    result = []
    for source in sorted(rows, key=lambda r: str(r.get("moved_at") or ""), reverse=True):
        row = source.copy()
        row["from_stage_name"] = (stages.get(row.get("from_stage_id")) or {}).get("name") or "Entrada no funil"
        row["to_stage_name"] = (stages.get(row.get("to_stage_id")) or {}).get("name") or "Etapa"
        row["moved_by_name"] = (users.get(str(row.get("moved_by"))) or {}).get("full_name") or "Sistema"
        result.append(row)
    return result


def list_lost_reasons(*, active_only: bool = True) -> list[dict]:
    if get_settings().demo_mode:
        rows = [row.copy() for row in DEMO_LOST_REASONS]
    else:
        query = get_admin_client().table("lost_reasons").select("*").order("name")
        if active_only:
            query = query.eq("is_active", True)
        rows = query.execute().data or []
    if active_only:
        rows = [row for row in rows if bool(row.get("is_active", True))]
    return sorted(rows, key=lambda row: (row.get("name") or "").casefold())


def _decorate(row: dict, *, include_items: bool = False, include_history: bool = False) -> dict:
    item = row.copy()
    customer = get_customer(str(item.get("customer_id"))) if item.get("customer_id") else None
    ticket = _raw_ticket(str(item.get("ticket_id"))) if item.get("ticket_id") else None
    funnel = get_funnel(str(item.get("funnel_id"))) if item.get("funnel_id") else None
    stage = get_stage(str(item.get("stage_id"))) if item.get("stage_id") else None
    assignee = _assignee(str(item.get("assigned_user_id"))) if item.get("assigned_user_id") else None
    reason = next((r for r in list_lost_reasons(active_only=False) if str(r.get("id")) == str(item.get("lost_reason_id"))), None)
    item["customer_name"] = (customer or {}).get("name") or "Cliente"
    item["ticket_title"] = (ticket or {}).get("title") or None
    item["funnel_name"] = (funnel or {}).get("name") or "—"
    item["stage_name"] = (stage or {}).get("name") or "—"
    item["stage_color"] = (stage or {}).get("color") or "#94a3b8"
    item["assigned_name"] = (assignee or {}).get("full_name") or "Sem responsável"
    item["status_label"] = OPPORTUNITY_STATUSES.get(item.get("status"), item.get("status") or "—")
    item["lost_reason_name"] = (reason or {}).get("name")
    item["calculated_value"] = money_storage(item.get("calculated_value"))
    item["calculated_value_label"] = money_label(item.get("calculated_value"))
    if item.get("final_value") is not None:
        item["final_value"] = money_storage(item.get("final_value"))
        item["final_value_label"] = money_label(item.get("final_value"))
    else:
        item["final_value_label"] = None
    if include_items:
        item["items"] = _item_rows(str(item["id"]))
        item["item_count"] = len(item["items"])
    else:
        item["item_count"] = sum(1 for r in (_item_rows(str(item["id"]))))
    if include_history:
        item["stage_history"] = _stage_history(str(item["id"]))
    return item


def list_opportunities(*, search: str | None = None, status: str = "all", funnel_id: str | None = None, customer_id: str | None = None, ticket_id: str | None = None) -> list[dict]:
    if status not in {"all", *OPPORTUNITY_STATUSES.keys()}:
        status = "all"
    rows = _raw_opportunities()
    if status != "all":
        rows = [row for row in rows if row.get("status") == status]
    if funnel_id:
        rows = [row for row in rows if str(row.get("funnel_id")) == str(funnel_id)]
    if customer_id:
        rows = [row for row in rows if str(row.get("customer_id")) == str(customer_id)]
    if ticket_id:
        rows = [row for row in rows if str(row.get("ticket_id")) == str(ticket_id)]
    result = [_decorate(row) for row in rows]
    if search:
        needle = search.strip().casefold()
        result = [row for row in result if needle in " ".join(str(row.get(k) or "") for k in ("title", "customer_name", "funnel_name", "stage_name", "assigned_name")).casefold()]
    result.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("created_at") or "")), reverse=True)
    return result


def get_opportunity(opportunity_id: str, *, include_items: bool = True, include_history: bool = True) -> dict | None:
    row = _raw_opportunity(opportunity_id)
    return _decorate(row, include_items=include_items, include_history=include_history) if row else None


def get_ticket_opportunity(ticket_id: str, *, open_only: bool = False) -> dict | None:
    rows = [row for row in _raw_opportunities() if str(row.get("ticket_id")) == str(ticket_id)]
    if open_only:
        rows = [row for row in rows if row.get("status") == "open"]
    if not rows:
        return None
    rows.sort(key=lambda row: (row.get("status") != "open", str(row.get("updated_at") or "")), reverse=False)
    return _decorate(rows[0], include_items=True, include_history=False)


def validate_opportunity_selection(*, customer_id: str, ticket_id: str | None, funnel_id: str, stage_id: str, assigned_user_id: str | None, expected_close_date: str | None = None) -> dict:
    customer = get_customer(customer_id)
    if not customer:
        raise ValueError("Cliente não encontrado.")
    ticket = _raw_ticket(ticket_id)
    if ticket_id and not ticket:
        raise ValueError("Atendimento não encontrado.")
    if ticket and str(ticket.get("customer_id")) != str(customer_id):
        raise ValueError("O atendimento selecionado não pertence ao cliente informado.")
    funnel = get_funnel(funnel_id, include_inactive_stages=True)
    if not funnel:
        raise ValueError("Funil não encontrado.")
    if not bool(funnel.get("is_active", True)):
        raise ValueError("Este funil está inativo e não aceita novas oportunidades.")
    stage = get_stage(stage_id)
    if not stage or str(stage.get("funnel_id")) != str(funnel_id):
        raise ValueError("A etapa selecionada não pertence ao funil informado.")
    if not bool(stage.get("is_active", True)):
        raise ValueError("Esta etapa está inativa e não aceita novas oportunidades.")
    if assigned_user_id and not _assignee(assigned_user_id):
        raise ValueError("Responsável comercial inválido ou inativo.")
    return {
        "customer": customer,
        "ticket": ticket,
        "funnel": funnel,
        "stage": stage,
        "expected_close_date": _date_or_none(expected_close_date),
    }


def _active_for_ticket(ticket_id: str | None, *, ignore_id: str | None = None) -> dict | None:
    if not ticket_id:
        return None
    return next((row for row in _raw_opportunities() if str(row.get("ticket_id")) == str(ticket_id) and row.get("status") == "open" and str(row.get("id")) != str(ignore_id)), None)


def _record_stage_history(*, opportunity_id: str, from_stage_id: str | None, to_stage_id: str, moved_by: str | None, source: str) -> dict:
    payload = {
        "opportunity_id": opportunity_id,
        "from_stage_id": from_stage_id,
        "to_stage_id": to_stage_id,
        "moved_by": moved_by,
        "source": source,
        "moved_at": _now(),
    }
    if get_settings().demo_mode:
        payload["id"] = new_id("opphistory")
        DEMO_OPPORTUNITY_STAGE_HISTORY.append(payload)
        return payload.copy()
    return get_admin_client().table("opportunity_stage_history").insert(payload).execute().data[0]


def create_opportunity(*, title: str, customer_id: str, ticket_id: str | None, funnel_id: str, stage_id: str, assigned_user_id: str | None, expected_close_date: str | None, actor_id: str | None, source: str = "detail") -> dict:
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("Título da oportunidade é obrigatório.")
    if len(clean_title) > 180:
        raise ValueError("Título da oportunidade deve ter no máximo 180 caracteres.")
    valid = validate_opportunity_selection(customer_id=customer_id, ticket_id=ticket_id, funnel_id=funnel_id, stage_id=stage_id, assigned_user_id=assigned_user_id, expected_close_date=expected_close_date)
    if _active_for_ticket(ticket_id):
        raise ValueError("Este atendimento já possui uma oportunidade aberta vinculada.")
    now = _now()
    same_stage_open = [r for r in _raw_opportunities() if r.get("status") == "open" and str(r.get("stage_id")) == str(stage_id)]
    position = max((int(r.get("kanban_position") or 0) for r in same_stage_open), default=0) + 1000
    payload = {
        "customer_id": customer_id,
        "ticket_id": ticket_id or None,
        "title": clean_title,
        "funnel_id": funnel_id,
        "stage_id": stage_id,
        "assigned_user_id": assigned_user_id or None,
        "status": "open",
        "currency_code": "BRL",
        "calculated_value": "0.00",
        "final_value": None,
        "expected_close_date": valid["expected_close_date"],
        "won_at": None,
        "lost_at": None,
        "lost_reason_id": None,
        "lost_notes": None,
        "kanban_position": position,
        "lock_version": 1,
        "archived_at": None,
        "archived_by": None,
        "created_at": now,
        "updated_at": now,
    }
    if get_settings().demo_mode:
        payload["id"] = new_id("opportunity")
        DEMO_OPPORTUNITIES.append(payload)
        row = payload.copy()
    else:
        row = get_admin_client().table("opportunities").insert(payload).execute().data[0]
    _record_stage_history(opportunity_id=str(row["id"]), from_stage_id=None, to_stage_id=stage_id, moved_by=actor_id, source=source)
    return _decorate(row, include_items=True, include_history=True)


def update_opportunity(opportunity_id: str, *, title: str, funnel_id: str, stage_id: str, assigned_user_id: str | None, expected_close_date: str | None, actor_id: str | None, source: str = "detail") -> dict:
    existing = _raw_opportunity(opportunity_id)
    if not existing:
        raise ValueError("Oportunidade não encontrada.")
    if existing.get("status") != "open":
        raise ValueError("Oportunidades ganhas ou perdidas precisam ser reabertas antes de edição comercial.")
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("Título da oportunidade é obrigatório.")
    validate_opportunity_selection(customer_id=str(existing.get("customer_id")), ticket_id=str(existing.get("ticket_id")) if existing.get("ticket_id") else None, funnel_id=funnel_id, stage_id=stage_id, assigned_user_id=assigned_user_id, expected_close_date=expected_close_date)
    old_stage = str(existing.get("stage_id")) if existing.get("stage_id") else None
    payload = {
        "title": clean_title,
        "funnel_id": funnel_id,
        "stage_id": stage_id,
        "assigned_user_id": assigned_user_id or None,
        "expected_close_date": _date_or_none(expected_close_date),
        "lock_version": int(existing.get("lock_version") or 0) + 1,
        "updated_at": _now(),
    }
    if old_stage != str(stage_id):
        same_stage_open = [r for r in _raw_opportunities() if r.get("status") == "open" and str(r.get("stage_id")) == str(stage_id) and str(r.get("id")) != str(opportunity_id)]
        payload["kanban_position"] = max((int(r.get("kanban_position") or 0) for r in same_stage_open), default=0) + 1000
    if get_settings().demo_mode:
        target = next(r for r in DEMO_OPPORTUNITIES if str(r.get("id")) == str(opportunity_id))
        target.update(payload)
        row = target.copy()
    else:
        row = get_admin_client().table("opportunities").update(payload).eq("id", opportunity_id).execute().data[0]
    if old_stage != str(stage_id):
        _record_stage_history(opportunity_id=opportunity_id, from_stage_id=old_stage, to_stage_id=stage_id, moved_by=actor_id, source=source)
    return _decorate(row, include_items=True, include_history=True)


def _recalculate(opportunity_id: str) -> dict:
    existing = _raw_opportunity(opportunity_id)
    if not existing:
        raise ValueError("Oportunidade não encontrada.")
    total = sum((parse_money(row.get("subtotal")) for row in _item_rows(opportunity_id)), Decimal("0.00")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    payload = {"calculated_value": f"{total:.2f}", "updated_at": _now(), "lock_version": int(existing.get("lock_version") or 0) + 1}
    if get_settings().demo_mode:
        target = next(r for r in DEMO_OPPORTUNITIES if str(r.get("id")) == str(opportunity_id))
        target.update(payload)
        row = target.copy()
    else:
        row = get_admin_client().table("opportunities").update(payload).eq("id", opportunity_id).execute().data[0]
    return _decorate(row, include_items=True, include_history=True)


def add_opportunity_item(opportunity_id: str, *, product_id: str, quantity, unit_price=None) -> tuple[dict, dict]:
    opportunity = _raw_opportunity(opportunity_id)
    if not opportunity:
        raise ValueError("Oportunidade não encontrada.")
    if opportunity.get("status") != "open":
        raise ValueError("Itens só podem ser alterados enquanto a oportunidade estiver aberta.")
    product = get_product(product_id)
    if not product:
        raise ValueError("Produto ou serviço não encontrado.")
    if not bool(product.get("is_active", True)):
        raise ValueError("Produto ou serviço inativo não pode ser adicionado a uma nova negociação.")
    qty = parse_quantity(quantity)
    price = parse_money(product.get("default_price") if unit_price in (None, "") else unit_price)
    subtotal = (qty * price).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    existing_rows = _item_rows(opportunity_id)
    payload = {
        "opportunity_id": opportunity_id,
        "product_id": product_id,
        "name_snapshot": product.get("name") or "Item",
        "description_snapshot": product.get("description"),
        "unit_snapshot": product.get("unit"),
        "quantity": f"{qty:.4f}",
        "unit_price": f"{price:.2f}",
        "discount_amount": "0.00",
        "subtotal": f"{subtotal:.2f}",
        "line_position": max((int(r.get("line_position") or 0) for r in existing_rows), default=0) + 1,
        "created_at": _now(),
        "updated_at": _now(),
    }
    if get_settings().demo_mode:
        payload["id"] = new_id("oppitem")
        DEMO_OPPORTUNITY_ITEMS.append(payload)
        item = payload.copy()
    else:
        item = get_admin_client().table("opportunity_items").insert(payload).execute().data[0]
    updated = _recalculate(opportunity_id)
    return _item_rows(opportunity_id)[-1] if get_settings().demo_mode else _decorate_item(item), updated


def _decorate_item(row: dict) -> dict:
    item = row.copy()
    item["quantity"] = quantity_storage(item.get("quantity"))
    item["quantity_label"] = quantity_label(item.get("quantity"))
    item["unit_price"] = money_storage(item.get("unit_price"))
    item["unit_price_label"] = money_label(item.get("unit_price"))
    item["subtotal"] = money_storage(item.get("subtotal"))
    item["subtotal_label"] = money_label(item.get("subtotal"))
    return item


def update_opportunity_item(opportunity_id: str, item_id: str, *, quantity, unit_price) -> tuple[dict, dict]:
    opportunity = _raw_opportunity(opportunity_id)
    if not opportunity:
        raise ValueError("Oportunidade não encontrada.")
    if opportunity.get("status") != "open":
        raise ValueError("Itens só podem ser alterados enquanto a oportunidade estiver aberta.")
    rows = _item_rows(opportunity_id)
    existing = next((row for row in rows if str(row.get("id")) == str(item_id)), None)
    if not existing:
        raise ValueError("Item da oportunidade não encontrado.")
    qty = parse_quantity(quantity)
    price = parse_money(unit_price)
    subtotal = (qty * price).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    payload = {"quantity": f"{qty:.4f}", "unit_price": f"{price:.2f}", "subtotal": f"{subtotal:.2f}", "updated_at": _now()}
    if get_settings().demo_mode:
        target = next(r for r in DEMO_OPPORTUNITY_ITEMS if str(r.get("id")) == str(item_id) and str(r.get("opportunity_id")) == str(opportunity_id))
        target.update(payload)
        item = target.copy()
    else:
        data = get_admin_client().table("opportunity_items").update(payload).eq("id", item_id).eq("opportunity_id", opportunity_id).execute().data or []
        if not data:
            raise ValueError("Item da oportunidade não encontrado.")
        item = data[0]
    updated = _recalculate(opportunity_id)
    return _decorate_item(item), updated


def remove_opportunity_item(opportunity_id: str, item_id: str) -> dict:
    opportunity = _raw_opportunity(opportunity_id)
    if not opportunity:
        raise ValueError("Oportunidade não encontrada.")
    if opportunity.get("status") != "open":
        raise ValueError("Itens só podem ser alterados enquanto a oportunidade estiver aberta.")
    if get_settings().demo_mode:
        index = next((i for i, row in enumerate(DEMO_OPPORTUNITY_ITEMS) if str(row.get("id")) == str(item_id) and str(row.get("opportunity_id")) == str(opportunity_id)), None)
        if index is None:
            raise ValueError("Item da oportunidade não encontrado.")
        DEMO_OPPORTUNITY_ITEMS.pop(index)
    else:
        get_admin_client().table("opportunity_items").delete().eq("id", item_id).eq("opportunity_id", opportunity_id).execute()
    return _recalculate(opportunity_id)


def mark_won(opportunity_id: str) -> dict:
    existing = _raw_opportunity(opportunity_id)
    if not existing:
        raise ValueError("Oportunidade não encontrada.")
    if existing.get("status") != "open":
        raise ValueError("Somente oportunidades abertas podem ser marcadas como ganhas.")
    now = _now()
    payload = {
        "status": "won",
        "final_value": money_storage(existing.get("calculated_value")),
        "won_at": now,
        "lost_at": None,
        "lost_reason_id": None,
        "lost_notes": None,
        "lock_version": int(existing.get("lock_version") or 0) + 1,
        "updated_at": now,
    }
    return _save_status(existing, payload)


def mark_lost(opportunity_id: str, *, lost_reason_id: str, lost_notes: str | None = None) -> dict:
    existing = _raw_opportunity(opportunity_id)
    if not existing:
        raise ValueError("Oportunidade não encontrada.")
    if existing.get("status") != "open":
        raise ValueError("Somente oportunidades abertas podem ser marcadas como perdidas.")
    reason = next((r for r in list_lost_reasons(active_only=True) if str(r.get("id")) == str(lost_reason_id)), None)
    if not reason:
        raise ValueError("Selecione um motivo de perda válido.")
    notes = (lost_notes or "").strip() or None
    if notes and len(notes) > 1200:
        raise ValueError("Observação de perda deve ter no máximo 1200 caracteres.")
    now = _now()
    payload = {
        "status": "lost",
        "final_value": None,
        "won_at": None,
        "lost_at": now,
        "lost_reason_id": lost_reason_id,
        "lost_notes": notes,
        "lock_version": int(existing.get("lock_version") or 0) + 1,
        "updated_at": now,
    }
    return _save_status(existing, payload)


def reopen_opportunity(opportunity_id: str) -> dict:
    existing = _raw_opportunity(opportunity_id)
    if not existing:
        raise ValueError("Oportunidade não encontrada.")
    if existing.get("status") == "open":
        return _decorate(existing, include_items=True, include_history=True)
    if _active_for_ticket(str(existing.get("ticket_id")) if existing.get("ticket_id") else None, ignore_id=opportunity_id):
        raise ValueError("Este atendimento já possui outra oportunidade aberta e não pode reabrir esta negociação.")
    payload = {
        "status": "open",
        "final_value": None,
        "won_at": None,
        "lost_at": None,
        "lost_reason_id": None,
        "lost_notes": None,
        "lock_version": int(existing.get("lock_version") or 0) + 1,
        "updated_at": _now(),
    }
    return _save_status(existing, payload)


def _save_status(existing: dict, payload: dict) -> dict:
    opportunity_id = str(existing["id"])
    if get_settings().demo_mode:
        target = next(r for r in DEMO_OPPORTUNITIES if str(r.get("id")) == opportunity_id)
        target.update(payload)
        row = target.copy()
    else:
        row = get_admin_client().table("opportunities").update(payload).eq("id", opportunity_id).execute().data[0]
    return _decorate(row, include_items=True, include_history=True)



def move_opportunity_stage(
    opportunity_id: str,
    *,
    to_stage_id: str,
    expected_lock_version: int,
    actor_id: str | None,
    source: str = "kanban",
) -> dict:
    """Move uma oportunidade aberta entre etapas do mesmo funil.

    A operação usa lock_version como trava otimista. No Kanban, uma alteração
    concorrente deve resultar em conflito em vez de sobrescrever silenciosamente
    o trabalho de outro usuário.
    """
    existing = _raw_opportunity(opportunity_id)
    if not existing:
        raise ValueError("Oportunidade não encontrada.")
    if existing.get("status") != "open":
        raise ValueError("Somente oportunidades abertas podem ser movidas no funil.")

    current_lock = int(existing.get("lock_version") or 0)
    try:
        expected = int(expected_lock_version)
    except (TypeError, ValueError) as exc:
        raise ValueError("Versão da oportunidade inválida. Atualize o funil e tente novamente.") from exc
    if expected != current_lock:
        raise OpportunityConflictError(_decorate(existing, include_items=False, include_history=False))

    stage = get_stage(to_stage_id)
    if not stage:
        raise ValueError("Etapa de destino não encontrada.")
    if not bool(stage.get("is_active", True)):
        raise ValueError("A etapa de destino está inativa.")
    if str(stage.get("funnel_id")) != str(existing.get("funnel_id")):
        raise ValueError("A etapa de destino não pertence ao funil atual da oportunidade.")

    old_stage = str(existing.get("stage_id") or "")
    if old_stage == str(to_stage_id):
        return _decorate(existing, include_items=False, include_history=False)

    same_stage_open = [
        row for row in _raw_opportunities()
        if row.get("status") == "open"
        and str(row.get("stage_id")) == str(to_stage_id)
        and str(row.get("id")) != str(opportunity_id)
    ]
    new_position = max((int(row.get("kanban_position") or 0) for row in same_stage_open), default=0) + 1000
    now = _now()
    payload = {
        "stage_id": to_stage_id,
        "kanban_position": new_position,
        "lock_version": current_lock + 1,
        "updated_at": now,
    }

    if get_settings().demo_mode:
        target = next(row for row in DEMO_OPPORTUNITIES if str(row.get("id")) == str(opportunity_id))
        # Confere novamente imediatamente antes da escrita para manter a mesma
        # semântica da atualização condicional usada no banco real.
        if int(target.get("lock_version") or 0) != current_lock:
            raise OpportunityConflictError(_decorate(target.copy(), include_items=False, include_history=False))
        target.update(payload)
        row = target.copy()
    else:
        data = (
            get_admin_client()
            .table("opportunities")
            .update(payload)
            .eq("id", opportunity_id)
            .eq("lock_version", current_lock)
            .execute()
            .data
            or []
        )
        if not data:
            latest = _raw_opportunity(opportunity_id)
            if not latest:
                raise ValueError("Oportunidade não encontrada após tentativa de movimentação.")
            raise OpportunityConflictError(_decorate(latest, include_items=False, include_history=False))
        row = data[0]

    _record_stage_history(
        opportunity_id=opportunity_id,
        from_stage_id=old_stage or None,
        to_stage_id=to_stage_id,
        moved_by=actor_id,
        source=source,
    )
    return _decorate(row, include_items=False, include_history=False)



def archive_opportunity(
    opportunity_id: str,
    *,
    expected_lock_version: int,
    actor_id: str | None,
) -> dict:
    """Arquiva um card do funil sem apagar histórico comercial/auditoria."""
    existing = _raw_opportunity(opportunity_id)
    if not existing or existing.get("archived_at"):
        raise ValueError("Oportunidade não encontrada ou já arquivada.")
    if existing.get("status") != "open":
        raise ValueError("Somente oportunidades abertas podem ser excluídas do funil.")

    current_lock = int(existing.get("lock_version") or 0)
    try:
        expected = int(expected_lock_version)
    except (TypeError, ValueError) as exc:
        raise ValueError("Versão da oportunidade inválida. Atualize o funil e tente novamente.") from exc
    if expected != current_lock:
        raise OpportunityConflictError(_decorate(existing, include_items=False, include_history=False))

    payload = {
        "archived_at": _now(),
        "archived_by": actor_id,
        "lock_version": current_lock + 1,
        "updated_at": _now(),
    }
    if get_settings().demo_mode:
        target = next(row for row in DEMO_OPPORTUNITIES if str(row.get("id")) == str(opportunity_id))
        if int(target.get("lock_version") or 0) != current_lock:
            raise OpportunityConflictError(_decorate(target.copy(), include_items=False, include_history=False))
        target.update(payload)
        row = target.copy()
    else:
        data = (
            get_admin_client()
            .table("opportunities")
            .update(payload)
            .eq("id", opportunity_id)
            .eq("lock_version", current_lock)
            .execute()
            .data
            or []
        )
        if not data:
            latest = _raw_opportunity(opportunity_id)
            if latest:
                raise OpportunityConflictError(_decorate(latest, include_items=False, include_history=False))
            raise ValueError("Não foi possível arquivar a oportunidade.")
        row = data[0]
    return _decorate(row, include_items=False, include_history=False)

def commercial_summary() -> dict:
    rows = [_decorate(row) for row in _raw_opportunities()]
    open_rows = [r for r in rows if r.get("status") == "open"]
    won_rows = [r for r in rows if r.get("status") == "won"]
    lost_rows = [r for r in rows if r.get("status") == "lost"]
    open_value = sum((parse_money(r.get("calculated_value")) for r in open_rows), Decimal("0.00"))
    won_value = sum((parse_money(r.get("final_value")) for r in won_rows if r.get("final_value") is not None), Decimal("0.00"))
    return {
        "open_count": len(open_rows),
        "open_value": money_storage(open_value),
        "open_value_label": money_label(open_value),
        "won_count": len(won_rows),
        "won_value": money_storage(won_value),
        "won_value_label": money_label(won_value),
        "lost_count": len(lost_rows),
    }
