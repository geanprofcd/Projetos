from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.demo_store import DEMO_AUDIT_LOG, DEMO_OPPORTUNITIES, DEMO_OPPORTUNITY_ITEMS, DEMO_OPPORTUNITY_STAGE_HISTORY
from app.services.opportunity_service import (
    add_opportunity_item,
    create_opportunity,
    get_opportunity,
    mark_lost,
    mark_won,
    remove_opportunity_item,
    reopen_opportunity,
    update_opportunity,
    update_opportunity_item,
)

USER = "00000000-0000-0000-0000-000000000001"


def run():
    before_opps = len(DEMO_OPPORTUNITIES)
    before_items = len(DEMO_OPPORTUNITY_ITEMS)
    before_history = len(DEMO_OPPORTUNITY_STAGE_HISTORY)
    opp = create_opportunity(
        title="Smoke oportunidade",
        customer_id="c1",
        ticket_id="1548",
        funnel_id="funnel-demo-commercial",
        stage_id="stage-demo-1",
        assigned_user_id=USER,
        expected_close_date="2026-10-31",
        actor_id=USER,
        source="system",
    )
    assert opp["status"] == "open" and opp["calculated_value"] == "0.00"
    try:
        create_opportunity(title="Duplicada", customer_id="c1", ticket_id="1548", funnel_id="funnel-demo-commercial", stage_id="stage-demo-1", assigned_user_id=USER, expected_close_date=None, actor_id=USER)
        raise AssertionError("deveria bloquear segunda oportunidade open no ticket")
    except ValueError:
        pass
    item, opp = add_opportunity_item(opp["id"], product_id="product-demo-1", quantity="2", unit_price="1500,50")
    assert item["subtotal"] == "3001.00" and opp["calculated_value"] == "3001.00"
    item, opp = update_opportunity_item(opp["id"], item["id"], quantity="3", unit_price="1000")
    assert opp["calculated_value"] == "3000.00"
    opp = update_opportunity(opp["id"], title="Smoke oportunidade", funnel_id="funnel-demo-commercial", stage_id="stage-demo-2", assigned_user_id=USER, expected_close_date="2026-11-01", actor_id=USER, source="detail")
    assert opp["stage_id"] == "stage-demo-2"
    won = mark_won(opp["id"])
    assert won["status"] == "won" and won["final_value"] == "3000.00"
    reopened = reopen_opportunity(opp["id"])
    assert reopened["status"] == "open" and reopened["final_value"] is None
    lost = mark_lost(opp["id"], lost_reason_id="lost-price", lost_notes="Teste")
    assert lost["status"] == "lost" and lost["lost_reason_id"] == "lost-price"
    reopened = reopen_opportunity(opp["id"])
    only_item = reopened["items"][0]
    opp = remove_opportunity_item(opp["id"], only_item["id"])
    assert opp["calculated_value"] == "0.00"
    # cleanup para não deixar sujeira ao rodar manualmente
    DEMO_OPPORTUNITY_ITEMS[:] = [r for r in DEMO_OPPORTUNITY_ITEMS if r.get("opportunity_id") != opp["id"]]
    DEMO_OPPORTUNITY_STAGE_HISTORY[:] = [r for r in DEMO_OPPORTUNITY_STAGE_HISTORY if r.get("opportunity_id") != opp["id"]]
    DEMO_OPPORTUNITIES[:] = [r for r in DEMO_OPPORTUNITIES if r.get("id") != opp["id"]]
    assert len(DEMO_OPPORTUNITIES) == before_opps
    assert len(DEMO_OPPORTUNITY_ITEMS) == before_items
    assert len(DEMO_OPPORTUNITY_STAGE_HISTORY) == before_history
    print("opportunities smoke: OK")


if __name__ == "__main__":
    run()
