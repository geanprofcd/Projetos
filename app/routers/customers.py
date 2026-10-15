from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.core.ui import templates
from app.core.config import get_settings
from app.dependencies.auth import current_user, internal_user
from app.services.customer_service import create_customer, create_farm, get_customer, get_farm, list_customers, list_farms, update_customer, update_farm
from app.services.audit_service import record_audit
from app.services.opportunity_service import list_opportunities
from app.services.ticket_service import list_tickets_for_customer


router = APIRouter(prefix="/clientes", tags=["clientes"])


def _require_internal(user: dict) -> dict:
    return internal_user(user)


def _parse_area(value: str) -> float | None:
    if not value.strip():
        return None
    try:
        area = float(value.replace(",", "."))
    except ValueError as exc:
        raise ValueError("Área deve ser um número válido.") from exc
    if area < 0:
        raise ValueError("Área não pode ser negativa.")
    return area


@router.get("")
def customers_page(request: Request, q: str | None = None, user: dict = Depends(current_user)):
    _require_internal(user)
    return templates.TemplateResponse(request=request, name="customers/list.html", context={"user": user, "customers": list_customers(q), "query": q or "", "active_page": "customers"})


@router.get("/novo")
def customer_new_page(request: Request, user: dict = Depends(current_user)):
    _require_internal(user)
    return templates.TemplateResponse(request=request, name="customers/form.html", context={"user": user, "customer": None, "error": None, "active_page": "customers"})


@router.post("/novo")
def customer_create(request: Request, name: str = Form(...), phone: str = Form(""), email: str = Form(""), document: str = Form(""), company_name: str = Form(""), user: dict = Depends(current_user)):
    _require_internal(user)
    try:
        customer = create_customer(name=name, phone=phone, email=email, document=document, company_name=company_name)
        record_audit(actor_id=user.get("id"), entity_type="customer", entity_id=customer["id"], action="created", payload={"name": customer.get("name")})
    except ValueError as exc:
        return templates.TemplateResponse(request=request, name="customers/form.html", status_code=422, context={"user": user, "customer": {"name": name, "phone": phone, "email": email, "document": document, "company_name": company_name, "status": "active"}, "error": str(exc), "active_page": "customers"})
    return RedirectResponse(url=f"/clientes/{customer['id']}", status_code=303)


@router.get("/{customer_id}/propriedades.json")
def customer_farms_json(customer_id: str, user: dict = Depends(current_user)):
    _require_internal(user)
    if not get_customer(customer_id):
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    if not get_settings().demo_mode:
        return JSONResponse([])
    return JSONResponse([{"id": farm["id"], "name": farm["name"]} for farm in list_farms(customer_id)])


@router.get("/{customer_id}")
def customer_detail(customer_id: str, request: Request, user: dict = Depends(current_user)):
    _require_internal(user)
    customer = get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return templates.TemplateResponse(request=request, name="customers/detail.html", context={"user": user, "customer": customer, "farms": list_farms(customer_id), "tickets": list_tickets_for_customer(customer_id, user), "opportunities": list_opportunities(customer_id=customer_id), "active_page": "customers"})


@router.get("/{customer_id}/editar")
def customer_edit_page(customer_id: str, request: Request, user: dict = Depends(current_user)):
    _require_internal(user)
    customer = get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return templates.TemplateResponse(request=request, name="customers/form.html", context={"user": user, "customer": customer, "error": None, "active_page": "customers"})


@router.post("/{customer_id}/editar")
def customer_edit(customer_id: str, request: Request, name: str = Form(...), phone: str = Form(""), email: str = Form(""), document: str = Form(""), company_name: str = Form(""), status: str = Form("active"), user: dict = Depends(current_user)):
    _require_internal(user)
    try:
        updated = update_customer(customer_id, name=name, phone=phone, email=email, document=document, company_name=company_name, status=status)
        record_audit(actor_id=user.get("id"), entity_type="customer", entity_id=customer_id, action="updated", payload={"name": updated.get("name"), "status": updated.get("status")})
    except ValueError as exc:
        customer = {"id": customer_id, "name": name, "phone": phone, "email": email, "document": document, "company_name": company_name, "status": status}
        return templates.TemplateResponse(request=request, name="customers/form.html", status_code=422, context={"user": user, "customer": customer, "error": str(exc), "active_page": "customers"})
    return RedirectResponse(url=f"/clientes/{customer_id}", status_code=303)


@router.get("/{customer_id}/propriedades/nova")
def farm_new_page(customer_id: str, request: Request, user: dict = Depends(current_user)):
    if not get_settings().demo_mode:
        raise HTTPException(status_code=410, detail="Módulo de propriedades legado descontinuado no STAGING.")
    _require_internal(user)
    customer = get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return templates.TemplateResponse(
        request=request,
        name="customers/farm_form.html",
        context={"user": user, "customer": customer, "farm": None, "error": None, "active_page": "customers"},
    )


@router.post("/{customer_id}/propriedades")
def farm_create(customer_id: str, request: Request, name: str = Form(...), city: str = Form(""), state: str = Form(""), area_hectares: str = Form(""), user: dict = Depends(current_user)):
    if not get_settings().demo_mode:
        raise HTTPException(status_code=410, detail="Módulo de propriedades legado descontinuado no STAGING.")
    _require_internal(user)
    customer = get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    try:
        area = _parse_area(area_hectares)
        farm = create_farm(customer_id, name=name, city=city, state=state, area_hectares=area)
        record_audit(actor_id=user.get("id"), entity_type="farm", entity_id=farm["id"], action="created", payload={"customer_id": customer_id, "name": farm.get("name")})
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="customers/farm_form.html",
            status_code=422,
            context={
                "user": user,
                "customer": customer,
                "farm": {"name": name, "city": city, "state": state, "area_hectares": area_hectares},
                "error": str(exc),
                "active_page": "customers",
            },
        )
    return RedirectResponse(url=f"/clientes/{customer_id}#propriedades", status_code=303)


@router.get("/{customer_id}/propriedades/{farm_id}/editar")
def farm_edit_page(customer_id: str, farm_id: str, request: Request, user: dict = Depends(current_user)):
    if not get_settings().demo_mode:
        raise HTTPException(status_code=410, detail="Módulo de propriedades legado descontinuado no STAGING.")
    _require_internal(user)
    customer = get_customer(customer_id)
    farm = get_farm(farm_id)
    if not customer or not farm or farm.get("customer_id") != customer_id:
        raise HTTPException(status_code=404, detail="Propriedade não encontrada.")
    return templates.TemplateResponse(request=request, name="customers/farm_form.html", context={"user": user, "customer": customer, "farm": farm, "error": None, "active_page": "customers"})


@router.post("/{customer_id}/propriedades/{farm_id}/editar")
def farm_edit(customer_id: str, farm_id: str, request: Request, name: str = Form(...), city: str = Form(""), state: str = Form(""), area_hectares: str = Form(""), user: dict = Depends(current_user)):
    if not get_settings().demo_mode:
        raise HTTPException(status_code=410, detail="Módulo de propriedades legado descontinuado no STAGING.")
    _require_internal(user)
    customer = get_customer(customer_id)
    farm = get_farm(farm_id)
    if not customer or not farm or farm.get("customer_id") != customer_id:
        raise HTTPException(status_code=404, detail="Propriedade não encontrada.")
    try:
        area = _parse_area(area_hectares)
        updated_farm = update_farm(farm_id, name=name, city=city, state=state, area_hectares=area)
        record_audit(actor_id=user.get("id"), entity_type="farm", entity_id=farm_id, action="updated", payload={"customer_id": customer_id, "name": updated_farm.get("name")})
    except (ValueError, TypeError) as exc:
        return templates.TemplateResponse(request=request, name="customers/farm_form.html", status_code=422, context={"user": user, "customer": customer, "farm": {"id": farm_id, "customer_id": customer_id, "name": name, "city": city, "state": state, "area_hectares": area_hectares}, "error": str(exc), "active_page": "customers"})
    return RedirectResponse(url=f"/clientes/{customer_id}#propriedades", status_code=303)
