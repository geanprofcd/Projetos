from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.core.ui import templates
from app.dependencies.auth import current_user
from app.services.audit_service import record_audit
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services.funnel_service import (
    create_funnel,
    create_stage,
    get_funnel,
    get_stage,
    list_funnels,
    move_stage,
    update_funnel,
    update_stage,
)

router = APIRouter(tags=["funis"])


def _admin(user: dict) -> dict:
    if user.get("role") != "administrador":
        raise HTTPException(status_code=403, detail="Apenas administradores podem configurar funis.")
    return user


def _csrf(request: Request) -> str:
    return csrf_token_for_session(request.cookies.get(COOKIE_NAME))


def _require_csrf(request: Request, supplied: str) -> None:
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME), supplied):
        raise HTTPException(status_code=403, detail="Token de segurança inválido. Atualize a página e tente novamente.")


def _detail_context(request: Request, user: dict, funnel: dict, *, error: str | None = None, stage_error: str | None = None):
    return {
        "user": user,
        "active_page": "settings",
        "funnel": funnel,
        "error": error,
        "stage_error": stage_error,
        "csrf_token": _csrf(request),
    }


@router.get("/configuracoes/funis")
def funnels_page(request: Request, user: dict = Depends(current_user)):
    _admin(user)
    return templates.TemplateResponse(
        request=request,
        name="funnels/list.html",
        context={
            "user": user,
            "active_page": "settings",
            "funnels": list_funnels(include_inactive=True),
            "csrf_token": _csrf(request),
        },
    )


@router.get("/configuracoes/funis/novo")
def funnel_new_page(request: Request, user: dict = Depends(current_user)):
    _admin(user)
    return templates.TemplateResponse(
        request=request,
        name="funnels/form.html",
        context={"user": user, "active_page": "settings", "funnel": None, "error": None, "csrf_token": _csrf(request)},
    )


@router.post("/configuracoes/funis/novo")
def funnel_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _admin(user)
    _require_csrf(request, csrf_token)
    try:
        funnel = create_funnel(name=name, description=description)
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="funnels/form.html",
            context={
                "user": user,
                "active_page": "settings",
                "funnel": {"name": name, "description": description, "is_active": True},
                "error": str(exc),
                "csrf_token": _csrf(request),
            },
            status_code=422,
        )
    record_audit(actor_id=user.get("id"), entity_type="sales_funnel", entity_id=funnel["id"], action="sales_funnel.created", payload={"name": funnel.get("name")})
    return RedirectResponse(url=f"/configuracoes/funis/{funnel['id']}?created=1", status_code=303)


@router.get("/configuracoes/funis/{funnel_id}")
def funnel_detail(funnel_id: str, request: Request, user: dict = Depends(current_user)):
    _admin(user)
    funnel = get_funnel(funnel_id)
    if not funnel:
        raise HTTPException(status_code=404, detail="Funil não encontrado.")
    return templates.TemplateResponse(request=request, name="funnels/detail.html", context=_detail_context(request, user, funnel))


@router.post("/configuracoes/funis/{funnel_id}/editar")
def funnel_update(
    funnel_id: str,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    is_active: str | None = Form(None),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _admin(user)
    _require_csrf(request, csrf_token)
    before = get_funnel(funnel_id)
    if not before:
        raise HTTPException(status_code=404, detail="Funil não encontrado.")
    try:
        funnel = update_funnel(funnel_id, name=name, description=description, is_active=is_active == "true")
    except ValueError as exc:
        draft = before.copy()
        draft.update({"name": name, "description": description, "is_active": is_active == "true"})
        return templates.TemplateResponse(request=request, name="funnels/detail.html", context=_detail_context(request, user, draft, error=str(exc)), status_code=422)
    changed = {key: {"from": before.get(key), "to": funnel.get(key)} for key in ("name", "description", "is_active") if before.get(key) != funnel.get(key)}
    record_audit(actor_id=user.get("id"), entity_type="sales_funnel", entity_id=funnel_id, action="sales_funnel.updated", payload={"changes": changed})
    return RedirectResponse(url=f"/configuracoes/funis/{funnel_id}?updated=1", status_code=303)


@router.post("/configuracoes/funis/{funnel_id}/etapas/nova")
def stage_create(
    funnel_id: str,
    request: Request,
    name: str = Form(...),
    color: str = Form("#3157d5"),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _admin(user)
    _require_csrf(request, csrf_token)
    funnel = get_funnel(funnel_id)
    if not funnel:
        raise HTTPException(status_code=404, detail="Funil não encontrado.")
    try:
        stage = create_stage(funnel_id=funnel_id, name=name, color=color)
    except ValueError as exc:
        return templates.TemplateResponse(request=request, name="funnels/detail.html", context=_detail_context(request, user, funnel, stage_error=str(exc)), status_code=422)
    record_audit(actor_id=user.get("id"), entity_type="funnel_stage", entity_id=stage["id"], action="funnel_stage.created", payload={"funnel_id": funnel_id, "name": stage.get("name"), "position": stage.get("position")})
    return RedirectResponse(url=f"/configuracoes/funis/{funnel_id}?stage_created=1", status_code=303)


@router.get("/configuracoes/funis/{funnel_id}/etapas/{stage_id}/editar")
def stage_edit_page(funnel_id: str, stage_id: str, request: Request, user: dict = Depends(current_user)):
    _admin(user)
    funnel = get_funnel(funnel_id)
    stage = get_stage(stage_id)
    if not funnel or not stage or str(stage.get("funnel_id")) != funnel_id:
        raise HTTPException(status_code=404, detail="Etapa não encontrada neste funil.")
    return templates.TemplateResponse(
        request=request,
        name="funnels/stage_form.html",
        context={"user": user, "active_page": "settings", "funnel": funnel, "stage": stage, "error": None, "csrf_token": _csrf(request)},
    )


@router.post("/configuracoes/funis/{funnel_id}/etapas/{stage_id}/editar")
def stage_update(
    funnel_id: str,
    stage_id: str,
    request: Request,
    name: str = Form(...),
    color: str = Form("#3157d5"),
    is_active: str | None = Form(None),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _admin(user)
    _require_csrf(request, csrf_token)
    before = get_stage(stage_id)
    funnel = get_funnel(funnel_id)
    if not funnel or not before or str(before.get("funnel_id")) != funnel_id:
        raise HTTPException(status_code=404, detail="Etapa não encontrada neste funil.")
    try:
        stage = update_stage(stage_id, name=name, color=color, is_active=is_active == "true")
    except ValueError as exc:
        draft = before.copy()
        draft.update({"name": name, "color": color, "is_active": is_active == "true"})
        return templates.TemplateResponse(
            request=request,
            name="funnels/stage_form.html",
            context={"user": user, "active_page": "settings", "funnel": funnel, "stage": draft, "error": str(exc), "csrf_token": _csrf(request)},
            status_code=422,
        )
    changed = {key: {"from": before.get(key), "to": stage.get(key)} for key in ("name", "color", "is_active") if before.get(key) != stage.get(key)}
    record_audit(actor_id=user.get("id"), entity_type="funnel_stage", entity_id=stage_id, action="funnel_stage.updated", payload={"funnel_id": funnel_id, "changes": changed})
    return RedirectResponse(url=f"/configuracoes/funis/{funnel_id}?stage_updated=1", status_code=303)


@router.post("/configuracoes/funis/{funnel_id}/etapas/{stage_id}/mover")
def stage_move(
    funnel_id: str,
    stage_id: str,
    request: Request,
    direction: str = Form(...),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _admin(user)
    _require_csrf(request, csrf_token)
    before = get_stage(stage_id)
    if not before or str(before.get("funnel_id")) != funnel_id:
        raise HTTPException(status_code=404, detail="Etapa não encontrada neste funil.")
    try:
        stage = move_stage(stage_id, direction=direction)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if int(stage.get("position") or 0) != int(before.get("position") or 0):
        record_audit(actor_id=user.get("id"), entity_type="funnel_stage", entity_id=stage_id, action="funnel_stage.reordered", payload={"funnel_id": funnel_id, "from": before.get("position"), "to": stage.get("position")})
    return RedirectResponse(url=f"/configuracoes/funis/{funnel_id}?reordered=1", status_code=303)
