"""Smoke test local de Funis e Etapas do VENDRA 0.0.3."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import csrf_token_for_session
from app.services.demo_store import DEMO_AUDIT_LOG, DEMO_FUNNEL_STAGES, DEMO_SALES_FUNNELS


def main() -> None:
    client = TestClient(app)
    client.cookies.set("vendra_session", "demo-admin")
    csrf = csrf_token_for_session("demo-admin")

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["app"] == "VENDRA"

    listing = client.get("/configuracoes/funis")
    assert listing.status_code == 200
    assert "Funis de vendas" in listing.text
    assert "Funil Comercial" in listing.text

    before_funnels = len(DEMO_SALES_FUNNELS)
    create_response = client.post(
        "/configuracoes/funis/novo",
        data={"name": "Renovação Smoke", "description": "Teste", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert create_response.status_code == 303
    assert len(DEMO_SALES_FUNNELS) == before_funnels + 1
    funnel = next(row for row in DEMO_SALES_FUNNELS if row.get("name") == "Renovação Smoke")

    duplicate = client.post(
        "/configuracoes/funis/novo",
        data={"name": "renovação smoke", "description": "Duplicado", "csrf_token": csrf},
    )
    assert duplicate.status_code == 422

    before_stages = len(DEMO_FUNNEL_STAGES)
    stage_response = client.post(
        f"/configuracoes/funis/{funnel['id']}/etapas/nova",
        data={"name": "Contato", "color": "#123456", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert stage_response.status_code == 303
    assert len(DEMO_FUNNEL_STAGES) == before_stages + 1
    stage1 = next(row for row in DEMO_FUNNEL_STAGES if row.get("funnel_id") == funnel["id"] and row.get("name") == "Contato")
    assert stage1["position"] == 1

    stage_response2 = client.post(
        f"/configuracoes/funis/{funnel['id']}/etapas/nova",
        data={"name": "Renegociação", "color": "#654321", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert stage_response2.status_code == 303
    stage2 = next(row for row in DEMO_FUNNEL_STAGES if row.get("funnel_id") == funnel["id"] and row.get("name") == "Renegociação")
    assert stage2["position"] == 2

    move = client.post(
        f"/configuracoes/funis/{funnel['id']}/etapas/{stage2['id']}/mover",
        data={"direction": "up", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert move.status_code == 303
    assert stage2["position"] == 1 and stage1["position"] == 2

    edit = client.post(
        f"/configuracoes/funis/{funnel['id']}/etapas/{stage1['id']}/editar",
        data={"name": "Contato inicial", "color": "#abcdef", "is_active": "false", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert edit.status_code == 303
    assert stage1["name"] == "Contato inicial"
    assert stage1["color"] == "#abcdef"
    assert stage1["is_active"] is False

    invalid_csrf = client.post(
        "/configuracoes/funis/novo",
        data={"name": "Não deve criar", "csrf_token": "invalid"},
        follow_redirects=False,
    )
    assert invalid_csrf.status_code == 403

    assert any(row.get("action") == "sales_funnel.created" and row.get("entity_id") == funnel["id"] for row in DEMO_AUDIT_LOG)
    assert any(row.get("action") == "funnel_stage.created" and row.get("entity_id") == stage1["id"] for row in DEMO_AUDIT_LOG)
    assert any(row.get("action") == "funnel_stage.reordered" and row.get("entity_id") == stage2["id"] for row in DEMO_AUDIT_LOG)

    print("VENDRA_FUNNELS_SMOKE_OK")


if __name__ == "__main__":
    main()
