from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse

from app.core.ui import templates
from app.dependencies.auth import current_user, internal_user
from app.services.admin_settings_service import get_dispatch_settings
from app.services.audit_service import record_audit
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services.dispatch_import_service import (
    MAX_UPLOAD_BYTES,
    SUPPORTED_EXTENSIONS,
    dispatch_import_item,
    get_import_batch,
    import_contact_file,
    list_import_batches,
    list_import_items,
    get_bulk_dispatch_state,
    start_bulk_dispatch,
)
from app.services.dispatch_service import create_dispatch, list_dispatches, retry_dispatch

router = APIRouter(prefix="/disparos", tags=["disparos"])


def _csrf(request: Request) -> str:
    return csrf_token_for_session(request.cookies.get(COOKIE_NAME))


def _require_csrf(request: Request, supplied: str) -> None:
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME), supplied):
        raise HTTPException(status_code=403, detail="Token de segurança inválido. Atualize a página e tente novamente.")


def _require_dispatch_access(user: dict) -> None:
    internal_user(user)
    if user.get("role") not in {"responsavel", "administrador"}:
        raise HTTPException(status_code=403, detail="Acesso restrito à equipe comercial.")


def _page_context(
    request: Request,
    user: dict,
    *,
    list_id: str | None = None,
    success: str | None = None,
    error: str | None = None,
    form: dict | None = None,
) -> dict:
    batches = list_import_batches(30)
    selected = get_import_batch(list_id)
    if not selected and batches:
        selected = batches[0]
    selected_id = str(selected.get("id")) if selected else None
    import_items = list_import_items(selected_id) if selected_id else []
    ready_count = sum(1 for item in import_items if item.get("status") == "ready")
    bulk_state = get_bulk_dispatch_state(selected_id) if selected_id else {"status": "idle", "total": 0, "processed": 0, "failed": 0, "remaining": 0, "percent": 0}
    return {
        "user": user,
        "active_page": "dispatches",
        "rows": list_dispatches(200),
        "settings": get_dispatch_settings(),
        "csrf_token": _csrf(request),
        "success": success,
        "error": error,
        "form": form,
        "import_batches": batches,
        "selected_batch": selected,
        "import_items": import_items,
        "ready_count": ready_count,
        "bulk_state": bulk_state,
        "supported_imports": ", ".join(sorted(ext.lstrip(".").upper() for ext in SUPPORTED_EXTENSIONS)),
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
    }


@router.get("")
def dispatches_page(
    request: Request,
    sent: int | None = None,
    failed: int | None = None,
    imported: int | None = None,
    bulk: int | None = None,
    list: str | None = None,  # noqa: A002 - query string intentionally named list
    user: dict = Depends(current_user),
):
    _require_dispatch_access(user)
    success = None
    error = None
    if imported:
        success = "Lista importada. Revise os contatos antes do envio."
    elif bulk:
        success = "Envio em lote iniciado. Os contatos prontos serão encaminhados um por um ao Make."
    elif sent:
        success = "Solicitação enviada ao Make."
    elif failed:
        error = "O Make não confirmou o disparo. Consulte o histórico abaixo."
    return templates.TemplateResponse(
        request=request,
        name="dispatches/list.html",
        context=_page_context(request, user, list_id=list, success=success, error=error),
    )


@router.post("")
def dispatch_create(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _require_dispatch_access(user)
    _require_csrf(request, csrf_token)
    try:
        row = create_dispatch(name=name, phone=phone, requested_by=str(user.get("id") or "") or None)
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="dispatches/list.html",
            status_code=422,
            context=_page_context(request, user, error=str(exc), form={"name": name, "phone": phone}),
        )
    record_audit(
        actor_id=user.get("id"),
        entity_type="dispatch",
        entity_id=str(row.get("id")),
        action="dispatch_requested",
        payload={
            "customer_id": row.get("customer_id"),
            "phone": row.get("phone"),
            "status": row.get("status"),
            "template_key": row.get("template_key"),
            "origin": "manual",
        },
    )
    return RedirectResponse(url=f"/disparos?{'sent=1' if row.get('status') != 'failed' else 'failed=1'}", status_code=303)


@router.post("/importar")
async def dispatch_import_contacts(
    request: Request,
    arquivo: UploadFile = File(...),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _require_dispatch_access(user)
    _require_csrf(request, csrf_token)
    filename = arquivo.filename or "lista"
    content = await arquivo.read(MAX_UPLOAD_BYTES + 1)
    try:
        batch = import_contact_file(
            filename=filename,
            content=content,
            imported_by=str(user.get("id") or "") or None,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="dispatches/list.html",
            status_code=422,
            context=_page_context(request, user, error=str(exc)),
        )
    record_audit(
        actor_id=user.get("id"),
        entity_type="dispatch_import_batch",
        entity_id=str(batch.get("id")),
        action="contacts_imported",
        payload={
            "filename": batch.get("filename"),
            "total_count": batch.get("total_count"),
            "valid_count": batch.get("valid_count"),
            "invalid_count": batch.get("invalid_count"),
            "duplicate_count": batch.get("duplicate_count"),
        },
    )
    return RedirectResponse(url=f"/disparos?imported=1&list={batch.get('id')}#lista-importada", status_code=303)


@router.post("/listas/{batch_id}/contatos/{item_id}/disparar")
def dispatch_import_contact(
    batch_id: str,
    item_id: str,
    request: Request,
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _require_dispatch_access(user)
    _require_csrf(request, csrf_token)
    batch = get_import_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lista importada não encontrada.")
    try:
        result = dispatch_import_item(item_id=item_id, requested_by=str(user.get("id") or "") or None)
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="dispatches/list.html",
            status_code=422,
            context=_page_context(request, user, list_id=batch_id, error=str(exc)),
        )
    row = result.get("dispatch") or {}
    record_audit(
        actor_id=user.get("id"),
        entity_type="dispatch_import_item",
        entity_id=item_id,
        action="dispatch_requested_from_list",
        payload={
            "batch_id": batch_id,
            "dispatch_id": row.get("id"),
            "phone": row.get("phone"),
            "status": row.get("status"),
            "already_requested": bool(result.get("already_requested")),
        },
    )
    flag = "sent=1" if row.get("status") != "failed" else "failed=1"
    return RedirectResponse(url=f"/disparos?list={batch_id}&{flag}#lista-importada", status_code=303)


@router.post("/listas/{batch_id}/enviar-todos")
def dispatch_import_bulk_start(
    batch_id: str,
    request: Request,
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _require_dispatch_access(user)
    _require_csrf(request, csrf_token)
    if not get_import_batch(batch_id):
        raise HTTPException(status_code=404, detail="Lista importada não encontrada.")
    try:
        state = start_bulk_dispatch(batch_id=batch_id, requested_by=str(user.get("id") or "") or None)
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="dispatches/list.html",
            status_code=422,
            context=_page_context(request, user, list_id=batch_id, error=str(exc)),
        )
    record_audit(
        actor_id=user.get("id"),
        entity_type="dispatch_import_batch",
        entity_id=batch_id,
        action="bulk_dispatch_started",
        payload={
            "total": state.get("total"),
            "status": state.get("status"),
        },
    )
    return RedirectResponse(url=f"/disparos?list={batch_id}&bulk=1#lista-importada", status_code=303)


@router.get("/listas/{batch_id}/progresso.json")
def dispatch_import_bulk_progress(batch_id: str, user: dict = Depends(current_user)):
    _require_dispatch_access(user)
    if not get_import_batch(batch_id):
        raise HTTPException(status_code=404, detail="Lista importada não encontrada.")
    try:
        state = get_bulk_dispatch_state(batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(state)


@router.post("/{dispatch_id}/reenviar")
def dispatch_retry(
    dispatch_id: str,
    request: Request,
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _require_dispatch_access(user)
    _require_csrf(request, csrf_token)
    try:
        row = retry_dispatch(dispatch_id, requested_by=str(user.get("id") or "") or None)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(
        actor_id=user.get("id"),
        entity_type="dispatch",
        entity_id=dispatch_id,
        action="dispatch_retried",
        payload={"status": row.get("status")},
    )
    return RedirectResponse(url=f"/disparos?{'sent=1' if row.get('status') != 'failed' else 'failed=1'}", status_code=303)
