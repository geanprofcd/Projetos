from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 4
LOCAL_CONFIG_ENV = "VENDRA_LOCAL_CONFIG"
LOCAL_DIR_NAME = "VENDRA"
LOCAL_FILE_NAME = "credentials.local.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def local_config_path() -> Path:
    """Return the per-user, per-machine local credential/configuration path.

    On Windows this resolves to %LOCALAPPDATA%\\VENDRA\\credentials.local.json.
    The VENDRA_LOCAL_CONFIG environment variable may override the path for tests
    or controlled deployments.
    """
    override = os.getenv(LOCAL_CONFIG_ENV, "").strip()
    if not override:
        try:
            # Import tardio evita ciclo de importação e permite ler o mesmo valor do .env.
            from app.core.config import get_settings
            override = (get_settings().vendra_local_config or "").strip()
        except Exception:
            override = ""
    if override:
        return Path(override).expanduser().resolve()

    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA", "").strip()
        root = Path(base) if base else Path.home() / "AppData" / "Local"
    else:
        xdg = os.getenv("XDG_DATA_HOME", "").strip()
        root = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return root / LOCAL_DIR_NAME / LOCAL_FILE_NAME


def legacy_demo_path() -> Path:
    return project_root() / ".vendra-data" / "admin_integrations.json"


def default_local_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "test-local",
        "created_at": _now(),
        "updated_at": _now(),
        "admin": {
            "full_name": "Administrador Demo",
            "email": "admin@demo.local",
            "password": "admin123",
        },
        "whatsapp": {
            "enabled": False,
            "display_phone_number": "",
            "provider_key": "meta_cloud",
            "provider": "Meta WhatsApp Cloud API",
            "phone_number_id": "",
            "business_account_id": "",
            "notes": "",
            "updated_at": None,
        },
        "webhooks": [],
        "make_outbox": {
            "enabled": False,
            "wake_url": "",
            "updated_at": None,
        },
        "ai_automation": {
            "enabled": False,
            "default_mode": "ai",
            "assistant_name": "Assistente de IA",
            "control_webhook_enabled": False,
            "control_webhook_url": "",
            "updated_at": None,
        },
        "ai_routing": {
            "enabled": False,
            "routes": {
                "1": {"funnel_id": "", "stage_id": ""},
                "2": {"funnel_id": "", "stage_id": ""},
                "3": {"funnel_id": "", "stage_id": ""},
            },
            "updated_at": None,
        },
        "dispatches": {
            "enabled": False,
            "webhook_url": "",
            "template_key": "",
            "updated_at": None,
        },
    }


def _merge_state(raw: Any) -> dict[str, Any]:
    state = default_local_state()
    if not isinstance(raw, dict):
        return state

    admin = raw.get("admin")
    if isinstance(admin, dict):
        state["admin"].update({
            key: admin.get(key)
            for key in ("full_name", "email", "password")
            if admin.get(key) is not None
        })

    whatsapp = raw.get("whatsapp")
    if isinstance(whatsapp, dict):
        state["whatsapp"].update(whatsapp)

    webhooks = raw.get("webhooks")
    if isinstance(webhooks, list):
        state["webhooks"] = [dict(item) for item in webhooks if isinstance(item, dict)]

    make_outbox = raw.get("make_outbox")
    if isinstance(make_outbox, dict):
        state["make_outbox"].update({
            key: make_outbox.get(key)
            for key in ("enabled", "wake_url", "updated_at")
            if make_outbox.get(key) is not None
        })

    ai_automation = raw.get("ai_automation")
    if isinstance(ai_automation, dict):
        state["ai_automation"].update({
            key: ai_automation.get(key)
            for key in ("enabled", "default_mode", "assistant_name", "control_webhook_enabled", "control_webhook_url", "updated_at")
            if ai_automation.get(key) is not None
        })

    ai_routing = raw.get("ai_routing")
    if isinstance(ai_routing, dict):
        state["ai_routing"]["enabled"] = bool(ai_routing.get("enabled"))
        raw_routes = ai_routing.get("routes")
        if isinstance(raw_routes, dict):
            for code in ("1", "2", "3"):
                route = raw_routes.get(code)
                if isinstance(route, dict):
                    state["ai_routing"]["routes"][code].update({
                        "funnel_id": str(route.get("funnel_id") or ""),
                        "stage_id": str(route.get("stage_id") or ""),
                    })
        if ai_routing.get("updated_at") is not None:
            state["ai_routing"]["updated_at"] = ai_routing.get("updated_at")

    dispatches = raw.get("dispatches")
    if isinstance(dispatches, dict):
        state["dispatches"].update({
            key: dispatches.get(key)
            for key in ("enabled", "webhook_url", "template_key", "updated_at")
            if dispatches.get(key) is not None
        })

    state["schema_version"] = SCHEMA_VERSION
    state["mode"] = "test-local"
    state["created_at"] = raw.get("created_at") or state["created_at"]
    state["updated_at"] = raw.get("updated_at") or state["updated_at"]
    if raw.get("migrated_from"):
        state["migrated_from"] = raw.get("migrated_from")
    if raw.get("migrated_at"):
        state["migrated_at"] = raw.get("migrated_at")
    return state


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = deepcopy(data)
    payload["schema_version"] = SCHEMA_VERSION
    payload["mode"] = "test-local"
    payload["updated_at"] = _now()

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        path.parent.chmod(0o700)
        tmp.chmod(0o600)
    except OSError:
        pass
    tmp.replace(path)


def _migrate_legacy_if_needed(path: Path) -> dict[str, Any] | None:
    legacy = legacy_demo_path()
    if path.exists() or not legacy.exists():
        return None
    old = _read_json(legacy)
    if not isinstance(old, dict):
        return None

    state = default_local_state()
    if isinstance(old.get("whatsapp"), dict):
        state["whatsapp"].update(old["whatsapp"])
    if isinstance(old.get("webhooks"), list):
        state["webhooks"] = [dict(item) for item in old["webhooks"] if isinstance(item, dict)]
    state["migrated_from"] = str(legacy)
    state["migrated_at"] = _now()
    _write_json(path, state)
    return state


def load_local_state(*, create_if_missing: bool = True) -> dict[str, Any]:
    path = local_config_path()
    migrated = _migrate_legacy_if_needed(path)
    if migrated is not None:
        return _merge_state(migrated)

    if path.exists():
        return _merge_state(_read_json(path))

    state = default_local_state()
    if create_if_missing:
        _write_json(path, state)
    return state


def save_local_state(data: dict[str, Any]) -> dict[str, Any]:
    state = _merge_state(data)
    _write_json(local_config_path(), state)
    return state


def demo_admin_credentials() -> dict[str, str]:
    state = load_local_state()
    admin = state.get("admin") or {}
    return {
        "full_name": str(admin.get("full_name") or "Administrador Demo"),
        "email": str(admin.get("email") or "admin@demo.local"),
        "password": str(admin.get("password") or "admin123"),
    }


def local_config_info() -> dict[str, Any]:
    path = local_config_path()
    state = load_local_state()
    return {
        "path": str(path),
        "exists": path.exists(),
        "mode": state.get("mode") or "test-local",
        "admin_email": (state.get("admin") or {}).get("email") or "admin@demo.local",
        "admin_password": (state.get("admin") or {}).get("password") or "admin123",
        "webhook_secrets_persisted": any(bool(row.get("secret")) for row in state.get("webhooks") or []),
        "make_outbox_wake_configured": bool((state.get("make_outbox") or {}).get("wake_url")),
        "ai_automation_configured": bool((state.get("ai_automation") or {}).get("enabled")),
        "dispatch_webhook_configured": bool((state.get("dispatches") or {}).get("webhook_url")),
    }
