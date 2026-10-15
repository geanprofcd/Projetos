from __future__ import annotations

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.demo_store import DEMO_AUDIT_LOG, DEMO_INTERNAL_USERS
from datetime import datetime, timezone


def list_audit_log(limit: int = 100) -> list[dict]:
    limit = min(max(int(limit), 1), 250)
    if get_settings().demo_mode:
        names = {row["id"]: row["full_name"] for row in DEMO_INTERNAL_USERS}
        rows = []
        for index, source in enumerate(reversed(DEMO_AUDIT_LOG[-limit:]), start=1):
            row = source.copy()
            row.setdefault("id", f"demo-audit-{index}")
            row["actor_name"] = names.get(row.get("actor_id"), "Sistema/integração")
            rows.append(row)
        return rows

    admin = get_admin_client()
    rows = admin.table("audit_log").select("*").order("created_at", desc=True).limit(limit).execute().data or []
    actor_ids = {row.get("actor_id") for row in rows if row.get("actor_id")}
    names: dict[str, str] = {}
    if actor_ids:
        profiles = admin.table("profiles").select("id,full_name").in_("id", list(actor_ids)).execute().data or []
        names = {str(row["id"]): row.get("full_name") or "Usuário" for row in profiles}
    for row in rows:
        row["actor_name"] = names.get(str(row.get("actor_id"))) if row.get("actor_id") else "Sistema/integração"
    return rows


def record_audit(*, actor_id: str | None, entity_type: str, entity_id: str, action: str, payload: dict | None = None) -> None:
    record = {
        "actor_id": actor_id,
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "action": action,
        "payload": payload or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if get_settings().demo_mode:
        DEMO_AUDIT_LOG.append(record)
        return
    get_admin_client().table("audit_log").insert(record).execute()
