from __future__ import annotations

import re
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.demo_store import DEMO_CUSTOMERS, DEMO_FARMS, new_id


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    return digits or None


def _with_farm_counts(customers: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    if get_settings().demo_mode:
        for farm in DEMO_FARMS:
            counts[farm["customer_id"]] = counts.get(farm["customer_id"], 0) + 1
    else:
        # New VENDRA schema deliberately has no public.farms table.
        # Preserve the legacy presentation key without issuing invalid queries.
        counts = {}
    for customer in customers:
        customer["farm_count"] = counts.get(customer["id"], 0)
    return customers


def list_customers(search: str | None = None, include_inactive: bool = True) -> list[dict]:
    if get_settings().demo_mode:
        rows = [c.copy() for c in DEMO_CUSTOMERS]
    else:
        query = get_admin_client().table("customers").select("*").order("name")
        if not include_inactive:
            query = query.eq("status", "active")
        rows = query.execute().data or []

    if not include_inactive:
        rows = [c for c in rows if c.get("status") == "active"]
    if search:
        needle = search.casefold().strip()
        rows = [
            c for c in rows
            if needle in " ".join(str(c.get(k) or "") for k in ("name", "phone", "email", "company_name", "document")).casefold()
        ]
    rows.sort(key=lambda c: (c.get("name") or "").casefold())
    return _with_farm_counts(rows)


def get_customer(customer_id: str) -> dict | None:
    if get_settings().demo_mode:
        row = next((c.copy() for c in DEMO_CUSTOMERS if c["id"] == customer_id), None)
    else:
        data = get_admin_client().table("customers").select("*").eq("id", customer_id).limit(1).execute().data or []
        row = data[0] if data else None
    if row:
        _with_farm_counts([row])
    return row


def find_customer_by_phone(phone: str) -> dict | None:
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    if get_settings().demo_mode:
        return next((c.copy() for c in DEMO_CUSTOMERS if c.get("phone_normalized") == normalized), None)
    data = get_admin_client().table("customers").select("*").eq("phone_normalized", normalized).limit(1).execute().data or []
    return data[0] if data else None


def create_customer(*, name: str, phone: str | None, email: str | None = None, document: str | None = None, company_name: str | None = None) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("Nome do cliente é obrigatório.")
    normalized = normalize_phone(phone)
    if normalized and find_customer_by_phone(phone or ""):
        raise ValueError("Já existe um cliente com este telefone.")
    payload = {
        "name": name,
        "phone": (phone or "").strip() or None,
        "phone_normalized": normalized,
        "email": (email or "").strip() or None,
        "document": (document or "").strip() or None,
        "company_name": (company_name or "").strip() or None,
        "status": "active",
    }
    if get_settings().demo_mode:
        payload.update({"id": new_id("customer"), "profile_id": None, "tags": [], "created_at": datetime.now(timezone.utc).isoformat()})
        DEMO_CUSTOMERS.append(payload)
        return payload.copy()
    return get_admin_client().table("customers").insert(payload).execute().data[0]


def update_customer(customer_id: str, *, name: str, phone: str | None, email: str | None, document: str | None, company_name: str | None, status: str) -> dict:
    if status not in {"active", "inactive"}:
        raise ValueError("Status de cliente inválido.")
    existing = get_customer(customer_id)
    if not existing:
        raise ValueError("Cliente não encontrado.")
    normalized = normalize_phone(phone)
    other = find_customer_by_phone(phone or "") if normalized else None
    if other and other["id"] != customer_id:
        raise ValueError("Já existe outro cliente com este telefone.")
    payload = {
        "name": name.strip(), "phone": (phone or "").strip() or None, "phone_normalized": normalized,
        "email": (email or "").strip() or None, "document": (document or "").strip() or None,
        "company_name": (company_name or "").strip() or None, "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if not payload["name"]:
        raise ValueError("Nome do cliente é obrigatório.")
    if get_settings().demo_mode:
        target = next(c for c in DEMO_CUSTOMERS if c["id"] == customer_id)
        target.update(payload)
        return target.copy()
    return get_admin_client().table("customers").update(payload).eq("id", customer_id).execute().data[0]


def list_farms(customer_id: str) -> list[dict]:
    if get_settings().demo_mode:
        rows = [f.copy() for f in DEMO_FARMS if f["customer_id"] == customer_id]
    else:
        rows = []  # Legacy module retired in the clean VENDRA schema.
    return sorted(rows, key=lambda f: (f.get("name") or "").casefold())


def get_farm(farm_id: str) -> dict | None:
    if get_settings().demo_mode:
        return next((f.copy() for f in DEMO_FARMS if f["id"] == farm_id), None)
    return None  # Legacy farm records are not part of the clean VENDRA schema.


def create_farm(customer_id: str, *, name: str, city: str | None, state: str | None, area_hectares: float | None) -> dict:
    if not get_customer(customer_id):
        raise ValueError("Cliente não encontrado.")
    payload = {"customer_id": customer_id, "name": name.strip(), "city": (city or "").strip() or None, "state": (state or "").strip().upper() or None, "area_hectares": area_hectares}
    if not payload["name"]:
        raise ValueError("Nome da propriedade é obrigatório.")
    if get_settings().demo_mode:
        payload.update({"id": new_id("farm"), "created_at": datetime.now(timezone.utc).isoformat()})
        DEMO_FARMS.append(payload)
        return payload.copy()
    raise ValueError("Cadastro de propriedades antigas desativado no VENDRA-STAGING.")


def update_farm(farm_id: str, *, name: str, city: str | None, state: str | None, area_hectares: float | None) -> dict:
    existing = get_farm(farm_id)
    if not existing:
        raise ValueError("Propriedade não encontrada.")
    payload = {"name": name.strip(), "city": (city or "").strip() or None, "state": (state or "").strip().upper() or None, "area_hectares": area_hectares, "updated_at": datetime.now(timezone.utc).isoformat()}
    if not payload["name"]:
        raise ValueError("Nome da propriedade é obrigatório.")
    if get_settings().demo_mode:
        target = next(f for f in DEMO_FARMS if f["id"] == farm_id)
        target.update(payload)
        return target.copy()
    raise ValueError("Edição de propriedades antigas desativada no VENDRA-STAGING.")
