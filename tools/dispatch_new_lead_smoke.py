"""VENDRA 0.0.19 — validate automatic CRM entry for initial dispatches.

Run from the isolated VENDRA source using: python tools/dispatch_new_lead_smoke.py
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ["VENDRA_LOCAL_CONFIG"] = str(ROOT / "runtime" / "smoke_dispatch_lead_0019_settings.json")

from app.services.admin_settings_service import save_dispatch_settings
from app.services.demo_store import DEMO_INTERNAL_USERS, DEMO_OPPORTUNITIES
from app.services.dispatch_service import create_dispatch, update_dispatch_status
from app.services.opportunity_service import get_ticket_opportunity, move_opportunity_stage
from app.services.funnel_service import create_funnel, create_stage


def main() -> None:
    save_dispatch_settings(enabled=True, webhook_url="https://make.invalid/webhook", template_key="continuar_atendimento_vendra")
    sent = []

    def fake_make(url, payload):
        sent.append(payload)
        return 200, '{"ok": true}'

    actor = DEMO_INTERNAL_USERS[0]["id"]
    with patch("app.services.dispatch_service._post_json", side_effect=fake_make):
        first = create_dispatch(name="Lead Smoke 0019", phone="5587999654321", requested_by=actor)
        assert first["status"] == "submitted", first
        assert sent and sent[-1]["event"] == "whatsapp.dispatch.requested"
        assert sent[-1]["template_key"] == "continuar_atendimento_vendra"
        opportunity = get_ticket_opportunity(first["ticket_id"], open_only=True)
        assert opportunity and opportunity["id"] == first["opportunity_id"], (first, opportunity)
        assert opportunity["funnel_name"].casefold() == "funil comercial", opportunity
        assert opportunity["stage_name"].casefold() == "novo lead", opportunity
        assert opportunity["assigned_user_id"] == actor, opportunity
        assert opportunity["status"] == "open", opportunity

        another = create_dispatch(name="Lead Smoke 0019", phone="5587999654321", requested_by=actor)
        assert another["ticket_id"] == first["ticket_id"], (first, another)
        assert another["opportunity_id"] == first["opportunity_id"], (first, another)
        assert len([x for x in DEMO_OPPORTUNITIES if str(x.get("ticket_id")) == first["ticket_id"] and x.get("status") == "open"]) == 1

        moved = move_opportunity_stage(opportunity["id"], to_stage_id="stage-demo-2", expected_lock_version=int(opportunity["lock_version"]), actor_id=actor, source="smoke")
        assert moved["stage_name"] == "Qualificação", moved
        again = create_dispatch(name="Lead Smoke 0019", phone="5587999654321", requested_by=actor)
        assert again["opportunity_id"] == first["opportunity_id"]
        progressed = get_ticket_opportunity(first["ticket_id"], open_only=True)
        assert progressed["stage_name"] == "Qualificação", progressed

        acknowledged = update_dispatch_status(dispatch_id=first["id"], status="sent", provider_message_id="wamid.smoke0019")
        assert acknowledged["provider_message_id"] == "wamid.smoke0019"

        # If 'Novo Lead' is an actual funnel, use its first active stage instead.
        target = create_funnel(name="Novo Lead")
        stage = create_stage(funnel_id=target["id"], name="Entrada")
        in_funnel = create_dispatch(name="Lead Funnel Smoke 0019", phone="5587999654322", requested_by=actor)
        funnel_opportunity = get_ticket_opportunity(in_funnel["ticket_id"], open_only=True)
        assert funnel_opportunity["funnel_id"] == target["id"], funnel_opportunity
        assert funnel_opportunity["stage_id"] == stage["id"], funnel_opportunity

    assert len(sent) == 4, len(sent)
    print("VENDRA_DISPATCH_NEW_LEAD_SMOKE_OK: inicial / idempotencia / nao regredir / wamid / funil personalizado")


if __name__ == "__main__":
    main()
