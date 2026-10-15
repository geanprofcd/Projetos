from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import app
from app.services.commercial_metrics_service import commercial_indicators
from app.services.demo_store import DEMO_OPPORTUNITIES


def main() -> None:
    client = TestClient(app)
    client.cookies.set("vendra_session", "demo-admin")
    health = client.get("/health")
    assert health.status_code == 200 and health.json()["app"] == "VENDRA"

    snapshot = deepcopy(DEMO_OPPORTUNITIES)
    try:
        DEMO_OPPORTUNITIES.extend(
            [
                {
                    "id": "indicator-won",
                    "customer_id": "c1",
                    "ticket_id": None,
                    "title": "Venda ganha smoke",
                    "funnel_id": "funnel-demo-commercial",
                    "stage_id": "stage-demo-4",
                    "assigned_user_id": "00000000-0000-0000-0000-000000000001",
                    "status": "won",
                    "currency_code": "BRL",
                    "calculated_value": "2500.00",
                    "final_value": "2500.00",
                    "expected_close_date": None,
                    "won_at": "2026-10-04T12:00:00+00:00",
                    "lost_at": None,
                    "lost_reason_id": None,
                    "lost_notes": None,
                    "kanban_position": 1000,
                    "lock_version": 1,
                    "created_at": "2026-10-01T12:00:00+00:00",
                    "updated_at": "2026-10-04T12:00:00+00:00",
                },
                {
                    "id": "indicator-lost",
                    "customer_id": "c2",
                    "ticket_id": None,
                    "title": "Venda perdida smoke",
                    "funnel_id": "funnel-demo-commercial",
                    "stage_id": "stage-demo-4",
                    "assigned_user_id": "00000000-0000-0000-0000-000000000001",
                    "status": "lost",
                    "currency_code": "BRL",
                    "calculated_value": "1000.00",
                    "final_value": None,
                    "expected_close_date": None,
                    "won_at": None,
                    "lost_at": "2026-10-04T13:00:00+00:00",
                    "lost_reason_id": "lost-price",
                    "lost_notes": None,
                    "kanban_position": 2000,
                    "lock_version": 1,
                    "created_at": "2026-10-02T12:00:00+00:00",
                    "updated_at": "2026-10-04T13:00:00+00:00",
                },
            ]
        )
        data = commercial_indicators(start_date="2026-10-01", end_date="2026-10-10")
        assert data["won_count"] == 1
        assert data["lost_count"] == 1
        assert data["won_value"] == "2500.00"
        assert data["conversion_label"] == "50,0%"
        assert data["avg_ticket"] == "2500.00"
        assert data["pipeline_count"] >= 1

        page = client.get("/indicadores?inicio=2026-10-01&fim=2026-10-10")
        assert page.status_code == 200
        assert "Pipeline atual" in page.text
        assert "50,0%" in page.text
        assert "Ticket médio ganho" in page.text

        dashboard = client.get("/")
        assert dashboard.status_code == 200
        assert "Visão comercial" in dashboard.text
        assert "Ver indicadores" in dashboard.text
    finally:
        DEMO_OPPORTUNITIES[:] = snapshot

    print("indicators smoke: OK")


if __name__ == "__main__":
    main()
