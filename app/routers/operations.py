from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.ui import templates
from app.dependencies.auth import current_user
from app.services.audit_service import list_audit_log, record_audit
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services.admin_settings_service import (
    WEBHOOK_KINDS,
    create_webhook,
    delete_webhook,
    get_ai_settings,
    get_ai_routing_settings,
    get_dispatch_settings,
    get_whatsapp_settings,
    get_make_outbox_settings,
    list_webhooks,
    rotate_webhook_secret,
    save_ai_settings,
    save_ai_routing_settings,
    save_dispatch_settings,
    save_whatsapp_settings,
    save_make_outbox_settings,
    set_webhook_active,
)
from app.services.whatsapp_provider_catalog import provider_catalog, provider_by_key
from app.services.local_credentials_service import local_config_info
from app.services.outbox_wake_service import test_make_outbox_wake
from app.services.integration_service import (
    integration_counts,
    list_recent_integration_events,
    list_recent_outbox,
    requeue_outbox,
    supabase_readiness,
    whatsapp_homologation_status,
)
from app.services.funnel_service import list_funnels
from app.services.integration_diagnostics_service import (
    contract_examples,
    integration_channel_overview,
    list_diagnostic_events,
    test_ai_control_webhook,
    test_dispatch_webhook,
)

router = APIRouter(tags=["operacao"])

_WEBHOOK_FLASHES: dict[str, dict] = {}

def _put_webhook_flash(user: dict, webhook: dict, secret: str, message: str) -> str:
    now = datetime.now(timezone.utc)
    # Limpeza oportunista para não manter segredos temporários além do necessário.
    for key, value in list(_WEBHOOK_FLASHES.items()):
        if value.get("expires_at") and value["expires_at"] < now:
            _WEBHOOK_FLASHES.pop(key, None)
    token = secrets.token_urlsafe(24)
    _WEBHOOK_FLASHES[token] = {
        "user_id": str(user.get("id") or ""),
        "webhook": webhook,
        "secret": secret,
        "message": message,
        "expires_at": now + timedelta(minutes=5),
    }
    return token


def _take_webhook_flash(user: dict, token: str | None) -> dict | None:
    if not token:
        return None
    # Não consumir o flash antes de a página chegar ao navegador. Proxies,
    # verificadores de segurança e retries HTTP podem repetir o GET do redirect.
    # O segredo permanece apenas em memória, vinculado ao mesmo usuário, e
    # expira em 5 minutos; nunca é persistido em texto puro.
    item = _WEBHOOK_FLASHES.get(token)
    if not item:
        return None
    if item.get("expires_at") < datetime.now(timezone.utc):
        _WEBHOOK_FLASHES.pop(token, None)
        return None
    if item.get("user_id") != str(user.get("id") or ""):
        return None
    return item


def _admin(user: dict) -> dict:
    if user.get("role") != "administrador":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
    return user


@router.get("/integracoes")
def integrations_page(
    request: Request,
    test: str | None = None,
    user: dict = Depends(current_user),
):
    _admin(user)
    success = None
    error = None
    if test == "ai_ok":
        success = "Webhook de controle da IA respondeu ao teste de conectividade."
    elif test == "dispatch_ok":
        success = "Webhook de Disparos respondeu ao teste de conectividade."
    elif test == "ai_failed":
        error = "O webhook de controle da IA não confirmou o teste. Consulte o diagnóstico recente."
    elif test == "dispatch_failed":
        error = "O webhook de Disparos não confirmou o teste. Consulte o diagnóstico recente."
    base_url = str(request.base_url).rstrip("/")
    return templates.TemplateResponse(
        request=request,
        name="operations/integrations.html",
        context={
            "user": user,
            "active_page": "integrations",
            "readiness": supabase_readiness(),
            "counts": integration_counts(),
            "events": list_recent_integration_events(30),
            "outbox": list_recent_outbox(30),
            "settings": get_settings(),
            "channels": integration_channel_overview(),
            "contracts": contract_examples(base_url),
            "diagnostics": list_diagnostic_events(20),
            "csrf_token": csrf_token_for_session(request.cookies.get(COOKIE_NAME)),
            "success": success,
            "error": error,
        },
    )


@router.post("/integracoes/testar/ia")
def integrations_test_ai(
    request: Request,
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _admin(user)
    _require_csrf(request, csrf_token)
    try:
        result = test_ai_control_webhook()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(
        actor_id=user.get("id"),
        entity_type="integration_test",
        entity_id="ai_control",
        action="tested",
        payload={"ok": bool(result.get("ok")), "status_code": result.get("status_code")},
    )
    return RedirectResponse(url=f"/integracoes?test={'ai_ok' if result.get('ok') else 'ai_failed'}#diagnosticos", status_code=303)


@router.post("/integracoes/testar/disparos")
def integrations_test_dispatches(
    request: Request,
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _admin(user)
    _require_csrf(request, csrf_token)
    try:
        result = test_dispatch_webhook()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(
        actor_id=user.get("id"),
        entity_type="integration_test",
        entity_id="dispatches",
        action="tested",
        payload={"ok": bool(result.get("ok")), "status_code": result.get("status_code")},
    )
    return RedirectResponse(url=f"/integracoes?test={'dispatch_ok' if result.get('ok') else 'dispatch_failed'}#diagnosticos", status_code=303)


@router.get("/integracoes/whatsapp/status.json")
def whatsapp_homologation_status_json(user: dict = Depends(current_user)):
    _admin(user)
    return whatsapp_homologation_status()


@router.get("/integracoes/whatsapp/provedores.json")
def whatsapp_providers_json(user: dict = Depends(current_user)):
    _admin(user)
    return {"providers": provider_catalog()}


@router.post("/integracoes/outbox/{outbox_id}/reprocessar")
def retry_outbox(outbox_id: str, user: dict = Depends(current_user)):
    _admin(user)
    try:
        requeue_outbox(outbox_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RedirectResponse(url="/integracoes#saidas", status_code=303)


@router.get("/auditoria")
def audit_page(request: Request, user: dict = Depends(current_user)):
    _admin(user)
    return templates.TemplateResponse(
        request=request,
        name="operations/audit.html",
        context={"user": user, "active_page": "audit", "rows": list_audit_log(100)},
    )


def _settings_context(request: Request, user: dict, **extra):
    base_url = str(request.base_url).rstrip("/")
    context = {
        "user": user,
        "active_page": "settings",
        "whatsapp": get_whatsapp_settings(),
        "make_outbox": get_make_outbox_settings(),
        "ai_automation": get_ai_settings(),
        "ai_routing": get_ai_routing_settings(),
        "routing_funnels": list_funnels(include_inactive=False),
        "dispatch_settings": get_dispatch_settings(),
        "provider_catalog": provider_catalog(),
        "webhooks": list_webhooks(),
        "webhook_kinds": WEBHOOK_KINDS,
        "base_url": base_url,
        "error": None,
        "success": None,
        "new_webhook": None,
        "new_webhook_secret": None,
        "csrf_token": csrf_token_for_session(request.cookies.get(COOKIE_NAME)),
        "local_config": local_config_info() if get_settings().demo_mode else None,
        "local_test_mode": bool(get_settings().demo_mode),
    }
    context.update(extra)
    return context


def _require_csrf(request: Request, supplied: str) -> None:
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME), supplied):
        raise HTTPException(status_code=403, detail="Token de segurança inválido. Atualize a página e tente novamente.")


@router.get("/configuracoes")
def settings_page(request: Request, flash: str | None = None, saved: str | None = None, user: dict = Depends(current_user)):
    _admin(user)
    reveal = _take_webhook_flash(user, flash)
    success = None
    if reveal:
        success = reveal.get("message")
    elif saved == "whatsapp":
        success = "Configuração do WhatsApp salva com segurança."
    elif saved == "make_outbox":
        success = "Disparo instantâneo da outbox salvo. Novas respostas podem acordar o cenário do Make imediatamente."
    elif saved == "make_outbox_test_ok":
        success = "Webhook instantâneo do Make respondeu com sucesso."
    elif saved == "ai":
        success = "Configuração da IA de atendimento salva."
    elif saved == "ai_routing":
        success = "Roteamento comercial da IA salvo."
    elif saved == "dispatches":
        success = "Configuração de Disparos salva."
    context = _settings_context(
        request,
        user,
        success=success,
        new_webhook=reveal.get("webhook") if reveal else None,
        new_webhook_secret=reveal.get("secret") if reveal else None,
    )
    response = templates.TemplateResponse(request=request, name="operations/settings.html", context=context)
    if reveal:
        # Credenciais temporárias não devem ser armazenadas em cache por navegador
        # ou por intermediários durante a homologação HTTPS.
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@router.post("/configuracoes/whatsapp")
def settings_whatsapp_save(
    request: Request,
    enabled: str | None = Form(default=None),
    display_phone_number: str = Form(""),
    provider_key: str = Form("meta_cloud"),
    provider: str = Form(""),
    phone_number_id: str = Form(""),
    business_account_id: str = Form(""),
    notes: str = Form(""),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _admin(user)
    _require_csrf(request, csrf_token)
    try:
        saved = save_whatsapp_settings(
            enabled=enabled == "on",
            display_phone_number=display_phone_number,
            provider_key=provider_key,
            provider=provider,
            phone_number_id=phone_number_id,
            business_account_id=business_account_id,
            notes=notes,
        )
        record_audit(
            actor_id=user.get("id"),
            entity_type="integration_settings",
            entity_id="whatsapp",
            action="updated",
            payload={
                "enabled": saved.get("enabled"),
                "display_phone_number": saved.get("display_phone_number"),
                "provider_key": saved.get("provider_key"),
                "provider": saved.get("provider"),
                "phone_number_id_configured": bool(saved.get("phone_number_id")),
                "business_account_id_configured": bool(saved.get("business_account_id")),
            },
        )
    except ValueError as exc:
        current = {
            "enabled": enabled == "on",
            "display_phone_number": display_phone_number,
            "provider_key": provider_key,
            "provider": provider,
            "phone_number_id": phone_number_id,
            "business_account_id": business_account_id,
            "notes": notes,
        }
        return templates.TemplateResponse(
            request=request,
            name="operations/settings.html",
            status_code=422,
            context=_settings_context(request, user, whatsapp=current, error=str(exc)),
        )
    return RedirectResponse(url="/configuracoes?saved=whatsapp#whatsapp", status_code=303)


@router.post("/configuracoes/make-outbox")
def settings_make_outbox_save(
    request: Request,
    enabled: str | None = Form(default=None),
    wake_url: str = Form(""),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _admin(user)
    _require_csrf(request, csrf_token)
    try:
        saved = save_make_outbox_settings(enabled=enabled == "on", wake_url=wake_url)
        record_audit(
            actor_id=user.get("id"),
            entity_type="integration_settings",
            entity_id="make_outbox",
            action="updated",
            payload={"enabled": saved.get("enabled"), "wake_url_configured": bool(saved.get("wake_url"))},
        )
    except ValueError as exc:
        current = {"enabled": enabled == "on", "wake_url": wake_url}
        return templates.TemplateResponse(
            request=request,
            name="operations/settings.html",
            status_code=422,
            context=_settings_context(request, user, make_outbox=current, error=str(exc)),
        )
    return RedirectResponse(url="/configuracoes?saved=make_outbox#make-outbox", status_code=303)


@router.post("/configuracoes/make-outbox/testar")
def settings_make_outbox_test(
    request: Request,
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _admin(user)
    _require_csrf(request, csrf_token)
    result = test_make_outbox_wake()
    record_audit(
        actor_id=user.get("id"),
        entity_type="integration_settings",
        entity_id="make_outbox",
        action="wake_test",
        payload={"sent": bool(result.get("sent")), "status_code": result.get("status_code"), "reason": result.get("reason")},
    )
    if result.get("sent"):
        return RedirectResponse(url="/configuracoes?saved=make_outbox_test_ok#make-outbox", status_code=303)
    detail = result.get("error") or result.get("response") or result.get("reason") or "sem resposta"
    return templates.TemplateResponse(
        request=request,
        name="operations/settings.html",
        status_code=502,
        context=_settings_context(request, user, error=f"O webhook do Make não confirmou o teste: {str(detail)[:300]}"),
    )


@router.post("/configuracoes/ia")
def settings_ai_save(
    request: Request,
    enabled: str | None = Form(default=None),
    default_mode: str = Form("ai"),
    assistant_name: str = Form("Assistente de IA"),
    control_webhook_enabled: str | None = Form(default=None),
    control_webhook_url: str = Form(""),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _admin(user)
    _require_csrf(request, csrf_token)
    try:
        saved = save_ai_settings(
            enabled=enabled == "on",
            default_mode=default_mode,
            assistant_name=assistant_name,
            control_webhook_enabled=control_webhook_enabled == "on",
            control_webhook_url=control_webhook_url,
        )
        record_audit(
            actor_id=user.get("id"),
            entity_type="integration_settings",
            entity_id="ai_automation",
            action="updated",
            payload={
                "enabled": saved.get("enabled"),
                "default_mode": saved.get("default_mode"),
                "assistant_name": saved.get("assistant_name"),
                "control_webhook_enabled": saved.get("control_webhook_enabled"),
                "control_webhook_configured": bool(saved.get("control_webhook_url")),
            },
        )
    except ValueError as exc:
        current = {
            "enabled": enabled == "on",
            "default_mode": default_mode,
            "assistant_name": assistant_name,
            "control_webhook_enabled": control_webhook_enabled == "on",
            "control_webhook_url": control_webhook_url,
        }
        return templates.TemplateResponse(
            request=request,
            name="operations/settings.html",
            status_code=422,
            context=_settings_context(request, user, ai_automation=current, error=str(exc)),
        )
    return RedirectResponse(url="/configuracoes?saved=ai#ia", status_code=303)


@router.post("/configuracoes/ia-roteamento")
def settings_ai_routing_save(
    request: Request,
    enabled: str | None = Form(default=None),
    route_1_funnel_id: str = Form(""),
    route_1_stage_id: str = Form(""),
    route_2_funnel_id: str = Form(""),
    route_2_stage_id: str = Form(""),
    route_3_funnel_id: str = Form(""),
    route_3_stage_id: str = Form(""),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _admin(user)
    _require_csrf(request, csrf_token)
    routes = {
        "1": {"funnel_id": route_1_funnel_id, "stage_id": route_1_stage_id},
        "2": {"funnel_id": route_2_funnel_id, "stage_id": route_2_stage_id},
        "3": {"funnel_id": route_3_funnel_id, "stage_id": route_3_stage_id},
    }
    try:
        # Validação estrutural: a etapa escolhida precisa pertencer ao funil informado.
        funnels = {str(f.get("id")): f for f in list_funnels(include_inactive=False)}
        for code, route in routes.items():
            funnel_id = str(route.get("funnel_id") or "")
            stage_id = str(route.get("stage_id") or "")
            if not funnel_id and not stage_id:
                continue
            funnel = funnels.get(funnel_id)
            if not funnel:
                raise ValueError(f"Funil inválido na rota #{code}.")
            if not any(str(stage.get("id")) == stage_id and bool(stage.get("is_active", True)) for stage in funnel.get("stages") or []):
                raise ValueError(f"A etapa escolhida na rota #{code} não pertence ao funil selecionado ou está inativa.")
        saved = save_ai_routing_settings(enabled=enabled == "on", routes=routes)
        record_audit(
            actor_id=user.get("id"),
            entity_type="integration_settings",
            entity_id="ai_routing",
            action="updated",
            payload={"enabled": saved.get("enabled"), "routes": saved.get("routes")},
        )
    except ValueError as exc:
        current = {"enabled": enabled == "on", "routes": routes}
        return templates.TemplateResponse(
            request=request,
            name="operations/settings.html",
            status_code=422,
            context=_settings_context(request, user, ai_routing=current, error=str(exc)),
        )
    return RedirectResponse(url="/configuracoes?saved=ai_routing#ai-routing", status_code=303)


@router.post("/configuracoes/disparos")
def settings_dispatches_save(
    request: Request,
    enabled: str | None = Form(default=None),
    webhook_url: str = Form(""),
    template_key: str = Form(""),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _admin(user)
    _require_csrf(request, csrf_token)
    try:
        saved = save_dispatch_settings(enabled=enabled == "on", webhook_url=webhook_url, template_key=template_key)
        record_audit(
            actor_id=user.get("id"),
            entity_type="integration_settings",
            entity_id="dispatches",
            action="updated",
            payload={
                "enabled": saved.get("enabled"),
                "webhook_configured": bool(saved.get("webhook_url")),
                "template_key": saved.get("template_key"),
            },
        )
    except ValueError as exc:
        current = {"enabled": enabled == "on", "webhook_url": webhook_url, "template_key": template_key}
        return templates.TemplateResponse(
            request=request,
            name="operations/settings.html",
            status_code=422,
            context=_settings_context(request, user, dispatch_settings=current, error=str(exc)),
        )
    return RedirectResponse(url="/configuracoes?saved=dispatches#dispatches", status_code=303)


@router.post("/configuracoes/webhooks")
def settings_webhook_create(
    request: Request,
    name: str = Form(...),
    kind: str = Form(...),
    csrf_token: str = Form(...),
    user: dict = Depends(current_user),
):
    _admin(user)
    _require_csrf(request, csrf_token)
    try:
        webhook, secret = create_webhook(name=name, kind=kind)
        record_audit(
            actor_id=user.get("id"),
            entity_type="configured_webhook",
            entity_id=str(webhook.get("id")),
            action="created",
            payload={"name": webhook.get("name"), "kind": webhook.get("kind"), "public_id": webhook.get("public_id")},
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="operations/settings.html",
            status_code=422,
            context=_settings_context(request, user, error=str(exc)),
        )
    message = (
        "Webhook criado. O segredo foi salvo somente no arquivo local desta máquina e continuará disponível na área de Configurações."
        if get_settings().demo_mode
        else "Webhook criado. Copie o segredo agora; ele não será exibido novamente."
    )
    flash_token = _put_webhook_flash(user, webhook, secret, message)
    return RedirectResponse(url=f"/configuracoes?flash={flash_token}#credencial-webhook", status_code=303)


@router.post("/configuracoes/webhooks/{webhook_id}/alternar")
def settings_webhook_toggle(webhook_id: str, request: Request, active: str = Form("false"), csrf_token: str = Form(...), user: dict = Depends(current_user)):
    _admin(user)
    _require_csrf(request, csrf_token)
    desired = active == "true"
    try:
        row = set_webhook_active(webhook_id, desired)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record_audit(actor_id=user.get("id"), entity_type="configured_webhook", entity_id=webhook_id, action="enabled" if desired else "disabled", payload={"name": row.get("name")})
    return RedirectResponse(url="/configuracoes#webhooks", status_code=303)


@router.post("/configuracoes/webhooks/{webhook_id}/rotacionar")
def settings_webhook_rotate(webhook_id: str, request: Request, csrf_token: str = Form(...), user: dict = Depends(current_user)):
    _admin(user)
    _require_csrf(request, csrf_token)
    try:
        webhook, secret = rotate_webhook_secret(webhook_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record_audit(actor_id=user.get("id"), entity_type="configured_webhook", entity_id=webhook_id, action="secret_rotated", payload={"name": webhook.get("name")})
    message = (
        "Segredo rotacionado. O valor novo foi salvo somente no arquivo local desta máquina; o segredo anterior deixou de funcionar imediatamente."
        if get_settings().demo_mode
        else "Segredo rotacionado. O segredo anterior deixou de funcionar imediatamente."
    )
    flash_token = _put_webhook_flash(user, webhook, secret, message)
    return RedirectResponse(url=f"/configuracoes?flash={flash_token}#credencial-webhook", status_code=303)


@router.post("/configuracoes/webhooks/{webhook_id}/excluir")
def settings_webhook_delete(webhook_id: str, request: Request, csrf_token: str = Form(...), user: dict = Depends(current_user)):
    _admin(user)
    _require_csrf(request, csrf_token)
    try:
        delete_webhook(webhook_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record_audit(actor_id=user.get("id"), entity_type="configured_webhook", entity_id=webhook_id, action="deleted", payload={})
    return RedirectResponse(url="/configuracoes#webhooks", status_code=303)
