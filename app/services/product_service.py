from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.demo_store import DEMO_PRODUCTS, new_id

KINDS = {"product": "Produto", "service": "Serviço"}
MONEY_QUANT = Decimal("0.01")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_money(value: str | int | float | Decimal | None) -> Decimal:
    """Converte entrada monetária sem usar float como fonte de verdade.

    Aceita formatos comuns como ``5000.00``, ``5.000,00`` e ``5000,00``.
    """
    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, int):
        amount = Decimal(value)
    else:
        raw = str(value or "").strip().replace("R$", "").replace(" ", "")
        if not raw:
            return Decimal("0.00")
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        try:
            amount = Decimal(raw)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Preço padrão inválido.") from exc
    if amount < 0:
        raise ValueError("Preço padrão não pode ser negativo.")
    return amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def money_storage(value: str | int | float | Decimal | None) -> str:
    return f"{parse_money(value):.2f}"


def money_label(value: str | int | float | Decimal | None) -> str:
    amount = parse_money(value)
    raw = f"{amount:,.2f}"
    return "R$ " + raw.replace(",", "X").replace(".", ",").replace("X", ".")


def _decorate(row: dict) -> dict:
    item = row.copy()
    item["kind_label"] = KINDS.get(item.get("kind"), item.get("kind") or "—")
    item["default_price"] = money_storage(item.get("default_price"))
    item["default_price_label"] = money_label(item.get("default_price"))
    return item


def _find_code(code: str | None) -> dict | None:
    normalized = (code or "").strip().casefold()
    if not normalized:
        return None
    if get_settings().demo_mode:
        row = next((p for p in DEMO_PRODUCTS if (p.get("code") or "").strip().casefold() == normalized), None)
        return row.copy() if row else None
    rows = get_admin_client().table("products").select("*").eq("code", (code or "").strip()).limit(1).execute().data or []
    if rows:
        return rows[0]
    # O banco definitivo deverá ter índice apropriado; este fallback mantém a
    # validação coerente em bases ainda sem normalização de SKU.
    candidates = get_admin_client().table("products").select("*").execute().data or []
    return next((p for p in candidates if (p.get("code") or "").strip().casefold() == normalized), None)


def list_products(*, search: str | None = None, kind: str | None = None, status: str = "all") -> list[dict]:
    if kind and kind not in KINDS:
        kind = None
    if status not in {"all", "active", "inactive"}:
        status = "all"

    if get_settings().demo_mode:
        rows = [p.copy() for p in DEMO_PRODUCTS]
    else:
        query = get_admin_client().table("products").select("*").order("name")
        if kind:
            query = query.eq("kind", kind)
        if status == "active":
            query = query.eq("is_active", True)
        elif status == "inactive":
            query = query.eq("is_active", False)
        rows = query.execute().data or []

    if kind:
        rows = [p for p in rows if p.get("kind") == kind]
    if status == "active":
        rows = [p for p in rows if bool(p.get("is_active", True))]
    elif status == "inactive":
        rows = [p for p in rows if not bool(p.get("is_active", True))]
    if search:
        needle = search.casefold().strip()
        rows = [
            p for p in rows
            if needle in " ".join(str(p.get(k) or "") for k in ("name", "code", "category", "description")).casefold()
        ]
    rows.sort(key=lambda p: ((p.get("name") or "").casefold(), (p.get("code") or "").casefold()))
    return [_decorate(row) for row in rows]


def get_product(product_id: str) -> dict | None:
    if get_settings().demo_mode:
        row = next((p.copy() for p in DEMO_PRODUCTS if p.get("id") == product_id), None)
    else:
        data = get_admin_client().table("products").select("*").eq("id", product_id).limit(1).execute().data or []
        row = data[0] if data else None
    return _decorate(row) if row else None


def _validate(*, name: str, kind: str, code: str | None, default_price) -> dict:
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("Nome do produto ou serviço é obrigatório.")
    if kind not in KINDS:
        raise ValueError("Tipo inválido. Escolha Produto ou Serviço.")
    clean_code = (code or "").strip() or None
    return {
        "name": clean_name,
        "kind": kind,
        "code": clean_code,
        "default_price": money_storage(default_price),
    }


def create_product(*, name: str, kind: str, code: str | None, description: str | None, category: str | None, unit: str | None, default_price) -> dict:
    base = _validate(name=name, kind=kind, code=code, default_price=default_price)
    if base["code"] and _find_code(base["code"]):
        raise ValueError("Já existe um produto ou serviço com este código/SKU.")
    now = _now()
    payload = {
        **base,
        "description": (description or "").strip() or None,
        "category": (category or "").strip() or None,
        "unit": (unit or "").strip() or None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    if get_settings().demo_mode:
        payload["id"] = new_id("product")
        DEMO_PRODUCTS.append(payload)
        return _decorate(payload)
    row = get_admin_client().table("products").insert(payload).execute().data[0]
    return _decorate(row)


def update_product(product_id: str, *, name: str, kind: str, code: str | None, description: str | None, category: str | None, unit: str | None, default_price, is_active: bool) -> dict:
    existing = get_product(product_id)
    if not existing:
        raise ValueError("Produto ou serviço não encontrado.")
    base = _validate(name=name, kind=kind, code=code, default_price=default_price)
    duplicate = _find_code(base["code"]) if base["code"] else None
    if duplicate and duplicate.get("id") != product_id:
        raise ValueError("Já existe outro produto ou serviço com este código/SKU.")
    payload = {
        **base,
        "description": (description or "").strip() or None,
        "category": (category or "").strip() or None,
        "unit": (unit or "").strip() or None,
        "is_active": bool(is_active),
        "updated_at": _now(),
    }
    if get_settings().demo_mode:
        index = next((i for i, p in enumerate(DEMO_PRODUCTS) if p.get("id") == product_id), None)
        if index is None:
            raise ValueError("Produto ou serviço não encontrado.")
        DEMO_PRODUCTS[index].update(payload)
        return _decorate(DEMO_PRODUCTS[index])
    row = get_admin_client().table("products").update(payload).eq("id", product_id).execute().data[0]
    return _decorate(row)
