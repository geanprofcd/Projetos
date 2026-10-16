from functools import lru_cache
import json
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VENDRA"
    app_env: str = "development"
    app_version: str = "0.0.23"
    secret_key: str = "change-me"
    cookie_secure: bool = False
    session_hours: int = 8
    demo_mode: bool = True
    vendra_local_config: str | None = None

    public_app_url: str | None = None
    meta_access_token: str | None = None
    meta_waba_id: str | None = None
    meta_phone_number_id: str | None = None
    meta_graph_version: str = "v24.0"

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_ssl: bool = False

    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    make_webhook_secret: str | None = None
    dispatch_transport_enabled: bool = False
    dispatch_transport_url: str | None = None
    dispatch_transport_secret: str | None = None
    dispatch_allowed_phones: str = ''
    whatsapp_persistent_control_enabled: bool = False
    attachment_bucket: str = "ticket-attachments"
    attachment_max_mb: int = 15
    attachment_video_max_mb: int = 50
    live_poll_seconds: int = 4
    integration_claim_ttl_seconds: int = 120
    make_worker_name: str = "make-whatsapp"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def supabase_configured(self) -> bool:
        """True only when real-looking Supabase credentials are present.

        The starter ships with explicit placeholders in .env.example. Those values
        are useful for setup but must not be reported as an operational Supabase
        configuration by /health or the integrations readiness panel.
        """
        if self.demo_mode:
            return False
        values = (self.supabase_url, self.supabase_anon_key, self.supabase_service_role_key)
        if not all(value and value.strip() for value in values):
            return False
        placeholder_markers = ("SEU-PROJETO", "SUA_ANON_KEY", "SUA_SERVICE_ROLE_KEY")
        joined = " ".join(value or "" for value in values)
        return not any(marker in joined for marker in placeholder_markers)


@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=os.environ.get('VENDRA_ENV_FILE', '.env') or None)


def installed_version() -> str:
    """Read the installed package version from version.json, immune to stale preserved .env values."""
    try:
        root = Path(__file__).resolve().parents[2]
        payload = json.loads((root / "version.json").read_text(encoding="utf-8"))
        value = str(payload.get("version") or "").strip()
        if value:
            return value
    except Exception:
        pass
    return get_settings().app_version
