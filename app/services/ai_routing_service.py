from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.admin_settings_service import get_ai_routing_settings
from app.services.customer_service import get_customer
from app.services.demo_store import DEMO_TICKETS
from app.services.funnel_service import get_funnel, get_stage
from app.services.opportunity_service import (
    OpportunityConflictError,
    create_opportunity,
    list_opportunities,
    move_opportunity_stage,
    update_opportunity,
)

ROUTE_CODES = {"1", "2", "3"}


def normalize_route_code(value: str | int | None) -> str | None:
    if value is None:
        return None
    clean = str(value).strip().replace("#", "")
    return clean if clean in ROUTE_CODES else None


def _ticket(ticket_id: str) -> dict | None:
    if get_settings().demo_mode:
        row = next((item for item in DEMO_TICKETS if str(item.get("id")) == str(ticket_id)), None)
        return row.copy() if row else None
    rows = get_admin_client().table("tickets").select("*").eq("id", ticket_id).limit(1).execute().data or []
    return rows[0] if rows else None


def route_contract() -> dict[str, Any]:
    settings = get_ai_routing_settings()
    routes: dict[str, Any] = {}
    for code in sorted(ROUTE_CODES):
        configured = (settings.get("routes") or {}).get(code) or {}
        funnel = get_funnel(str(configured.get("funnel_id"))) if configured.get("funnel_id") else None
        stage = get_stage(str(configured.get("stage_id"))) if configured.get("stage_id") else None
        routes[code] = {
            "configured": bool(funnel and stage and str(stage.get("funnel_id")) == str(funnel.get("id"))),
            "funnel_id": str(configured.get("funnel_id") or ""),
            "funnel_name": (funnel or {}).get("name"),
            "stage_id": str(configured.get("stage_id") or ""),
            "stage_name": (stage or {}).get("name"),
        }
    return {
        "enabled": bool(settings.get("enabled")),
        "routes": routes,
        "updated_at": settings.get("updated_at"),
        "source": settings.get("source") or "configured",
    }


def apply_ai_route(*, ticket_id: str, route_code: str | int | None) -> dict[str, Any]:
    code = normalize_route_code(route_code)
    if not code:
        return {"applied": False, "reason": "route_code_absent_or_invalid", "route_code": None}

    settings = get_ai_routing_settings()
    if not settings.get("enabled"):
        return {"applied": False, "reason": "routing_disabled", "route_code": code}

    mapping = (settings.get("routes") or {}).get(code) or {}
    funnel_id = str(mapping.get("funnel_id") or "")
    stage_id = str(mapping.get("stage_id") or "")
    if not funnel_id or not stage_id:
        return {"applied": False, "reason": "route_not_configured", "route_code": code}

    funnel = get_funnel(funnel_id)
    stage = get_stage(stage_id)
    if not funnel or not stage or str(stage.get("funnel_id")) != funnel_id:
        return {"applied": False, "reason": "route_target_invalid", "route_code": code}
    if not bool(funnel.get("is_active", True)) or not bool(stage.get("is_active", True)):
        return {"applied": False, "reason": "route_target_inactive", "route_code": code}

    ticket = _ticket(ticket_id)
    if not ticket:
        return {"applied": False, "reason": "ticket_not_found", "route_code": code}
    customer_id = str(ticket.get("customer_id") or "")
    if not customer_id:
        return {"applied": False, "reason": "ticket_without_customer", "route_code": code}

    existing = list_opportunities(status="open", ticket_id=str(ticket_id))
    opportunity = existing[0] if existing else None
    customer = get_customer(customer_id)
    customer_name = (customer or {}).get("name") or "Cliente"

    if not opportunity:
        created = create_opportunity(
            title=f"Oportunidade WhatsApp — {customer_name}"[:180],
            customer_id=customer_id,
            ticket_id=str(ticket_id),
            funnel_id=funnel_id,
            stage_id=stage_id,
            assigned_user_id=str(ticket.get("assigned_user_id")) if ticket.get("assigned_user_id") else None,
            expected_close_date=None,
            actor_id=None,
            source=f"ai_route_{code}",
        )
        return {
            "applied": True,
            "action": "created",
            "route_code": code,
            "opportunity_id": str(created.get("id")),
            "funnel_id": funnel_id,
            "stage_id": stage_id,
            "funnel_name": created.get("funnel_name"),
            "stage_name": created.get("stage_name"),
        }

    if str(opportunity.get("funnel_id")) != funnel_id:
        updated = update_opportunity(
            str(opportunity.get("id")),
            title=str(opportunity.get("title") or f"Oportunidade WhatsApp — {customer_name}"),
            funnel_id=funnel_id,
            stage_id=stage_id,
            assigned_user_id=str(opportunity.get("assigned_user_id")) if opportunity.get("assigned_user_id") else None,
            expected_close_date=opportunity.get("expected_close_date"),
            actor_id=None,
            source=f"ai_route_{code}",
        )
        action = "moved_funnel"
    elif str(opportunity.get("stage_id")) != stage_id:
        try:
            updated = move_opportunity_stage(
                str(opportunity.get("id")),
                to_stage_id=stage_id,
                expected_lock_version=int(opportunity.get("lock_version") or 0),
                actor_id=None,
                source=f"ai_route_{code}",
            )
        except OpportunityConflictError as exc:
            return {
                "applied": False,
                "reason": "opportunity_conflict",
                "route_code": code,
                "opportunity_id": str((exc.current or {}).get("id") or opportunity.get("id")),
            }
        action = "moved_stage"
    else:
        updated = opportunity
        action = "already_in_stage"

    return {
        "applied": True,
        "action": action,
        "route_code": code,
        "opportunity_id": str(updated.get("id")),
        "funnel_id": funnel_id,
        "stage_id": stage_id,
        "funnel_name": updated.get("funnel_name") or funnel.get("name"),
        "stage_name": updated.get("stage_name") or stage.get("name"),
    }
