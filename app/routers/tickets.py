from __future__ import annotations

import hashlib
import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from app.core.config import get_settings
from app.core.ui import templates
from app.dependencies.auth import current_user, internal_user
from app.services.audit_service import record_audit
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services.attachment_service import (
    AttachmentError,
    delete_attachment,
    demo_file_path,
    get_attachment,
    get_attachment_ticket_id,
    prepare_attachment,
    save_attachment,
    signed_download_url,
)
from app.services.customer_service import list_customers, list_farms
from app.services.funnel_service import get_funnel, list_funnels
from app.services.metadata_service import list_categories, list_crops, list_internal_users
from app.services.opportunity_service import OpportunityConflictError, archive_opportunity, get_ticket_opportunity, list_opportunities, move_opportunity_stage
from app.services.integration_service import queue_whatsapp_outbound
from app.services.whatsapp_window_service import WhatsAppTemplateRequiredError, get_whatsapp_service_window, require_freeform_window
from app.services.automation_service import (
    connect_ticket_to_ai,
    disconnect_ticket_from_ai,
    get_ticket_ai_control,
    set_ticket_ai_mode,
)
from app.services.product_service import money_label, parse_money
from app.services.ticket_attention_service import summarize_ticket, summarize_tickets, date_br
from app.services.ticket_service import (
    TICKET_STATUSES,
    add_message,
    assign_ticket,
    claim_ticket_on_open,
    change_status,
    create_ticket,
    delete_message_after_failed_upload,
    get_ticket,
    list_messages,
    list_tickets,
    status_options,
)

router = APIRouter(prefix="/atendimentos", tags=["atendimentos"])
logger = logging.getLogger(__name__)


def _detail_context(ticket_id: str, user: dict, request: Request | None = None, **extra) -> dict:
    ticket = get_ticket(ticket_id, user)
    if not ticket:
        raise HTTPException(status_code=404, detail="Atendimento não encontrado.")
    messages = list_messages(ticket_id, user)
    context = {
        "user": user,
        "ticket": ticket,
        "messages": messages,
        "ticket_milestones": summarize_ticket(ticket, messages),
        "active_page": "tickets",
        "statuses": status_options(ticket["status"]),
        "poll_seconds": max(2, get_settings().live_poll_seconds),
        "settings_attachment_max_mb": get_settings().attachment_max_mb,
        "settings_attachment_video_max_mb": get_settings().attachment_video_max_mb,
        "composer_error": None,
        "composer_body": "",
        "csrf_token": _tickets_csrf(request) if request else None,
    }
    if user.get("role") in {"responsavel", "administrador"}:
        context["responsibles"] = list_internal_users()
        context["opportunity"] = get_ticket_opportunity(ticket_id)
        if ticket.get("source") == "whatsapp":
            context["whatsapp_window"] = get_whatsapp_service_window(ticket_id)
            try:
                context["ai_control"] = get_ticket_ai_control(ticket_id)
            except ValueError:
                context["ai_control"] = None
    context["template_notice"] = request.query_params.get("template_notice") if request else None
    context.update(extra)
    return context


def _serialize_message(message: dict, current_user_id: str) -> dict:
    return {
        "id": str(message.get("id") or ""),
        "sender_id": str(message.get("sender_id") or ""),
        "sender_name": message.get("sender_name") or "Usuário",
        "sender_kind": message.get("sender_kind") or "human",
        "body": message.get("body") or "",
        "channel": message.get("channel") or "internal",
        "direction": message.get("direction") or "outbound",
        "is_internal": bool(message.get("is_internal")),
        "created_at": message.get("created_at"),
        "delivery_status": message.get("delivery_status"),
        "delivery_error": message.get("delivery_error"),
        "mine": str(message.get("sender_id") or "") == str(current_user_id) or message.get("sender_kind") == "ai",
        "attachments": [
            {
                "id": str(item.get("id") or ""),
                "file_name": item.get("file_name") or "arquivo",
                "mime_type": item.get("mime_type") or "application/octet-stream",
                "size_label": item.get("size_label") or "",
                "is_image": bool(item.get("is_image")),
                "is_audio": bool(item.get("is_audio")),
                "is_video": bool(item.get("is_video")),
                "is_browser_playable_video": bool(item.get("is_browser_playable_video")),
                "is_pdf": bool(item.get("is_pdf")),
                "url": item.get("url"),
            }
            for item in (message.get("attachments") or [])
        ],
    }


def _tickets_csrf(request: Request) -> str:
    return csrf_token_for_session(request.cookies.get(COOKIE_NAME))


def _require_tickets_csrf(request: Request, supplied: str) -> None:
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME), supplied):
        raise HTTPException(status_code=403, detail="Token de segurança inválido. Atualize a página e tente novamente.")


def _kanban_signature(columns: list[dict]) -> str:
    snapshot = []
    for column in columns:
        stage = column.get("stage") or {}
        snapshot.append({
            "stage_id": str(stage.get("id") or ""),
            "stage_name": stage.get("name") or "",
            "stage_color": stage.get("color") or "",
            "count": int(column.get("count") or 0),
            "total_label": column.get("total_label") or "",
            "cards": [
                {
                    "id": str(card.get("id") or ""),
                    "stage_id": str(card.get("stage_id") or ""),
                    "lock_version": int(card.get("lock_version") or 0),
                    "kanban_position": int(card.get("kanban_position") or 0),
                    "customer_name": card.get("customer_name") or "",
                    "title": card.get("title") or "",
                    "calculated_value_label": card.get("calculated_value_label") or "",
                    "assigned_name": card.get("assigned_name") or "",
                    "expected_close_date": card.get("expected_close_date"),
                    "arrival_date": card.get("arrival_date"),
                    "first_reply_time": card.get("first_reply_time"),
                    "pending": card.get("pending"),
                    "updated_at": card.get("updated_at"),
                }
                for card in (column.get("cards") or [])
            ],
        })
    return hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _kanban_context(*, funnel_id: str | None, search: str | None, assigned_user_id: str | None, user: dict) -> dict:
    funnels = [f for f in list_funnels(include_inactive=False) if any(bool(s.get("is_active", True)) for s in (f.get("stages") or []))]
    selected = next((f for f in funnels if str(f.get("id")) == str(funnel_id)), None) or (funnels[0] if funnels else None)
    if not selected:
        return {
            "funnels": funnels,
            "selected_funnel": None,
            "columns": [],
            "responsibles": list_internal_users(),
            "kanban_search": search or "",
            "kanban_assigned": assigned_user_id or "",
            "kanban_signature": _kanban_signature([]),
        }

    opportunities = list_opportunities(search=search, status="open", funnel_id=str(selected["id"]))
    if assigned_user_id:
        opportunities = [row for row in opportunities if str(row.get("assigned_user_id") or "") == str(assigned_user_id)]
    opportunities.sort(key=lambda row: (int(row.get("kanban_position") or 0), str(row.get("created_at") or "")))
    tickets = list_tickets(user, limit=500)
    lookup = {str(ticket['id']): ticket for ticket in tickets}
    related = [lookup[str(item['ticket_id'])] for item in opportunities if item.get('ticket_id') and str(item['ticket_id']) in lookup]
    milestones = summarize_tickets(related)
    for item in opportunities:
        ticket_id = str(item.get('ticket_id') or '')
        data = milestones.get(ticket_id) or {}
        item['arrival_date'] = data.get('arrival_date') or date_br(item.get('created_at'))
        item['first_reply_time'] = data.get('first_reply_time') or '—'
        item['pending'] = data.get('pending') or False

    columns = []
    for stage in [s for s in (selected.get("stages") or []) if bool(s.get("is_active", True))]:
        cards = [row for row in opportunities if str(row.get("stage_id")) == str(stage.get("id"))]
        total = sum((parse_money(row.get("calculated_value")) for row in cards), start=parse_money("0"))
        columns.append({"stage": stage, "cards": cards, "count": len(cards), "total_label": money_label(total)})
    return {
        "funnels": funnels,
        "selected_funnel": selected,
        "columns": columns,
        "responsibles": list_internal_users(),
        "kanban_search": search or "",
        "kanban_assigned": assigned_user_id or "",
        "kanban_signature": _kanban_signature(columns),
    }


@router.get("")
def tickets_page(
    request: Request,
    view: str = "lista",
    funil: str | None = None,
    q: str | None = None,
    responsavel: str | None = None,
    conflict: int | None = None,
    deleted: int | None = None,
    user: dict = Depends(current_user),
):
    can_use_crm = user.get("role") in {"responsavel", "administrador"}
    selected_view = "funil" if view == "funil" and can_use_crm else "lista"
    context = {
        "user": user,
        "tickets": list_tickets(user),
        "active_page": "tickets",
        "poll_seconds": max(2, get_settings().live_poll_seconds),
        "selected_view": selected_view,
        "csrf_token": _tickets_csrf(request),
        "kanban_conflict": bool(conflict),
        "kanban_deleted": bool(deleted),
    }
    if can_use_crm:
        context.update(_kanban_context(funnel_id=funil, search=q, assigned_user_id=responsavel, user=user))
    if selected_view == "lista":
        context["ticket_attention"] = summarize_tickets(context["tickets"])
    return templates.TemplateResponse(request=request, name="tickets/list.html", context=context)


@router.get("/funil/feed.json")
def ticket_kanban_feed(
    request: Request,
    funil: str | None = None,
    q: str | None = None,
    responsavel: str | None = None,
    user: dict = Depends(current_user),
):
    internal_user(user)
    context = _kanban_context(funnel_id=funil, search=q, assigned_user_id=responsavel, user=user)
    selected = context.get("selected_funnel")
    if not selected:
        return JSONResponse({
            "signature": context.get("kanban_signature"),
            "funnel_id": None,
            "html": "",
            "empty": True,
        })
    fragment = templates.env.get_template("tickets/_kanban_columns.html").render(
        columns=context.get("columns") or [],
        selected_funnel=selected,
        csrf_token=_tickets_csrf(request),
        kanban_search=context.get("kanban_search") or "",
        kanban_assigned=context.get("kanban_assigned") or "",
    )
    return JSONResponse({
        "signature": context.get("kanban_signature"),
        "funnel_id": str(selected.get("id")),
        "html": fragment,
        "empty": False,
    })


@router.post("/funil/oportunidades/{opportunity_id}/mover")
def ticket_kanban_move(
    opportunity_id: str,
    request: Request,
    stage_id: str = Form(...),
    lock_version: int = Form(...),
    csrf_token: str = Form(...),
    response_mode: str = Form("redirect"),
    funnel_id: str = Form(""),
    q: str = Form(""),
    assigned_user_id: str = Form(""),
    user: dict = Depends(current_user),
):
    internal_user(user)
    _require_tickets_csrf(request, csrf_token)
    try:
        opportunity = move_opportunity_stage(
            opportunity_id,
            to_stage_id=stage_id,
            expected_lock_version=lock_version,
            actor_id=user.get("id"),
            source="kanban",
        )
    except OpportunityConflictError as exc:
        if response_mode == "json":
            return JSONResponse(
                status_code=409,
                content={"ok": False, "error": str(exc), "code": "conflict", "current_lock_version": int((exc.current or {}).get("lock_version") or 0)},
            )
        params = ["view=funil", "conflict=1"]
        if funnel_id:
            params.append("funil=" + str(funnel_id))
        return RedirectResponse(url="/atendimentos?" + "&".join(params), status_code=303)
    except ValueError as exc:
        if response_mode == "json":
            return JSONResponse(status_code=422, content={"ok": False, "error": str(exc), "code": "invalid_move"})
        raise HTTPException(status_code=422, detail=str(exc))

    record_audit(
        actor_id=user.get("id"),
        entity_type="opportunity",
        entity_id=opportunity_id,
        action="opportunity_stage_changed",
        payload={"to_stage_id": stage_id, "source": "kanban", "lock_version": opportunity.get("lock_version")},
    )
    if response_mode == "json":
        return JSONResponse({
            "ok": True,
            "opportunity": {
                "id": str(opportunity.get("id")),
                "stage_id": str(opportunity.get("stage_id")),
                "stage_name": opportunity.get("stage_name"),
                "lock_version": int(opportunity.get("lock_version") or 0),
                "calculated_value_label": opportunity.get("calculated_value_label"),
            },
        })
    params = ["view=funil"]
    if funnel_id:
        params.append("funil=" + str(funnel_id))
    if q:
        from urllib.parse import quote_plus
        params.append("q=" + quote_plus(q))
    if assigned_user_id:
        params.append("responsavel=" + str(assigned_user_id))
    return RedirectResponse(url="/atendimentos?" + "&".join(params), status_code=303)


@router.post("/funil/oportunidades/{opportunity_id}/arquivar")
def ticket_kanban_archive(
    opportunity_id: str,
    request: Request,
    lock_version: int = Form(...),
    csrf_token: str = Form(...),
    funnel_id: str = Form(""),
    q: str = Form(""),
    assigned_user_id: str = Form(""),
    user: dict = Depends(current_user),
):
    internal_user(user)
    _require_tickets_csrf(request, csrf_token)
    try:
        opportunity = archive_opportunity(
            opportunity_id,
            expected_lock_version=lock_version,
            actor_id=user.get("id"),
        )
    except OpportunityConflictError:
        params = ["view=funil", "conflict=1"]
        if funnel_id:
            params.append("funil=" + str(funnel_id))
        return RedirectResponse(url="/atendimentos?" + "&".join(params), status_code=303)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record_audit(
        actor_id=user.get("id"),
        entity_type="opportunity",
        entity_id=opportunity_id,
        action="opportunity_archived_from_kanban",
        payload={"stage_id": opportunity.get("stage_id"), "source": "kanban", "archived_at": opportunity.get("archived_at")},
    )
    params = ["view=funil", "deleted=1"]
    if funnel_id:
        params.append("funil=" + str(funnel_id))
    if q:
        from urllib.parse import quote_plus
        params.append("q=" + quote_plus(q))
    if assigned_user_id:
        params.append("responsavel=" + str(assigned_user_id))
    return RedirectResponse(url="/atendimentos?" + "&".join(params), status_code=303)


@router.get("/feed.json")
def tickets_feed(user: dict = Depends(current_user)):
    tickets = list_tickets(user)
    attention = summarize_tickets(tickets)
    items = [
        {
            "id": str(ticket["id"]),
            "customer_name": ticket.get("customer_name") or "Cliente",
            "farm_name": ticket.get("farm_name") or "—",
            "crop_name": ticket.get("crop_name") or "—",
            "title": ticket.get("title") or "Atendimento",
            "source": ticket.get("source") or "interno",
            "status": ticket.get("status") or "novo",
            "assigned_name": ticket.get("assigned_name") or "Sem responsável",
            "updated_at": ticket.get("updated_at"),
            "arrival_date": (attention.get(str(ticket["id"])) or {}).get("arrival_date", "—"),
            "first_reply_time": (attention.get(str(ticket["id"])) or {}).get("first_reply_time", "—"),
            "pending": (attention.get(str(ticket["id"])) or {}).get("pending", False),
        }
        for ticket in tickets
    ]
    signature = hashlib.sha256(json.dumps(items, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return JSONResponse({"signature": signature, "tickets": items})


@router.get("/alertas.json")
def ticket_pending_alerts(user: dict = Depends(current_user)):
    """Alertas de conversas sem resposta ao lead após 30 minutos."""
    internal_user(user)
    from app.services.access_service import level_for
    tickets = list_tickets(user, limit=300)
    level = level_for(user)
    if level not in {'administrativo', 'gerencial'}:
        tickets = [row for row in tickets if not row.get('assigned_user_id') or str(row.get('assigned_user_id')) == str(user.get('id'))]
    attention = summarize_tickets(tickets)
    alerts = []
    for ticket in tickets:
        info = attention.get(str(ticket['id'])) or {}
        if not info.get('pending'):
            continue
        alerts.append({
            'ticket_id': str(ticket['id']),
            'customer_name': ticket.get('customer_name') or 'Lead',
            'minutes': info['pending_minutes'],
            'since': info['pending_since'],
            'first_reply_time': info['first_reply_time'],
            'key': info['alert_key'],
        })
    alerts.sort(key=lambda item: (-item['minutes'], item['customer_name']))
    return JSONResponse({'threshold_minutes': 30, 'alerts': alerts, 'count': len(alerts)}, headers={'Cache-Control': 'no-store'})


@router.get("/novo")
def ticket_new_page(request: Request, cliente: str | None = None, user: dict = Depends(current_user)):
    internal_user(user)
    customers = list_customers(include_inactive=False)
    selected_customer = cliente if any(c["id"] == cliente for c in customers) else None
    farms = list_farms(selected_customer) if selected_customer else []
    selected_farm = farms[0]["id"] if len(farms) == 1 else None
    return templates.TemplateResponse(request=request, name="tickets/form.html", context={"user": user, "customers": customers, "farms": farms, "selected_customer": selected_customer, "selected_farm": selected_farm, "crops": list_crops(), "categories": list_categories(), "responsibles": list_internal_users(), "error": None, "form": {}, "active_page": "tickets"})


@router.post("/novo")
def ticket_create(request: Request, title: str = Form(...), customer_id: str = Form(...), farm_id: str = Form(""), crop_id: str = Form(""), category_id: str = Form(""), assigned_user_id: str = Form(""), status: str = Form("novo"), priority: str = Form("normal"), source: str = Form("interno"), user: dict = Depends(current_user)):
    internal_user(user)
    form = locals().copy()
    try:
        ticket = create_ticket(user=user, title=title, customer_id=customer_id, farm_id=farm_id or None, crop_id=crop_id or None, category_id=category_id or None, assigned_user_id=assigned_user_id or None, status=status, priority=priority, source=source)
    except (ValueError, PermissionError) as exc:
        return templates.TemplateResponse(request=request, name="tickets/form.html", status_code=422, context={"user": user, "customers": list_customers(include_inactive=False), "farms": list_farms(customer_id), "selected_customer": customer_id, "selected_farm": None, "crops": list_crops(), "categories": list_categories(), "responsibles": list_internal_users(), "error": str(exc), "form": form, "active_page": "tickets"})
    return RedirectResponse(url=f"/atendimentos/{ticket['id']}", status_code=303)


@router.get("/{ticket_id}")
def ticket_detail(ticket_id: str, request: Request, user: dict = Depends(current_user)):
    try:
        claim_ticket_on_open(ticket_id, user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(request=request, name="tickets/detail.html", context=_detail_context(ticket_id, user, request=request))


@router.get("/{ticket_id}/mensagens.json")
def ticket_messages_feed(ticket_id: str, user: dict = Depends(current_user)):
    ticket = get_ticket(ticket_id, user)
    if not ticket:
        raise HTTPException(status_code=404, detail="Atendimento não encontrado.")
    messages = [_serialize_message(message, str(user["id"])) for message in list_messages(ticket_id, user)]
    automation = None
    whatsapp_window = get_whatsapp_service_window(ticket_id) if ticket.get("source") == "whatsapp" else None
    if ticket.get("source") == "whatsapp" and user.get("role") in {"responsavel", "administrador"}:
        try:
            automation = get_ticket_ai_control(ticket_id)
        except ValueError:
            automation = None
    signature_payload = {
        "messages": messages,
        "status": ticket.get("status"),
        "assigned_user_id": ticket.get("assigned_user_id"),
        "updated_at": ticket.get("updated_at"),
        "automation": automation,
        "whatsapp_window": whatsapp_window,
    }
    signature = hashlib.sha256(json.dumps(signature_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return JSONResponse({"signature": signature, "messages": messages, "ticket": {"status": ticket.get("status"), "updated_at": ticket.get("updated_at")}, "automation": automation, "whatsapp_window": whatsapp_window})


@router.post("/{ticket_id}/mensagens")
async def send_message(
    ticket_id: str,
    request: Request,
    user: dict = Depends(current_user),
    body: str = Form(""),
    is_internal: bool = Form(False),
    files: list[UploadFile] = File(default=[]),
    csrf_token: str | None = Form(default=None),
):
    _require_tickets_csrf(request, csrf_token or "")
    ticket = get_ticket(ticket_id, user)
    if not ticket:
        raise HTTPException(status_code=404, detail="Atendimento não encontrado.")
    if user.get("role") == "agronomo":
        is_internal = False

    if ticket.get("source") == "whatsapp" and not is_internal:
        try:
            require_freeform_window(ticket_id)
        except WhatsAppTemplateRequiredError as exc:
            return templates.TemplateResponse(
                request=request,
                name="tickets/detail.html",
                status_code=422,
                context=_detail_context(ticket_id, user, request=request, composer_error=str(exc), composer_body=body),
            )

    selected_files = [upload for upload in files if upload.filename]
    if len(selected_files) > 6:
        return templates.TemplateResponse(
            request=request,
            name="tickets/detail.html",
            status_code=422,
            context=_detail_context(ticket_id, user, request=request, composer_error="Envie no máximo 6 arquivos por mensagem.", composer_body=body),
        )

    prepared_files = []
    try:
        for upload in selected_files:
            content = await upload.read()
            prepared_files.append(prepare_attachment(upload.filename, upload.content_type, content))
            await upload.close()
        if not body.strip() and not prepared_files:
            raise AttachmentError("Digite uma mensagem ou selecione ao menos um anexo.")
    except AttachmentError as exc:
        return templates.TemplateResponse(
            request=request,
            name="tickets/detail.html",
            status_code=422,
            context=_detail_context(ticket_id, user, request=request, composer_error=str(exc), composer_body=body),
        )

    message = None
    saved_attachments = []
    human_whatsapp = (not is_internal and user.get("role") in {"responsavel", "administrador"}
                      and ticket.get("source") == "whatsapp")
    if human_whatsapp:
        try:
            # Falha no controle interrompe antes de persistir mensagem/anexos/outbox.
            set_ticket_ai_mode(ticket_id, mode="human", actor_id=str(user.get("id") or "") or None, source="human_message")
        except ValueError as exc:
            return templates.TemplateResponse(
                request=request, name="tickets/detail.html", status_code=422,
                context=_detail_context(ticket_id, user, request=request, composer_error=str(exc), composer_body=body),
            )
    try:
        message = add_message(ticket_id, user, body, is_internal=is_internal, allow_empty=bool(prepared_files))
        for prepared in prepared_files:
            saved_attachments.append(
                save_attachment(
                    ticket_id=ticket_id,
                    message_id=str(message["id"]),
                    uploaded_by=str(user.get("id") or "") or None,
                    prepared=prepared,
                )
            )
        if human_whatsapp:
            queue_whatsapp_outbound(ticket_id=ticket_id, message_id=str(message["id"]))
    except Exception:
        logger.exception("Falha ao persistir mensagem/anexo do atendimento %s", ticket_id)
        for attachment in reversed(saved_attachments):
            try:
                delete_attachment(attachment)
            except Exception:
                logger.exception("Falha no rollback do anexo %s", attachment.get("id"))
        if message and message.get("id"):
            try:
                delete_message_after_failed_upload(ticket_id, str(message["id"]))
            except Exception:
                logger.exception("Falha no rollback da mensagem %s", message.get("id"))
        return templates.TemplateResponse(
            request=request,
            name="tickets/detail.html",
            status_code=500,
            context=_detail_context(ticket_id, user, request=request, composer_error="Não foi possível salvar a mensagem e os anexos. Tente novamente.", composer_body=body),
        )

    return RedirectResponse(url=f"/atendimentos/{ticket_id}", status_code=303)


@router.get("/{ticket_id}/anexos/{attachment_id}")
def download_attachment(ticket_id: str, attachment_id: str, user: dict = Depends(current_user)):
    ticket = get_ticket(ticket_id, user)
    if not ticket:
        raise HTTPException(status_code=404, detail="Atendimento não encontrado.")

    visible_attachment_ids = {
        str(item.get("id"))
        for message in list_messages(ticket_id, user)
        for item in (message.get("attachments") or [])
    }
    if str(attachment_id) not in visible_attachment_ids:
        raise HTTPException(status_code=404, detail="Anexo não encontrado neste atendimento.")

    attachment = get_attachment(attachment_id)
    if not attachment or str(get_attachment_ticket_id(attachment)) != str(ticket_id):
        raise HTTPException(status_code=404, detail="Anexo não encontrado neste atendimento.")

    settings = get_settings()
    if settings.demo_mode:
        path = demo_file_path(attachment)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Arquivo não encontrado no armazenamento local.")
        attachment_mime = str(attachment.get("mime_type") or "")
        inline = attachment_mime.startswith(("image/", "audio/", "video/")) or attachment_mime == "application/pdf"
        return FileResponse(
            path=path,
            media_type=attachment.get("mime_type") or "application/octet-stream",
            filename=attachment.get("file_name") or "arquivo",
            content_disposition_type="inline" if inline else "attachment",
        )

    try:
        return RedirectResponse(url=signed_download_url(attachment), status_code=307)
    except AttachmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{ticket_id}/ia/assumir")
def ticket_ai_takeover(
    ticket_id: str,
    request: Request,
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    internal_user(user)
    if user.get("role") not in {"responsavel", "administrador"}:
        raise HTTPException(status_code=403, detail="Acesso restrito à equipe de atendimento.")
    _require_tickets_csrf(request, csrf_token)
    try:
        control = disconnect_ticket_from_ai(ticket_id, actor_id=str(user.get("id") or "") or None, source="ui_takeover")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(
        actor_id=user.get("id"),
        entity_type="ticket",
        entity_id=ticket_id,
        action="ai_handoff_human",
        payload={"control_version": control.get("control_version")},
    )
    return RedirectResponse(url=f"/atendimentos/{ticket_id}", status_code=303)


@router.post("/{ticket_id}/ia/reativar")
def ticket_ai_resume(
    ticket_id: str,
    request: Request,
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    internal_user(user)
    if user.get("role") not in {"responsavel", "administrador"}:
        raise HTTPException(status_code=403, detail="Acesso restrito à equipe de atendimento.")
    _require_tickets_csrf(request, csrf_token)
    try:
        control = connect_ticket_to_ai(ticket_id, actor_id=str(user.get("id") or "") or None, source="ui_resume")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(
        actor_id=user.get("id"),
        entity_type="ticket",
        entity_id=ticket_id,
        action="ai_handoff_ai",
        payload={"control_version": control.get("control_version")},
    )
    return RedirectResponse(url=f"/atendimentos/{ticket_id}", status_code=303)


@router.post("/{ticket_id}/ia/desconectar")
def ticket_ai_disconnect(
    ticket_id: str,
    request: Request,
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    internal_user(user)
    if user.get("role") not in {"responsavel", "administrador"}:
        raise HTTPException(status_code=403, detail="Acesso restrito à equipe de atendimento.")
    _require_tickets_csrf(request, csrf_token)
    try:
        control = disconnect_ticket_from_ai(ticket_id, actor_id=str(user.get("id") or "") or None, source="ui_disconnect")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(
        actor_id=user.get("id"),
        entity_type="ticket",
        entity_id=ticket_id,
        action="ai_conversation_disconnected",
        payload={"control_version": control.get("control_version"), "connection_state": control.get("connection_state")},
    )
    return RedirectResponse(url=f"/atendimentos/{ticket_id}", status_code=303)


@router.post("/{ticket_id}/ia/conectar")
def ticket_ai_connect(
    ticket_id: str,
    request: Request,
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    internal_user(user)
    if user.get("role") not in {"responsavel", "administrador"}:
        raise HTTPException(status_code=403, detail="Acesso restrito à equipe de atendimento.")
    _require_tickets_csrf(request, csrf_token)
    try:
        control = connect_ticket_to_ai(ticket_id, actor_id=str(user.get("id") or "") or None, source="ui_connect")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(
        actor_id=user.get("id"),
        entity_type="ticket",
        entity_id=ticket_id,
        action="ai_conversation_connected",
        payload={"control_version": control.get("control_version"), "connection_state": control.get("connection_state")},
    )
    return RedirectResponse(url=f"/atendimentos/{ticket_id}", status_code=303)


@router.post("/{ticket_id}/atribuir")
def ticket_assign(ticket_id: str, assigned_user_id: str = Form(""), user: dict = Depends(current_user)):
    internal_user(user)
    try:
        assign_ticket(ticket_id, user, assigned_user_id or None)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RedirectResponse(url=f"/atendimentos/{ticket_id}", status_code=303)


@router.post("/{ticket_id}/status")
def ticket_status(ticket_id: str, status: str = Form(...), user: dict = Depends(current_user)):
    internal_user(user)
    try:
        change_status(ticket_id, user, status)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RedirectResponse(url=f"/atendimentos/{ticket_id}", status_code=303)
