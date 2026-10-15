from __future__ import annotations

from datetime import datetime, timezone
import re

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.demo_store import DEMO_FUNNEL_STAGES, DEMO_SALES_FUNNELS, new_id

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
DEFAULT_STAGE_COLOR = "#3157d5"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_name(value: str | None, *, label: str) -> str:
    clean = (value or "").strip()
    if not clean:
        raise ValueError(f"{label} é obrigatório.")
    if len(clean) > 120:
        raise ValueError(f"{label} deve ter no máximo 120 caracteres.")
    return clean


def _clean_color(value: str | None) -> str:
    color = (value or DEFAULT_STAGE_COLOR).strip()
    if not HEX_COLOR.match(color):
        raise ValueError("Cor inválida. Use o formato hexadecimal, como #3157d5.")
    return color.lower()


def _funnel_name_conflict(name: str, *, ignore_id: str | None = None) -> bool:
    normalized = name.casefold()
    if get_settings().demo_mode:
        return any(
            row.get("id") != ignore_id and (row.get("name") or "").strip().casefold() == normalized
            for row in DEMO_SALES_FUNNELS
        )
    rows = get_admin_client().table("sales_funnels").select("id,name").execute().data or []
    return any(str(row.get("id")) != str(ignore_id) and (row.get("name") or "").strip().casefold() == normalized for row in rows)


def _stage_name_conflict(funnel_id: str, name: str, *, ignore_id: str | None = None) -> bool:
    normalized = name.casefold()
    if get_settings().demo_mode:
        return any(
            row.get("funnel_id") == funnel_id
            and row.get("id") != ignore_id
            and (row.get("name") or "").strip().casefold() == normalized
            for row in DEMO_FUNNEL_STAGES
        )
    rows = get_admin_client().table("funnel_stages").select("id,name").eq("funnel_id", funnel_id).execute().data or []
    return any(str(row.get("id")) != str(ignore_id) and (row.get("name") or "").strip().casefold() == normalized for row in rows)


def _stage_rows(funnel_id: str, *, include_inactive: bool = True) -> list[dict]:
    if get_settings().demo_mode:
        rows = [row.copy() for row in DEMO_FUNNEL_STAGES if row.get("funnel_id") == funnel_id]
    else:
        query = get_admin_client().table("funnel_stages").select("*").eq("funnel_id", funnel_id).order("position")
        if not include_inactive:
            query = query.eq("is_active", True)
        rows = query.execute().data or []
    if not include_inactive:
        rows = [row for row in rows if bool(row.get("is_active", True))]
    rows.sort(key=lambda row: (int(row.get("position") or 0), (row.get("name") or "").casefold()))
    return rows


def list_funnels(*, include_inactive: bool = True) -> list[dict]:
    if get_settings().demo_mode:
        rows = [row.copy() for row in DEMO_SALES_FUNNELS]
    else:
        query = get_admin_client().table("sales_funnels").select("*").order("name")
        if not include_inactive:
            query = query.eq("is_active", True)
        rows = query.execute().data or []
    if not include_inactive:
        rows = [row for row in rows if bool(row.get("is_active", True))]
    result = []
    for source in rows:
        row = source.copy()
        stages = _stage_rows(str(row["id"]), include_inactive=True)
        row["stages"] = stages
        row["stage_count"] = len(stages)
        row["active_stage_count"] = sum(1 for stage in stages if bool(stage.get("is_active", True)))
        result.append(row)
    result.sort(key=lambda row: ((row.get("name") or "").casefold(), str(row.get("id"))))
    return result


def get_funnel(funnel_id: str, *, include_inactive_stages: bool = True) -> dict | None:
    if get_settings().demo_mode:
        source = next((row for row in DEMO_SALES_FUNNELS if row.get("id") == funnel_id), None)
        row = source.copy() if source else None
    else:
        data = get_admin_client().table("sales_funnels").select("*").eq("id", funnel_id).limit(1).execute().data or []
        row = data[0] if data else None
    if not row:
        return None
    row["stages"] = _stage_rows(funnel_id, include_inactive=include_inactive_stages)
    row["stage_count"] = len(row["stages"])
    row["active_stage_count"] = sum(1 for stage in row["stages"] if bool(stage.get("is_active", True)))
    return row


def get_stage(stage_id: str) -> dict | None:
    if get_settings().demo_mode:
        source = next((row for row in DEMO_FUNNEL_STAGES if row.get("id") == stage_id), None)
        return source.copy() if source else None
    data = get_admin_client().table("funnel_stages").select("*").eq("id", stage_id).limit(1).execute().data or []
    return data[0] if data else None


def create_funnel(*, name: str, description: str | None = None) -> dict:
    clean_name = _clean_name(name, label="Nome do funil")
    if _funnel_name_conflict(clean_name):
        raise ValueError("Já existe um funil com este nome.")
    now = _now()
    payload = {
        "name": clean_name,
        "description": (description or "").strip() or None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    if get_settings().demo_mode:
        payload["id"] = new_id("funnel")
        DEMO_SALES_FUNNELS.append(payload)
        return payload.copy()
    return get_admin_client().table("sales_funnels").insert(payload).execute().data[0]


def update_funnel(funnel_id: str, *, name: str, description: str | None = None, is_active: bool = True) -> dict:
    existing = get_funnel(funnel_id)
    if not existing:
        raise ValueError("Funil não encontrado.")
    clean_name = _clean_name(name, label="Nome do funil")
    if _funnel_name_conflict(clean_name, ignore_id=funnel_id):
        raise ValueError("Já existe outro funil com este nome.")
    payload = {
        "name": clean_name,
        "description": (description or "").strip() or None,
        "is_active": bool(is_active),
        "updated_at": _now(),
    }
    if get_settings().demo_mode:
        index = next(i for i, row in enumerate(DEMO_SALES_FUNNELS) if row.get("id") == funnel_id)
        DEMO_SALES_FUNNELS[index].update(payload)
        return DEMO_SALES_FUNNELS[index].copy()
    return get_admin_client().table("sales_funnels").update(payload).eq("id", funnel_id).execute().data[0]


def create_stage(*, funnel_id: str, name: str, color: str | None = None) -> dict:
    if not get_funnel(funnel_id):
        raise ValueError("Funil não encontrado.")
    clean_name = _clean_name(name, label="Nome da etapa")
    if _stage_name_conflict(funnel_id, clean_name):
        raise ValueError("Já existe uma etapa com este nome neste funil.")
    stages = _stage_rows(funnel_id, include_inactive=True)
    position = max((int(row.get("position") or 0) for row in stages), default=0) + 1
    now = _now()
    payload = {
        "funnel_id": funnel_id,
        "name": clean_name,
        "position": position,
        "color": _clean_color(color),
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    if get_settings().demo_mode:
        payload["id"] = new_id("stage")
        DEMO_FUNNEL_STAGES.append(payload)
        return payload.copy()
    return get_admin_client().table("funnel_stages").insert(payload).execute().data[0]


def update_stage(stage_id: str, *, name: str, color: str | None = None, is_active: bool = True) -> dict:
    existing = get_stage(stage_id)
    if not existing:
        raise ValueError("Etapa não encontrada.")
    clean_name = _clean_name(name, label="Nome da etapa")
    funnel_id = str(existing["funnel_id"])
    if _stage_name_conflict(funnel_id, clean_name, ignore_id=stage_id):
        raise ValueError("Já existe outra etapa com este nome neste funil.")
    payload = {
        "name": clean_name,
        "color": _clean_color(color),
        "is_active": bool(is_active),
        "updated_at": _now(),
    }
    if get_settings().demo_mode:
        index = next(i for i, row in enumerate(DEMO_FUNNEL_STAGES) if row.get("id") == stage_id)
        DEMO_FUNNEL_STAGES[index].update(payload)
        return DEMO_FUNNEL_STAGES[index].copy()
    return get_admin_client().table("funnel_stages").update(payload).eq("id", stage_id).execute().data[0]


def move_stage(stage_id: str, *, direction: str) -> dict:
    if direction not in {"up", "down"}:
        raise ValueError("Direção inválida para reordenar a etapa.")
    stage = get_stage(stage_id)
    if not stage:
        raise ValueError("Etapa não encontrada.")
    funnel_id = str(stage["funnel_id"])
    stages = _stage_rows(funnel_id, include_inactive=True)
    current_index = next((i for i, row in enumerate(stages) if row.get("id") == stage_id), None)
    if current_index is None:
        raise ValueError("Etapa não encontrada no funil.")
    target_index = current_index - 1 if direction == "up" else current_index + 1
    if target_index < 0 or target_index >= len(stages):
        return stage
    other = stages[target_index]
    current_position = int(stage.get("position") or current_index + 1)
    target_position = int(other.get("position") or target_index + 1)
    now = _now()
    if get_settings().demo_mode:
        current_ref = next(row for row in DEMO_FUNNEL_STAGES if row.get("id") == stage_id)
        other_ref = next(row for row in DEMO_FUNNEL_STAGES if row.get("id") == other.get("id"))
        current_ref["position"], other_ref["position"] = target_position, current_position
        current_ref["updated_at"] = other_ref["updated_at"] = now
        return current_ref.copy()
    admin = get_admin_client()
    # Usa uma posição temporária positiva para não colidir com o índice único
    # (funnel_id, position) durante a troca. Em banco definitivo, esta operação
    # deve preferencialmente ser encapsulada em transação/RPC.
    temporary_position = max((int(row.get("position") or 0) for row in stages), default=0) + 1000000
    admin.table("funnel_stages").update({"position": temporary_position, "updated_at": now}).eq("id", stage_id).execute()
    admin.table("funnel_stages").update({"position": current_position, "updated_at": now}).eq("id", other["id"]).execute()
    admin.table("funnel_stages").update({"position": target_position, "updated_at": now}).eq("id", stage_id).execute()
    return get_stage(stage_id) or stage
