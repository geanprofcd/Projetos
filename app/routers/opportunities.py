from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.core.ui import templates
from app.dependencies.auth import current_user, internal_user
from app.services.audit_service import record_audit
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services.customer_service import get_customer, list_customers
from app.services.funnel_service import get_funnel, list_funnels
from app.services.metadata_service import list_internal_users
from app.services.opportunity_service import (
    OPPORTUNITY_STATUSES,
    add_opportunity_item,
    commercial_summary,
    create_opportunity,
    get_opportunity,
    list_lost_reasons,
    list_opportunities,
    mark_lost,
    mark_won,
    remove_opportunity_item,
    reopen_opportunity,
    update_opportunity,
    update_opportunity_item,
    validate_opportunity_selection,
)
from app.services.product_service import list_products
from app.services.ticket_service import create_ticket, get_ticket

router = APIRouter(tags=["oportunidades"])


def _csrf(request: Request) -> str:
    return csrf_token_for_session(request.cookies.get(COOKIE_NAME))


def _require_csrf(request: Request, supplied: str) -> None:
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME), supplied):
        raise HTTPException(status_code=403, detail="Token de segurança inválido. Atualize a página e tente novamente.")


def _internal(user: dict) -> dict:
    return internal_user(user)


def _form_context(request: Request, user: dict, *, draft: dict | None = None, ticket: dict | None = None, customer: dict | None = None, error: str | None = None):
    funnels = list_funnels(include_inactive=False)
    return {
        "user": user,
        "active_page": "tickets",
        "draft": draft or {},
        "ticket": ticket,
        "selected_customer": customer,
        "customers": list_customers(include_inactive=False),
        "funnels": funnels,
        "responsibles": list_internal_users(),
        "error": error,
        "csrf_token": _csrf(request),
    }


def _detail_context(request: Request, user: dict, opportunity_id: str, **extra):
    opportunity = get_opportunity(opportunity_id, include_items=True, include_history=False)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada.")
    context = {
        "user": user,
        "active_page": "tickets",
        "opportunity": opportunity,
        "funnels": list_funnels(include_inactive=True),
        "responsibles": list_internal_users(),
        "products": list_products(status="active"),
        "lost_reasons": list_lost_reasons(active_only=True),
        "csrf_token": _csrf(request),
        "error": None,
        "item_error": None,
        "status_error": None,
    }
    context.update(extra)
    return context


@router.get("/oportunidades")
def opportunities_page(
    request: Request,
    q: str | None = None,
    status: str = "all",
    funnel_id: str | None = None,
    user: dict = Depends(current_user),
):
    _internal(user)
    return templates.TemplateResponse(
        request=request,
        name="opportunities/list.html",
        context={
            "user": user,
            "active_page": "tickets",
            "opportunities": list_opportunities(search=q, status=status, funnel_id=funnel_id),
            "summary": commercial_summary(),
            "statuses": OPPORTUNITY_STATUSES,
            "funnels": list_funnels(include_inactive=True),
            "query": q or "",
            "status_filter": status,
            "funnel_filter": funnel_id or "",
        },
    )


@router.get("/oportunidades/nova")
def opportunity_new_page(request: Request, cliente: str | None = None, atendimento: str | None = None, user: dict = Depends(current_user)):
    _internal(user)
    ticket = get_ticket(atendimento, user) if atendimento else None
    customer_id = str(ticket.get("customer_id")) if ticket else cliente
    customer = get_customer(customer_id) if customer_id else None
    default_funnel = next((f for f in list_funnels(include_inactive=False) if f.get("stages")), None)
    default_stage = next((s for s in (default_funnel or {}).get("stages", []) if s.get("is_active", True)), None)
    draft = {
        "customer_id": customer_id or "",
        "ticket_id": atendimento or "",
        "title": (ticket or {}).get("title") or "",
        "funnel_id": (default_funnel or {}).get("id") or "",
        "stage_id": (default_stage or {}).get("id") or "",
        "assigned_user_id": (ticket or {}).get("assigned_user_id") or user.get("id") or "",
        "expected_close_date": "",
    }
    return templates.TemplateResponse(request=request, name="opportunities/form.html", context=_form_context(request, user, draft=draft, ticket=ticket, customer=customer))


@router.post("/oportunidades/nova")
def opportunity_create(
    request: Request,
    title: str = Form(...),
    customer_id: str = Form(...),
    ticket_id: str = Form(""),
    funnel_id: str = Form(...),
    stage_id: str = Form(...),
    assigned_user_id: str = Form(""),
    expected_close_date: str = Form(""),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _internal(user)
    _require_csrf(request, csrf_token)
    draft = {
        "title": title, "customer_id": customer_id, "ticket_id": ticket_id, "funnel_id": funnel_id,
        "stage_id": stage_id, "assigned_user_id": assigned_user_id, "expected_close_date": expected_close_date,
    }
    ticket = get_ticket(ticket_id, user) if ticket_id else None
    customer = get_customer(customer_id)
    try:
        validate_opportunity_selection(
            customer_id=customer_id,
            ticket_id=ticket_id or None,
            funnel_id=funnel_id,
            stage_id=stage_id,
            assigned_user_id=assigned_user_id or None,
            expected_close_date=expected_close_date or None,
        )
        if not ticket_id:
            created_ticket = create_ticket(
                user=user,
                title=title,
                customer_id=customer_id,
                farm_id=None,
                crop_id=None,
                category_id=None,
                assigned_user_id=assigned_user_id or user.get("id"),
                status="em_atendimento",
                priority="normal",
                source="interno",
            )
            ticket_id = str(created_ticket["id"])
            ticket = created_ticket
        opportunity = create_opportunity(
            title=title,
            customer_id=customer_id,
            ticket_id=ticket_id or None,
            funnel_id=funnel_id,
            stage_id=stage_id,
            assigned_user_id=assigned_user_id or user.get("id"),
            expected_close_date=expected_close_date or None,
            actor_id=user.get("id"),
            source="detail",
        )
    except (ValueError, PermissionError) as exc:
        return templates.TemplateResponse(
            request=request,
            name="opportunities/form.html",
            status_code=422,
            context=_form_context(request, user, draft=draft, ticket=ticket, customer=customer, error=str(exc)),
        )
    record_audit(
        actor_id=user.get("id"), entity_type="opportunity", entity_id=opportunity["id"], action="opportunity_created",
        payload={"customer_id": customer_id, "ticket_id": opportunity.get("ticket_id"), "funnel_id": funnel_id, "stage_id": stage_id, "assigned_user_id": opportunity.get("assigned_user_id")},
    )
    return RedirectResponse(url=f"/oportunidades/{opportunity['id']}?created=1", status_code=303)


@router.get("/oportunidades/{opportunity_id}")
def opportunity_detail(opportunity_id: str, request: Request, user: dict = Depends(current_user)):
    _internal(user)
    return templates.TemplateResponse(request=request, name="opportunities/detail.html", context=_detail_context(request, user, opportunity_id))


@router.post("/oportunidades/{opportunity_id}/editar")
def opportunity_update(
    opportunity_id: str,
    request: Request,
    title: str = Form(...),
    funnel_id: str = Form(...),
    stage_id: str = Form(...),
    assigned_user_id: str = Form(""),
    expected_close_date: str = Form(""),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _internal(user)
    _require_csrf(request, csrf_token)
    before = get_opportunity(opportunity_id)
    if not before:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada.")
    try:
        after = update_opportunity(
            opportunity_id,
            title=title,
            funnel_id=funnel_id,
            stage_id=stage_id,
            assigned_user_id=assigned_user_id or None,
            expected_close_date=expected_close_date or None,
            actor_id=user.get("id"),
            source="detail",
        )
    except ValueError as exc:
        return templates.TemplateResponse(request=request, name="opportunities/detail.html", status_code=422, context=_detail_context(request, user, opportunity_id, error=str(exc)))
    changed = {key: {"from": before.get(key), "to": after.get(key)} for key in ("title", "funnel_id", "stage_id", "assigned_user_id", "expected_close_date") if before.get(key) != after.get(key)}
    record_audit(actor_id=user.get("id"), entity_type="opportunity", entity_id=opportunity_id, action="opportunity_updated", payload={"changes": changed})
    if before.get("stage_id") != after.get("stage_id"):
        record_audit(actor_id=user.get("id"), entity_type="opportunity", entity_id=opportunity_id, action="opportunity_stage_changed", payload={"from_stage_id": before.get("stage_id"), "to_stage_id": after.get("stage_id"), "source": "detail", "lock_version": after.get("lock_version")})
    return RedirectResponse(url=f"/oportunidades/{opportunity_id}?updated=1", status_code=303)


@router.post("/oportunidades/{opportunity_id}/itens")
def opportunity_item_add(
    opportunity_id: str,
    request: Request,
    product_id: str = Form(...),
    quantity: str = Form("1"),
    unit_price: str = Form(""),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _internal(user)
    _require_csrf(request, csrf_token)
    try:
        item, opportunity = add_opportunity_item(opportunity_id, product_id=product_id, quantity=quantity, unit_price=unit_price or None)
    except ValueError as exc:
        return templates.TemplateResponse(request=request, name="opportunities/detail.html", status_code=422, context=_detail_context(request, user, opportunity_id, item_error=str(exc)))
    record_audit(actor_id=user.get("id"), entity_type="opportunity", entity_id=opportunity_id, action="opportunity_item_added", payload={"item_id": item.get("id"), "product_id": item.get("product_id"), "quantity": item.get("quantity"), "unit_price": item.get("unit_price"), "subtotal": item.get("subtotal"), "calculated_value": opportunity.get("calculated_value")})
    return RedirectResponse(url=f"/oportunidades/{opportunity_id}?item_added=1#itens", status_code=303)


@router.post("/oportunidades/{opportunity_id}/itens/{item_id}/editar")
def opportunity_item_update(
    opportunity_id: str,
    item_id: str,
    request: Request,
    quantity: str = Form(...),
    unit_price: str = Form(...),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _internal(user)
    _require_csrf(request, csrf_token)
    try:
        item, opportunity = update_opportunity_item(opportunity_id, item_id, quantity=quantity, unit_price=unit_price)
    except ValueError as exc:
        return templates.TemplateResponse(request=request, name="opportunities/detail.html", status_code=422, context=_detail_context(request, user, opportunity_id, item_error=str(exc)))
    record_audit(actor_id=user.get("id"), entity_type="opportunity", entity_id=opportunity_id, action="opportunity_item_updated", payload={"item_id": item_id, "product_id": item.get("product_id"), "quantity": item.get("quantity"), "unit_price": item.get("unit_price"), "subtotal": item.get("subtotal"), "calculated_value": opportunity.get("calculated_value")})
    return RedirectResponse(url=f"/oportunidades/{opportunity_id}?item_updated=1#itens", status_code=303)


@router.post("/oportunidades/{opportunity_id}/itens/{item_id}/remover")
def opportunity_item_remove(
    opportunity_id: str,
    item_id: str,
    request: Request,
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _internal(user)
    _require_csrf(request, csrf_token)
    try:
        opportunity = remove_opportunity_item(opportunity_id, item_id)
    except ValueError as exc:
        return templates.TemplateResponse(request=request, name="opportunities/detail.html", status_code=422, context=_detail_context(request, user, opportunity_id, item_error=str(exc)))
    record_audit(actor_id=user.get("id"), entity_type="opportunity", entity_id=opportunity_id, action="opportunity_item_removed", payload={"item_id": item_id, "calculated_value": opportunity.get("calculated_value")})
    return RedirectResponse(url=f"/oportunidades/{opportunity_id}?item_removed=1#itens", status_code=303)


@router.post("/oportunidades/{opportunity_id}/ganhar")
def opportunity_win(opportunity_id: str, request: Request, csrf_token: str = Form(...), user: dict = Depends(current_user)):
    _internal(user)
    _require_csrf(request, csrf_token)
    try:
        opportunity = mark_won(opportunity_id)
    except ValueError as exc:
        return templates.TemplateResponse(request=request, name="opportunities/detail.html", status_code=422, context=_detail_context(request, user, opportunity_id, status_error=str(exc)))
    record_audit(actor_id=user.get("id"), entity_type="opportunity", entity_id=opportunity_id, action="opportunity_won", payload={"final_value": opportunity.get("final_value"), "stage_id": opportunity.get("stage_id"), "won_at": opportunity.get("won_at")})
    return RedirectResponse(url=f"/oportunidades/{opportunity_id}?won=1", status_code=303)


@router.post("/oportunidades/{opportunity_id}/perder")
def opportunity_loss(
    opportunity_id: str,
    request: Request,
    lost_reason_id: str = Form(...),
    lost_notes: str = Form(""),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _internal(user)
    _require_csrf(request, csrf_token)
    try:
        opportunity = mark_lost(opportunity_id, lost_reason_id=lost_reason_id, lost_notes=lost_notes)
    except ValueError as exc:
        return templates.TemplateResponse(request=request, name="opportunities/detail.html", status_code=422, context=_detail_context(request, user, opportunity_id, status_error=str(exc)))
    record_audit(actor_id=user.get("id"), entity_type="opportunity", entity_id=opportunity_id, action="opportunity_lost", payload={"lost_reason_id": opportunity.get("lost_reason_id"), "lost_at": opportunity.get("lost_at")})
    return RedirectResponse(url=f"/oportunidades/{opportunity_id}?lost=1", status_code=303)


@router.post("/oportunidades/{opportunity_id}/reabrir")
def opportunity_reopen(opportunity_id: str, request: Request, csrf_token: str = Form(...), user: dict = Depends(current_user)):
    _internal(user)
    _require_csrf(request, csrf_token)
    before = get_opportunity(opportunity_id)
    if not before:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada.")
    try:
        opportunity = reopen_opportunity(opportunity_id)
    except ValueError as exc:
        return templates.TemplateResponse(request=request, name="opportunities/detail.html", status_code=422, context=_detail_context(request, user, opportunity_id, status_error=str(exc)))
    record_audit(actor_id=user.get("id"), entity_type="opportunity", entity_id=opportunity_id, action="opportunity_reopened", payload={"previous_status": before.get("status"), "stage_id": opportunity.get("stage_id")})
    return RedirectResponse(url=f"/oportunidades/{opportunity_id}?reopened=1", status_code=303)
