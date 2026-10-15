from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.core.ui import templates
from app.dependencies.auth import current_user, internal_user
from app.services.audit_service import record_audit
from app.services.access_service import allowed
from app.services.product_service import KINDS, create_product, get_product, list_products, update_product

router = APIRouter(tags=["produtos"])


def _admin(user: dict) -> dict:
    if not allowed(user, "produtos"):
        raise HTTPException(status_code=403, detail="Sem permissão para alterar o catálogo.")
    return user


def _form_context(request: Request, user: dict, *, product: dict | None = None, error: str | None = None):
    return {
        "user": user,
        "active_page": "products",
        "product": product,
        "kinds": KINDS,
        "error": error,
    }


@router.get("/produtos")
def products_page(
    request: Request,
    q: str | None = None,
    kind: str | None = None,
    status: str = "all",
    user: dict = Depends(current_user),
):
    internal_user(user)
    return templates.TemplateResponse(
        request=request,
        name="products/list.html",
        context={
            "user": user,
            "active_page": "products",
            "products": list_products(search=q, kind=kind, status=status),
            "query": q or "",
            "kind": kind or "",
            "status_filter": status,
            "kinds": KINDS,
            "can_edit": allowed(user, "produtos"),
        },
    )


@router.get("/produtos/novo")
def product_new_page(request: Request, user: dict = Depends(current_user)):
    internal_user(user)
    _admin(user)
    return templates.TemplateResponse(request=request, name="products/form.html", context=_form_context(request, user))


@router.post("/produtos/novo")
def product_create(
    request: Request,
    name: str = Form(...),
    kind: str = Form(...),
    code: str = Form(""),
    description: str = Form(""),
    category: str = Form(""),
    unit: str = Form(""),
    default_price: str = Form("0"),
    user: dict = Depends(current_user),
):
    internal_user(user)
    _admin(user)
    draft = {
        "name": name,
        "kind": kind,
        "code": code,
        "description": description,
        "category": category,
        "unit": unit,
        "default_price": default_price,
        "is_active": True,
    }
    try:
        product = create_product(
            name=name,
            kind=kind,
            code=code,
            description=description,
            category=category,
            unit=unit,
            default_price=default_price,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="products/form.html",
            context=_form_context(request, user, product=draft, error=str(exc)),
            status_code=422,
        )
    record_audit(
        actor_id=user.get("id"),
        entity_type="product",
        entity_id=product["id"],
        action="product.created",
        payload={"kind": product.get("kind"), "code": product.get("code"), "name": product.get("name")},
    )
    return RedirectResponse(url="/produtos?created=1", status_code=303)


@router.get("/produtos/{product_id}/editar")
def product_edit_page(product_id: str, request: Request, user: dict = Depends(current_user)):
    internal_user(user)
    _admin(user)
    product = get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto ou serviço não encontrado.")
    return templates.TemplateResponse(
        request=request,
        name="products/form.html",
        context=_form_context(request, user, product=product),
    )


@router.post("/produtos/{product_id}/editar")
def product_update(
    product_id: str,
    request: Request,
    name: str = Form(...),
    kind: str = Form(...),
    code: str = Form(""),
    description: str = Form(""),
    category: str = Form(""),
    unit: str = Form(""),
    default_price: str = Form("0"),
    is_active: str | None = Form(None),
    user: dict = Depends(current_user),
):
    internal_user(user)
    _admin(user)
    before = get_product(product_id)
    if not before:
        raise HTTPException(status_code=404, detail="Produto ou serviço não encontrado.")
    draft = {
        "id": product_id,
        "name": name,
        "kind": kind,
        "code": code,
        "description": description,
        "category": category,
        "unit": unit,
        "default_price": default_price,
        "is_active": is_active == "true",
    }
    try:
        product = update_product(
            product_id,
            name=name,
            kind=kind,
            code=code,
            description=description,
            category=category,
            unit=unit,
            default_price=default_price,
            is_active=is_active == "true",
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="products/form.html",
            context=_form_context(request, user, product=draft, error=str(exc)),
            status_code=422,
        )
    changed = {
        key: {"from": before.get(key), "to": product.get(key)}
        for key in ("name", "kind", "code", "category", "unit", "default_price", "is_active")
        if before.get(key) != product.get(key)
    }
    record_audit(
        actor_id=user.get("id"),
        entity_type="product",
        entity_id=product_id,
        action="product.updated",
        payload={"changes": changed},
    )
    return RedirectResponse(url="/produtos?updated=1", status_code=303)
