from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from urllib.parse import urlparse
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.local_credentials_service import default_local_state, load_local_state, save_local_state

WEBHOOK_KINDS = {
    "whatsapp_text": "WhatsApp / Make — entrada e ponte de saída",
    "generic_json": "Evento JSON genérico",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_demo() -> dict[str, Any]:
    return load_local_state()


def _save_demo(data: dict[str, Any]) -> None:
    save_local_state(data)


def _slug(value: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return (raw or "webhook")[:40]


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _clean_phone(value: str) -> str:
    text = value.strip()
    digits = re.sub(r"\D", "", text)
    if text and len(digits) < 10:
        raise ValueError("Informe um número de WhatsApp válido com DDI e DDD.")
    return text


def get_whatsapp_settings() -> dict[str, Any]:
    settings = get_settings()
    if settings.demo_mode:
        return dict(_load_demo()["whatsapp"])
    rows = (
        get_admin_client()
        .table("integration_settings")
        .select("settings,updated_at")
        .eq("key", "whatsapp")
        .limit(1)
        .execute()
        .data
        or []
    )
    result = default_local_state()["whatsapp"]
    if rows:
        result.update(rows[0].get("settings") or {})
        result["updated_at"] = rows[0].get("updated_at")
    return result


def save_whatsapp_settings(
    *,
    enabled: bool,
    display_phone_number: str,
    provider_key: str,
    provider: str,
    phone_number_id: str,
    business_account_id: str,
    notes: str,
) -> dict[str, Any]:
    display_phone_number = _clean_phone(display_phone_number)
    from app.services.whatsapp_provider_catalog import WHATSAPP_PROVIDERS

    provider_key = provider_key.strip()[:80]
    if provider_key not in WHATSAPP_PROVIDERS:
        provider_key = "generic_bsp"
    canonical_provider = WHATSAPP_PROVIDERS[provider_key]["name"]
    provider = provider.strip()[:120]
    phone_number_id = phone_number_id.strip()[:160]
    business_account_id = business_account_id.strip()[:160]
    notes = notes.strip()[:1000]
    if enabled and not display_phone_number:
        raise ValueError("Informe o número do WhatsApp antes de ativar o canal.")

    payload = {
        "enabled": bool(enabled),
        "display_phone_number": display_phone_number,
        "provider_key": provider_key,
        "provider": provider or canonical_provider,
        "phone_number_id": phone_number_id,
        "business_account_id": business_account_id,
        "notes": notes,
        "updated_at": _now(),
    }
    settings = get_settings()
    if settings.demo_mode:
        state = _load_demo()
        state["whatsapp"] = payload
        _save_demo(state)
        return dict(payload)

    admin = get_admin_client()
    existing = admin.table("integration_settings").select("key").eq("key", "whatsapp").limit(1).execute().data or []
    row = {"key": "whatsapp", "settings": payload, "updated_at": payload["updated_at"]}
    if existing:
        admin.table("integration_settings").update(row).eq("key", "whatsapp").execute()
    else:
        admin.table("integration_settings").insert(row).execute()
    return dict(payload)


def list_webhooks() -> list[dict[str, Any]]:
    settings = get_settings()
    if settings.demo_mode:
        source_rows = [dict(row) for row in _load_demo()["webhooks"]]
        rows = []
        for source in source_rows:
            row = {key: value for key, value in source.items() if key not in {"secret_hash", "secret"}}
            # Teste local deliberado: permite recuperar o segredo salvo nesta máquina.
            # Em produção/Supabase esse campo nunca existe.
            if source.get("secret"):
                row["local_secret"] = source.get("secret")
            rows.append(row)
    else:
        rows = (
            get_admin_client()
            .table("configured_webhooks")
            .select("id,name,slug,public_id,kind,active,last_used_at,last_status,created_at,updated_at")
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
    for row in rows:
        row["kind_label"] = WEBHOOK_KINDS.get(row.get("kind"), row.get("kind") or "Webhook")
    rows.sort(key=lambda row: row.get("created_at") or "", reverse=True)
    return rows


def create_webhook(*, name: str, kind: str) -> tuple[dict[str, Any], str]:
    name = name.strip()[:120]
    if not name:
        raise ValueError("Informe um nome para o webhook.")
    if kind not in WEBHOOK_KINDS:
        raise ValueError("Tipo de webhook inválido.")
    secret = secrets.token_urlsafe(32)
    now = _now()
    row = {
        "id": secrets.token_hex(16),
        "name": name,
        "slug": _slug(name),
        "public_id": secrets.token_urlsafe(10).replace("-", "").replace("_", "")[:14],
        "kind": kind,
        "active": True,
        "secret_hash": _hash_secret(secret),
        "last_used_at": None,
        "last_status": None,
        "created_at": now,
        "updated_at": now,
    }
    settings = get_settings()
    if settings.demo_mode:
        state = _load_demo()
        local_row = dict(row)
        # Ambiente de teste local: preserva o segredo no arquivo por usuário/máquina
        # para que a integração Make possa ser reconfigurada após reinícios.
        local_row["secret"] = secret
        state["webhooks"].append(local_row)
        _save_demo(state)
    else:
        payload = dict(row)
        # O Postgres gera UUID; o id local em hexadecimal não deve ser forçado.
        payload.pop("id", None)
        inserted = get_admin_client().table("configured_webhooks").insert(payload).execute().data[0]
        row.update(inserted)
    public = {key: value for key, value in row.items() if key not in {"secret_hash", "secret"}}
    public["kind_label"] = WEBHOOK_KINDS[kind]
    return public, secret


def _find_webhook(public_id: str) -> dict[str, Any] | None:
    settings = get_settings()
    if settings.demo_mode:
        return next((dict(row) for row in _load_demo()["webhooks"] if row.get("public_id") == public_id), None)
    rows = get_admin_client().table("configured_webhooks").select("*").eq("public_id", public_id).limit(1).execute().data or []
    return rows[0] if rows else None


def validate_webhook(public_id: str, secret: str | None) -> dict[str, Any] | None:
    row = _find_webhook(public_id)
    if not row or not row.get("active") or not secret:
        return None
    if not hmac.compare_digest(str(row.get("secret_hash") or ""), _hash_secret(secret)):
        return None
    return row


def _update_webhook(webhook_id: str, values: dict[str, Any]) -> dict[str, Any]:
    values = {**values, "updated_at": _now()}
    settings = get_settings()
    if settings.demo_mode:
        state = _load_demo()
        for row in state["webhooks"]:
            if str(row.get("id")) == str(webhook_id):
                row.update(values)
                _save_demo(state)
                return dict(row)
        raise ValueError("Webhook não encontrado.")
    rows = get_admin_client().table("configured_webhooks").update(values).eq("id", webhook_id).execute().data or []
    if not rows:
        raise ValueError("Webhook não encontrado.")
    return rows[0]


def set_webhook_active(webhook_id: str, active: bool) -> dict[str, Any]:
    return _update_webhook(webhook_id, {"active": bool(active)})


def rotate_webhook_secret(webhook_id: str) -> tuple[dict[str, Any], str]:
    secret = secrets.token_urlsafe(32)
    values = {"secret_hash": _hash_secret(secret), "last_status": "secret_rotated"}
    if get_settings().demo_mode:
        values["secret"] = secret
    row = _update_webhook(webhook_id, values)
    public = {key: value for key, value in row.items() if key not in {"secret_hash", "secret"}}
    public["kind_label"] = WEBHOOK_KINDS.get(row.get("kind"), row.get("kind"))
    return public, secret


def delete_webhook(webhook_id: str) -> None:
    settings = get_settings()
    if settings.demo_mode:
        state = _load_demo()
        before = len(state["webhooks"])
        state["webhooks"] = [row for row in state["webhooks"] if str(row.get("id")) != str(webhook_id)]
        if len(state["webhooks"]) == before:
            raise ValueError("Webhook não encontrado.")
        _save_demo(state)
        return
    get_admin_client().table("configured_webhooks").delete().eq("id", webhook_id).execute()


def mark_webhook_used(webhook: dict[str, Any], status: str) -> None:
    webhook_id = str(webhook.get("id") or "")
    if not webhook_id:
        return
    try:
        _update_webhook(webhook_id, {"last_used_at": _now(), "last_status": status[:80]})
    except Exception:
        # Métrica de uso não pode derrubar o processamento do webhook.
        return



def validate_any_webhook_secret(secret: str | None, *, kind: str | None = None) -> dict[str, Any] | None:
    if not secret:
        return None
    secret_hash = _hash_secret(secret)
    settings = get_settings()
    if settings.demo_mode:
        rows = _load_demo()["webhooks"]
    else:
        query = get_admin_client().table("configured_webhooks").select("secret_hash,kind,active").eq("active", True)
        if kind:
            query = query.eq("kind", kind)
        rows = query.execute().data or []
    for row in rows:
        if not row.get("active"):
            continue
        if kind and row.get("kind") != kind:
            continue
        if hmac.compare_digest(str(row.get("secret_hash") or ""), secret_hash):
            return dict(row)
    return None


def public_whatsapp_channel() -> dict[str, Any]:
    row = get_whatsapp_settings()
    return {
        "enabled": bool(row.get("enabled")),
        "display_phone_number": row.get("display_phone_number") or None,
        "provider_key": row.get("provider_key") or "meta_cloud",
        "provider": row.get("provider") or None,
        "phone_number_id": row.get("phone_number_id") or None,
        "business_account_id": row.get("business_account_id") or None,
    }

def get_make_outbox_settings() -> dict[str, Any]:
    """Configuration for the instant Make wake webhook used by outbound WhatsApp."""
    settings = get_settings()
    if settings.demo_mode:
        return dict(_load_demo().get("make_outbox") or default_local_state()["make_outbox"])
    rows = (
        get_admin_client()
        .table("integration_settings")
        .select("settings,updated_at")
        .eq("key", "make_outbox")
        .limit(1)
        .execute()
        .data
        or []
    )
    result = dict(default_local_state()["make_outbox"])
    if rows:
        result.update(rows[0].get("settings") or {})
        result["updated_at"] = rows[0].get("updated_at")
    return result


def _validate_wake_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ValueError("Informe uma URL válida do Custom Webhook do Make.")
    if parsed.scheme == "http" and (parsed.hostname or "").lower() not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Use HTTPS para o webhook do Make. HTTP é permitido apenas em localhost para testes.")
    return value


def save_make_outbox_settings(*, enabled: bool, wake_url: str) -> dict[str, Any]:
    wake_url = _validate_wake_url(wake_url)
    if enabled and not wake_url:
        raise ValueError("Informe a URL do Custom Webhook do Make antes de ativar o disparo instantâneo.")
    payload = {
        "enabled": bool(enabled),
        "wake_url": wake_url,
        "updated_at": _now(),
    }
    settings = get_settings()
    if settings.demo_mode:
        state = _load_demo()
        state["make_outbox"] = payload
        _save_demo(state)
        return dict(payload)

    admin = get_admin_client()
    existing = admin.table("integration_settings").select("key").eq("key", "make_outbox").limit(1).execute().data or []
    row = {"key": "make_outbox", "settings": payload, "updated_at": payload["updated_at"]}
    if existing:
        admin.table("integration_settings").update(row).eq("key", "make_outbox").execute()
    else:
        admin.table("integration_settings").insert(row).execute()
    return dict(payload)



def get_ai_settings() -> dict[str, Any]:
    settings = get_settings()
    if settings.demo_mode:
        return dict(_load_demo().get("ai_automation") or default_local_state()["ai_automation"])
    rows = (
        get_admin_client()
        .table("integration_settings")
        .select("settings,updated_at")
        .eq("key", "ai_automation")
        .limit(1)
        .execute()
        .data
        or []
    )
    result = dict(default_local_state()["ai_automation"])
    if rows:
        result.update(rows[0].get("settings") or {})
        result["updated_at"] = rows[0].get("updated_at")
    return result


def save_ai_settings(
    *,
    enabled: bool,
    default_mode: str,
    assistant_name: str,
    control_webhook_enabled: bool,
    control_webhook_url: str,
) -> dict[str, Any]:
    default_mode = str(default_mode or "ai").strip().lower()
    if default_mode not in {"ai", "human"}:
        raise ValueError("Modo padrão da IA inválido.")
    assistant_name = str(assistant_name or "").strip()[:120]
    if not assistant_name:
        raise ValueError("Informe um nome para identificar a IA nas conversas.")
    control_webhook_url = _validate_wake_url(control_webhook_url)
    if control_webhook_enabled and not control_webhook_url:
        raise ValueError("Informe a URL do webhook de controle do Make antes de ativá-lo.")
    payload = {
        "enabled": bool(enabled),
        "default_mode": default_mode,
        "assistant_name": assistant_name,
        "control_webhook_enabled": bool(control_webhook_enabled),
        "control_webhook_url": control_webhook_url,
        "updated_at": _now(),
    }
    settings = get_settings()
    if settings.demo_mode:
        state = _load_demo()
        state["ai_automation"] = payload
        _save_demo(state)
        return dict(payload)
    admin = get_admin_client()
    existing = admin.table("integration_settings").select("key").eq("key", "ai_automation").limit(1).execute().data or []
    row = {"key": "ai_automation", "settings": payload, "updated_at": payload["updated_at"]}
    if existing:
        admin.table("integration_settings").update(row).eq("key", "ai_automation").execute()
    else:
        admin.table("integration_settings").insert(row).execute()
    return dict(payload)


def _normalize_route_label(value: str | None) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.casefold().replace("-", " ").split())


def _standard_ai_routing_defaults() -> dict[str, Any] | None:
    """Resolve o mapa comercial padrão sem depender de IDs fixos.

    O fallback só é usado quando o roteamento nunca foi salvo pelo administrador.
    Assim, instalações novas/local-demo funcionam de imediato e configurações
    explícitas continuam tendo prioridade total.
    """
    from app.services.funnel_service import list_funnels

    targets = {"1": "novo lead", "2": "qualificacao", "3": "proposta"}
    funnels = list_funnels(include_inactive=False)
    preferred = sorted(
        funnels,
        key=lambda f: (
            0 if _normalize_route_label(f.get("name")) in {"funil comercial", "comercial"} else 1,
            _normalize_route_label(f.get("name")),
        ),
    )
    for funnel in preferred:
        active_stages = [s for s in (funnel.get("stages") or []) if bool(s.get("is_active", True))]
        by_name = {_normalize_route_label(stage.get("name")): stage for stage in active_stages}
        if not all(label in by_name for label in targets.values()):
            continue
        return {
            "enabled": True,
            "routes": {
                code: {
                    "funnel_id": str(funnel.get("id") or ""),
                    "stage_id": str(by_name[label].get("id") or ""),
                }
                for code, label in targets.items()
            },
            "updated_at": None,
            "source": "standard_default",
        }
    return None


def _with_standard_ai_routing_fallback(result: dict[str, Any]) -> dict[str, Any]:
    routes = result.get("routes") or {}
    has_explicit_route = any(
        bool((routes.get(code) or {}).get("funnel_id")) or bool((routes.get(code) or {}).get("stage_id"))
        for code in ("1", "2", "3")
    )
    # updated_at é preenchido sempre que o administrador salva o formulário,
    # inclusive para desligar o roteamento. Nunca sobrescreva essa decisão.
    if result.get("updated_at") or has_explicit_route:
        return result
    fallback = _standard_ai_routing_defaults()
    if not fallback:
        return result
    merged = dict(result)
    merged.update(fallback)
    return merged


def get_ai_routing_settings() -> dict[str, Any]:
    settings = get_settings()
    default = default_local_state()["ai_routing"]
    if settings.demo_mode:
        current = _load_demo().get("ai_routing") or default
        result = dict(default)
        result["routes"] = {code: dict(values) for code, values in (default.get("routes") or {}).items()}
        result.update({k: v for k, v in current.items() if k != "routes"})
        for code, values in (current.get("routes") or {}).items():
            if code in result["routes"] and isinstance(values, dict):
                result["routes"][code].update(values)
        return _with_standard_ai_routing_fallback(result)
    rows = (
        get_admin_client()
        .table("integration_settings")
        .select("settings,updated_at")
        .eq("key", "ai_routing")
        .limit(1)
        .execute()
        .data
        or []
    )
    result = dict(default)
    result["routes"] = {code: dict(values) for code, values in (default.get("routes") or {}).items()}
    if rows:
        stored = rows[0].get("settings") or {}
        result.update({k: v for k, v in stored.items() if k != "routes"})
        for code, values in (stored.get("routes") or {}).items():
            if code in result["routes"] and isinstance(values, dict):
                result["routes"][code].update(values)
        result["updated_at"] = rows[0].get("updated_at")
    return _with_standard_ai_routing_fallback(result)


def save_ai_routing_settings(*, enabled: bool, routes: dict[str, dict[str, str]]) -> dict[str, Any]:
    normalized: dict[str, dict[str, str]] = {}
    for code in ("1", "2", "3"):
        route = routes.get(code) or {}
        normalized[code] = {
            "funnel_id": str(route.get("funnel_id") or "").strip()[:120],
            "stage_id": str(route.get("stage_id") or "").strip()[:120],
        }
        if bool(enabled) and bool(normalized[code]["funnel_id"]) != bool(normalized[code]["stage_id"]):
            raise ValueError(f"Configure funil e etapa juntos para a rota #{code}.")
    payload = {"enabled": bool(enabled), "routes": normalized, "updated_at": _now()}
    settings = get_settings()
    if settings.demo_mode:
        state = _load_demo()
        state["ai_routing"] = payload
        _save_demo(state)
        return dict(payload)
    admin = get_admin_client()
    existing = admin.table("integration_settings").select("key").eq("key", "ai_routing").limit(1).execute().data or []
    row = {"key": "ai_routing", "settings": payload, "updated_at": payload["updated_at"]}
    if existing:
        admin.table("integration_settings").update(row).eq("key", "ai_routing").execute()
    else:
        admin.table("integration_settings").insert(row).execute()
    return dict(payload)


def get_dispatch_settings() -> dict[str, Any]:
    settings = get_settings()
    if settings.demo_mode:
        return dict(_load_demo().get("dispatches") or default_local_state()["dispatches"])
    rows = (
        get_admin_client()
        .table("integration_settings")
        .select("settings,updated_at")
        .eq("key", "dispatches")
        .limit(1)
        .execute()
        .data
        or []
    )
    result = dict(default_local_state()["dispatches"])
    if rows:
        result.update(rows[0].get("settings") or {})
        result["updated_at"] = rows[0].get("updated_at")
    return result


def save_dispatch_settings(*, enabled: bool, webhook_url: str, template_key: str) -> dict[str, Any]:
    webhook_url = _validate_wake_url(webhook_url)
    template_key = str(template_key or "").strip()[:120]
    if enabled and not webhook_url:
        raise ValueError("Informe a URL do Custom Webhook do Make antes de ativar Disparos.")
    payload = {
        "enabled": bool(enabled),
        "webhook_url": webhook_url,
        "template_key": template_key,
        "updated_at": _now(),
    }
    settings = get_settings()
    if settings.demo_mode:
        state = _load_demo()
        state["dispatches"] = payload
        _save_demo(state)
        return dict(payload)
    admin = get_admin_client()
    existing = admin.table("integration_settings").select("key").eq("key", "dispatches").limit(1).execute().data or []
    row = {"key": "dispatches", "settings": payload, "updated_at": payload["updated_at"]}
    if existing:
        admin.table("integration_settings").update(row).eq("key", "dispatches").execute()
    else:
        admin.table("integration_settings").insert(row).execute()
    return dict(payload)
