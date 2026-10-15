from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import csrf_token_for_session
from app.services.demo_store import DEMO_AUDIT_LOG, DEMO_OPPORTUNITIES
from app.services.opportunity_service import OpportunityConflictError, archive_opportunity, move_opportunity_stage

USER = "00000000-0000-0000-0000-000000000001"


def main() -> None:
    client = TestClient(app)
    client.cookies.set("vendra_session", "demo-admin")
    csrf = csrf_token_for_session("demo-admin")

    health = client.get("/health")
    assert health.status_code == 200 and health.json()["app"] == "VENDRA"

    page = client.get("/atendimentos?view=funil&funil=funnel-demo-commercial")
    assert page.status_code == 200
    assert "Funil Comercial" in page.text
    assert "Implantação e consultoria comercial" in page.text
    assert "R$" in page.text
    assert "kanban-card-delete-zone" in page.text
    assert "Excluir card" in page.text
    assert "kanban-v0.0.16.js" in page.text
    assert "kanbanLiveBadge" in page.text
    assert "data-kanban-signature" in page.text

    initial_feed = client.get("/atendimentos/funil/feed.json?funil=funnel-demo-commercial")
    assert initial_feed.status_code == 200, initial_feed.text
    initial_payload = initial_feed.json()
    assert initial_payload["funnel_id"] == "funnel-demo-commercial"
    assert initial_payload["signature"]
    assert "opportunity-demo-1" in initial_payload["html"]
    # O card abre a conversa por padrão e mantém a oportunidade como atalho secundário.
    assert 'href="/atendimentos/1547"' in initial_payload["html"]
    assert 'href="/oportunidades/opportunity-demo-1"' in initial_payload["html"]
    conversation = client.get("/atendimentos/1547")
    assert conversation.status_code == 200, conversation.text

    target = next(row for row in DEMO_OPPORTUNITIES if row.get("id") == "opportunity-demo-1")
    old_stage = target["stage_id"]
    old_lock = int(target.get("lock_version") or 0)
    destination = "stage-demo-4" if old_stage != "stage-demo-4" else "stage-demo-3"

    response = client.post(
        "/atendimentos/funil/oportunidades/opportunity-demo-1/mover",
        data={
            "stage_id": destination,
            "lock_version": str(old_lock),
            "csrf_token": csrf,
            "response_mode": "json",
            "funnel_id": "funnel-demo-commercial",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ok"] is True
    assert target["stage_id"] == destination
    assert int(target["lock_version"]) == old_lock + 1
    assert any(a.get("action") == "opportunity_stage_changed" and a.get("entity_id") == "opportunity-demo-1" for a in DEMO_AUDIT_LOG)

    moved_feed = client.get("/atendimentos/funil/feed.json?funil=funnel-demo-commercial")
    assert moved_feed.status_code == 200, moved_feed.text
    moved_payload = moved_feed.json()
    assert moved_payload["signature"] != initial_payload["signature"]
    assert f'data-opportunity-id="opportunity-demo-1" data-stage-id="{destination}"' in moved_payload["html"]

    conflict = client.post(
        "/atendimentos/funil/oportunidades/opportunity-demo-1/mover",
        data={
            "stage_id": old_stage,
            "lock_version": str(old_lock),
            "csrf_token": csrf,
            "response_mode": "json",
            "funnel_id": "funnel-demo-commercial",
        },
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "conflict"

    # restaura o registro demo para não deixar o smoke alterar o estado em memória
    move_opportunity_stage(
        "opportunity-demo-1",
        to_stage_id=old_stage,
        expected_lock_version=int(target["lock_version"]),
        actor_id=USER,
        source="smoke-cleanup",
    )

    # Exclusão visual do card = arquivamento seguro, sem apagar o registro.
    lock_before_archive = int(target.get("lock_version") or 0)
    archived = archive_opportunity(
        "opportunity-demo-1",
        expected_lock_version=lock_before_archive,
        actor_id=USER,
    )
    assert archived.get("archived_at")
    assert target.get("archived_at")
    hidden_page = client.get("/atendimentos?view=funil&funil=funnel-demo-commercial")
    assert "Implantação e consultoria comercial" not in hidden_page.text

    # Limpa o estado demo do smoke.
    target["archived_at"] = None
    target["archived_by"] = None
    target["lock_version"] = lock_before_archive
    print("kanban smoke: OK")


if __name__ == "__main__":
    main()
