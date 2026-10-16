from functools import lru_cache
from typing import Any

from app.core.config import get_settings


def _create_client(url: str, key: str) -> Any:
    # Import tardio: o modo demo consegue subir mesmo antes de instalar/configurar Supabase.
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError(
            "Pacote supabase não instalado. Execute: pip install -r requirements.txt"
        ) from exc
    from supabase.lib.client_options import SyncClientOptions
    from app.db.http_client import create_database_http_client
    return create_client(url, key, options=SyncClientOptions(
        httpx_client=create_database_http_client(),
        auto_refresh_token=False, persist_session=False,
    ))


@lru_cache
def get_auth_client() -> Any:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_ANON_KEY precisam estar configurados.")
    return _create_client(settings.supabase_url, settings.supabase_anon_key)


@lru_cache
def get_admin_client() -> Any:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY precisam estar configurados.")
    # Esta chave nunca deve ir para HTML/JS/browser.
    return _create_client(settings.supabase_url, settings.supabase_service_role_key)
