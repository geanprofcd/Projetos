from __future__ import annotations

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.demo_store import DEMO_CATEGORIES, DEMO_CROPS, DEMO_INTERNAL_USERS


def list_crops() -> list[dict]:
    if get_settings().demo_mode:
        return [row.copy() for row in DEMO_CROPS]
    return []  # Agronomic crops are not part of the clean VENDRA schema.


def list_categories() -> list[dict]:
    if get_settings().demo_mode:
        return [row.copy() for row in DEMO_CATEGORIES]
    return []  # Agronomic categories are not part of the clean VENDRA schema.


def list_internal_users(active_only: bool = True) -> list[dict]:
    if get_settings().demo_mode:
        rows = [row.copy() for row in DEMO_INTERNAL_USERS]
    else:
        rows = get_admin_client().table("profiles").select("id,full_name,email,role,status").in_("role", ["responsavel", "administrador"]).order("full_name").execute().data or []
    if active_only:
        rows = [row for row in rows if row.get("status") == "active"]
    return rows
