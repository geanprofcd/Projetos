from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from app.services.admin_settings_service import get_make_outbox_settings
from app.core.config import get_settings

logger = logging.getLogger(__name__)


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
        raise RuntimeError("Ambiente de homologação: envio externo bloqueado.")
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
        with urllib.request.urlopen(request, timeout=timeout) as response:
            sample = response.read(512).decode("utf-8", errors="replace")
            return int(getattr(response, "status", 200)), sample
    except urllib.error.HTTPError as exc:
        sample = exc.read(512).decode("utf-8", errors="replace")
        return int(exc.code), sample


def send_make_outbox_wake(item: dict[str, Any], *, event: str = "whatsapp_outbox.created", timeout: float = 4.0) -> dict[str, Any]:
    config = get_make_outbox_settings()
    url = str(config.get("wake_url") or "").strip()
    if not config.get("enabled") or not url:
        return {"sent": False, "configured": bool(url), "enabled": bool(config.get("enabled")), "reason": "disabled_or_missing"}
    try:
        status, response_sample = _post_json(url, _payload(item, event=event), timeout=timeout)
        if 200 <= status < 300:
            return {"sent": True, "status_code": status, "response": response_sample}
        return {"sent": False, "status_code": status, "response": response_sample, "reason": "http_error"}
    except Exception as exc:  # O wake nunca pode cancelar a outbox durável.
        logger.warning("Falha ao avisar o Make sobre a outbox %s: %s", item.get("id"), exc)
        return {"sent": False, "reason": "exception", "error": str(exc)[:500]}


def notify_make_outbox_async(item: dict[str, Any]) -> bool:
    config = get_make_outbox_settings()
    if not config.get("enabled") or not str(config.get("wake_url") or "").strip():
        return False

    snapshot = dict(item)

    def worker() -> None:
        result = send_make_outbox_wake(snapshot)
        if not result.get("sent"):
            logger.warning(
                "Wake da outbox %s não confirmado; item permanece na fila para recuperação por polling. Resultado=%s",
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
