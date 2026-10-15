"""Smoke test local do catálogo Produtos e Serviços do VENDRA.

Executar a partir da raiz do projeto:
    python tools/products_smoke.py
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.routers.products import _admin
from app.services.demo_store import DEMO_AUDIT_LOG, DEMO_PRODUCTS


def main() -> None:
    client = TestClient(app)
    client.cookies.set("vendra_session", "demo-admin")

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["app"] == "VENDRA"

    listing = client.get("/produtos")
    assert listing.status_code == 200
    assert "Produtos e Serviços" in listing.text

    before = len(DEMO_PRODUCTS)
    created_response = client.post(
        "/produtos/novo",
        data={
            "name": "Treinamento Smoke",
            "kind": "service",
            "code": "SMOKE-PRODUCT-001",
            "description": "Registro temporário do smoke test",
            "category": "Teste",
            "unit": "turma",
            "default_price": "1.250,50",
        },
        follow_redirects=False,
    )
    assert created_response.status_code == 303
    assert len(DEMO_PRODUCTS) == before + 1
    created = next(p for p in DEMO_PRODUCTS if p.get("code") == "SMOKE-PRODUCT-001")
    assert created["default_price"] == "1250.50"

    duplicate = client.post(
        "/produtos/novo",
        data={"name": "Duplicado", "kind": "service", "code": "smoke-product-001", "default_price": "10"},
    )
    assert duplicate.status_code == 422

    updated_response = client.post(
        f"/produtos/{created['id']}/editar",
        data={
            "name": "Treinamento Smoke Atualizado",
            "kind": "service",
            "code": "SMOKE-PRODUCT-001",
            "description": "Atualizado",
            "category": "Teste",
            "unit": "turma",
            "default_price": "1500.00",
            "is_active": "false",
        },
        follow_redirects=False,
    )
    assert updated_response.status_code == 303
    updated = next(p for p in DEMO_PRODUCTS if p.get("id") == created["id"])
    assert updated["default_price"] == "1500.00"
    assert updated["is_active"] is False
    assert any(a.get("action") == "product.created" and a.get("entity_id") == created["id"] for a in DEMO_AUDIT_LOG)
    assert any(a.get("action") == "product.updated" and a.get("entity_id") == created["id"] for a in DEMO_AUDIT_LOG)

    try:
        _admin({"role": "responsavel"})
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Responsável não deve editar o catálogo na v0.1")

    # O smoke não deve deixar registro persistente no projeto. O processo de
    # empacotamento remove .vendra-data após a execução.
    print("VENDRA_PRODUCTS_SMOKE_OK")


if __name__ == "__main__":
    main()
