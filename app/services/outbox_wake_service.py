from __future__ import annotations

import json
import logging
import threading
import os
import urllib.error
import urllib.request
import re
from urllib.parse import urlsplit
from uuid import UUID
from datetime import datetime, timezone
from typing import Any

from app.services.admin_settings_service import get_make_outbox_settings
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _configuration():
    settings = get_settings()
    if settings.app_env != 'staging':
        config = get_make_outbox_settings()
        if (settings.app_env != 'production' or not config.get('enabled')
                or not getattr(settings, 'whatsapp_persistent_control_enabled', False)):
            return config
        parsed = urlsplit(str(config.get('wake_url') or ''))
        secret = os.environ.get('VENDRA_OUTBOX_WAKE_SECRET', '')
        allowed = os.environ.get('VENDRA_BRIDGE_ALLOWED_PHONES', '')
        all_phones = os.environ.get('VENDRA_BRIDGE_ALLOW_ALL_PHONES', 'false')
        if (settings.demo_mode or settings.supabase_url.rstrip('/') != 'https://znkjibqcikuigfwfsbjb.supabase.co'
                or parsed.scheme != 'https' or parsed.netloc != 'hook.us2.make.com'
                or not re.fullmatch(r'/[a-zA-Z0-9]{20,100}', parsed.path)
                or parsed.query or parsed.fragment or len(secret) < 32
                or all_phones not in ('true','false') or (not allowed.strip() and all_phones != 'true')):
            raise ValueError('Perfil de notificacao de producao invalido.')
        return {**config, '_production_protected': True, '_wake_secret': secret}
    if not getattr(settings, 'whatsapp_staging_wake_enabled', False):
        return {'enabled': False}
    url = settings.whatsapp_staging_wake_url
    parsed = urlsplit(url)
    if (settings.demo_mode or not settings.whatsapp_persistent_control_enabled
            or settings.supabase_url.rstrip('/') != 'https://ljufhqnadzltqbtdaulv.supabase.co'
            or parsed.scheme != 'https' or parsed.netloc != 'hook.us2.make.com'
            or not re.fullmatch(r'/[a-zA-Z0-9]{20,100}', parsed.path)
            or parsed.query or parsed.fragment or len(settings.whatsapp_staging_wake_token) < 32
            or not settings.whatsapp_staging_wake_phone):
        raise ValueError('Perfil de notificação STAGING inválido.')
    UUID(settings.whatsapp_staging_wake_ticket_id)
    return {'enabled': True, 'wake_url': url}


def _validate_staging_item(item):
    from app.db.supabase import get_admin_client
    settings = get_settings()
    if str(item.get('ticket_id')) != settings.whatsapp_staging_wake_ticket_id:
        raise ValueError('Atendimento fora do teste autorizado.')
    oid = str(UUID(str(item.get('id')))); mid = str(UUID(str(item.get('message_id'))))
    db = get_admin_client()
    rows = db.table('whatsapp_outbox').select('id,ticket_id,message_id,phone,status,provider_message_id').eq('id', oid).limit(1).execute().data or []
    if len(rows) != 1:
        raise ValueError('Saída indisponível.')
    row = rows[0]
    def phone(value):
        value = re.sub(r'\D', '', str(value or ''))
        return value[:4]+value[5:] if len(value) == 13 and value[4] == '9' else value
    if (row['ticket_id'] != settings.whatsapp_staging_wake_ticket_id or row['message_id'] != mid
            or row['status'] != 'pending' or row.get('provider_message_id')
            or phone(row['phone']) != phone(settings.whatsapp_staging_wake_phone)):
        raise ValueError('Saída fora do teste autorizado ou já processada.')


def _validate_production_item(item):
    from app.db.supabase import get_admin_client
    oid, tid, mid = [str(UUID(str(item.get(k)))) for k in ('id', 'ticket_id', 'message_id')]
    rows = (get_admin_client().table('whatsapp_outbox')
        .select('id,ticket_id,message_id,phone,status,provider_message_id')
        .eq('id', oid).limit(1).execute().data or [])
    def phone(value):
        value = re.sub(r'\D', '', str(value or ''))
        if not re.fullmatch(r'55\d{10,11}', value):
            raise ValueError('Telefone de saida invalido.')
        return value[:4]+value[5:] if len(value)==13 and value[4]=='9' else value
    allowed = {phone(p) for p in os.environ.get('VENDRA_BRIDGE_ALLOWED_PHONES', '').split(',') if p.strip()}
    if (len(rows) != 1 or rows[0]['ticket_id'] != tid or rows[0]['message_id'] != mid
            or rows[0]['status'] != 'pending' or rows[0].get('provider_message_id')
            or (phone(rows[0]['phone']) not in allowed
                and os.environ.get('VENDRA_BRIDGE_ALLOW_ALL_PHONES', 'false') != 'true')):
        raise ValueError('Saida fora do escopo autorizado ou ja processada.')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _payload(item: dict[str, Any], *, event: str = "whatsapp_outbox.created") -> dict[str, Any]:
    return {
        "event": event,
        "outbox_id": str(item.get("id") or ""),
        "ticket_id": str(item.get("ticket_id") or ""),
        "message_id": str(item.get("message_id") or ""),
        "created_at": item.get("created_at") or _now(),
    }


def _post_json(url: str, payload: dict[str, Any], *, timeout: float = 4.0) -> tuple[int, str]:
    if get_settings().app_env == "staging":
        config = _configuration()
        if not config.get('enabled') or url != config.get('wake_url'):
            raise RuntimeError('Ambiente de homologação: envio externo bloqueado.')
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "VENDRA-Outbox-Wake/0.0.3",
        },
    )
    try:
        # Não encaminhar o segredo do wake para outro host após redirecionamento.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            sample = response.read(512).decode("utf-8", errors="replace")
            return int(getattr(response, "status", 200)), sample
    except urllib.error.HTTPError as exc:
        sample = exc.read(512).decode("utf-8", errors="replace")
        return int(exc.code), sample


def send_make_outbox_wake(item: dict[str, Any], *, event: str = "whatsapp_outbox.created", timeout: float = 4.0) -> dict[str, Any]:
    try:
        config = _configuration()
    except Exception:
        return {'sent': False, 'reason': 'invalid_configuration'}
    url = str(config.get("wake_url") or "").strip()
    if not config.get("enabled") or not url:
        return {"sent": False, "configured": bool(url), "enabled": bool(config.get("enabled")), "reason": "disabled_or_missing"}
    try:
        payload = _payload(item, event=event)
        if get_settings().app_env == 'staging':
            _validate_staging_item(item)
            payload['wake_secret'] = get_settings().whatsapp_staging_wake_token
            timeout = max(timeout, 10.0)
        elif config.get('_production_protected'):
            _validate_production_item(item)
            payload['wake_secret'] = config['_wake_secret']
            timeout = max(timeout, 10.0)
        status, response_sample = _post_json(url, payload, timeout=timeout)
        if 200 <= status < 300:
            return {"sent": True, "status_code": status, "response": response_sample}
        return {"sent": False, "status_code": status, "response": response_sample, "reason": "http_error"}
    except Exception as exc:  # O wake nunca pode cancelar a outbox durável.
        logger.warning("Falha ao avisar o Make sobre a outbox %s: %s", item.get("id"), type(exc).__name__)
        return {"sent": False, "reason": "exception", "error_type": type(exc).__name__}


def notify_make_outbox_async(item: dict[str, Any]) -> bool:
    try:
        config = _configuration()
    except Exception:
        return False
    if not config.get("enabled") or not str(config.get("wake_url") or "").strip():
        return False

    snapshot = dict(item)

    def worker() -> None:
        result = send_make_outbox_wake(snapshot)
        if not result.get("sent"):
            logger.warning(
                "Wake da outbox %s não confirmado; comando persistido exige conferência. Resultado=%s",
                snapshot.get("id"),
                result,
            )

    threading.Thread(target=worker, name=f"vendra-outbox-wake-{snapshot.get('id')}", daemon=True).start()
    return True


def test_make_outbox_wake() -> dict[str, Any]:
    probe = {
        "id": "probe",
        "ticket_id": "",
        "message_id": "",
        "created_at": _now(),
    }
    return send_make_outbox_wake(probe, event="whatsapp_outbox.probe", timeout=6.0)
