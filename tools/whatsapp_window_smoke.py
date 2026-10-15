"""Smoke local VENDRA 0.0.14: janela de atendimento WhatsApp e bloqueio de texto livre."""
from __future__ import annotations

import os
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["VENDRA_LOCAL_CONFIG"] = str(ROOT / "runtime" / "smoke_whatsapp_window_0014_credentials.json")

from app.services.demo_store import DEMO_MESSAGES, DEMO_TICKETS
from app.services.whatsapp_window_service import (
    WhatsAppTemplateRequiredError,
    get_whatsapp_service_window,
    require_freeform_window,
)


def main() -> None:
    ticket_id = "1548"
    original_messages = deepcopy(DEMO_MESSAGES.get(ticket_id, []))
    try:
        now = datetime.now(timezone.utc)
        DEMO_MESSAGES.setdefault(ticket_id, []).append(
            {
                "id": "smoke-window-fresh",
                "sender_id": "c1",
                "sender_name": "Cliente Window Smoke",
                "body": "Mensagem recente",
                "created_at": (now - timedelta(minutes=10)).isoformat(),
                "is_internal": False,
                "channel": "whatsapp",
                "direction": "inbound",
            }
        )
        opened = get_whatsapp_service_window(ticket_id, now=now)
        assert opened["applicable"] is True
        assert opened["open"] is True
        assert opened["template_required"] is False
        assert opened["send_mode"] == "freeform"
        assert 23 * 3600 < opened["remaining_seconds"] <= 24 * 3600
        require_freeform_window(ticket_id)

        DEMO_MESSAGES[ticket_id] = [
            {
                **row,
                "created_at": (now - timedelta(hours=25)).isoformat(),
            }
            if row.get("direction") == "inbound" and row.get("channel") == "whatsapp"
            else row
            for row in DEMO_MESSAGES[ticket_id]
        ]
        closed = get_whatsapp_service_window(ticket_id, now=now)
        assert closed["open"] is False
        assert closed["template_required"] is True
        assert closed["send_mode"] == "template_required"
        try:
            require_freeform_window(ticket_id)
        except WhatsAppTemplateRequiredError:
            pass
        else:
            raise AssertionError("Texto livre deveria ser bloqueado fora da janela de 24h.")

        non_whatsapp = next(row for row in DEMO_TICKETS if row["id"] == "1547")
        assert non_whatsapp["source"] != "whatsapp"
        not_applicable = get_whatsapp_service_window("1547", now=now)
        assert not_applicable["applicable"] is False
        assert not_applicable["template_required"] is False

        print("VENDRA_WHATSAPP_WINDOW_SMOKE_OK")
    finally:
        DEMO_MESSAGES[ticket_id] = original_messages


if __name__ == "__main__":
    main()
