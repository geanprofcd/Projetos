"""Smoke local da IA de atendimento / handoff humano do VENDRA 0.0.7."""
from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["VENDRA_LOCAL_CONFIG"] = str(ROOT / "runtime" / "smoke_ai_credentials.json")
try:
    Path(os.environ["VENDRA_LOCAL_CONFIG"]).unlink()
except FileNotFoundError:
    pass

from fastapi.testclient import TestClient

from app.main import app
from app.services.admin_settings_service import create_webhook, save_ai_settings
from app.services.automation_service import get_ticket_ai_control, persist_ai_reply, set_ticket_ai_mode
from app.services.demo_store import DEMO_INTEGRATION_EVENTS, DEMO_MESSAGES, DEMO_WHATSAPP_OUTBOX, now_iso
from app.services.integration_service import update_outbox_status


def main() -> None:
    save_ai_settings(
        enabled=True,
        default_mode="ai",
        assistant_name="Vendra IA Smoke",
        control_webhook_enabled=False,
        control_webhook_url="",
    )

    # Mantém o smoke repetível mesmo quando o estado demo já foi persistido por uma execução anterior.
    previous_message_ids = {
        str(row.get("id"))
        for row in DEMO_MESSAGES.get("1548", [])
        if row.get("external_message_id") == "smoke-ai-reply-1" or row.get("id") == "smoke-window-open-0014"
    }
    DEMO_MESSAGES["1548"] = [
        row for row in DEMO_MESSAGES.get("1548", [])
        if row.get("external_message_id") != "smoke-ai-reply-1" and row.get("id") != "smoke-window-open-0014"
    ]
    DEMO_WHATSAPP_OUTBOX[:] = [row for row in DEMO_WHATSAPP_OUTBOX if str(row.get("message_id")) not in previous_message_ids]
    DEMO_INTEGRATION_EVENTS.pop("ai_reply:smoke-ai-reply-1", None)

    # A política 0.0.14 exige mensagem recente do cliente antes de texto livre.
    DEMO_MESSAGES.setdefault("1548", []).append({
        "id": "smoke-window-open-0014",
        "sender_id": "c1",
        "sender_name": "João da Silva",
        "body": "Mensagem recente para abrir a janela de 24h.",
        "created_at": now_iso(),
        "is_internal": False,
        "channel": "whatsapp",
        "direction": "inbound",
    })

    control = set_ticket_ai_mode("1548", mode="ai", actor_id="smoke", source="smoke")
    version = int(control["control_version"])
    before = len(DEMO_WHATSAPP_OUTBOX)
    reply = persist_ai_reply(
        ticket_id="1548",
        message="Resposta automática de teste.",
        control_version=version,
        external_message_id="smoke-ai-reply-1",
    )
    assert reply["accepted"] is True and not reply.get("suppressed")
    assert len(DEMO_WHATSAPP_OUTBOX) == before + 1
    msg = next(row for row in DEMO_MESSAGES["1548"] if row.get("external_message_id") == "smoke-ai-reply-1")
    assert msg.get("sender_kind") == "ai"
    assert msg.get("sender_name") == "Vendra IA Smoke"
    update_outbox_status(outbox_id=reply["outbox_id"], status="sent", provider_message_id="wamid.ai-smoke")
    duplicate = persist_ai_reply(
        ticket_id="1548",
        message="Resposta automática de teste.",
        control_version=version,
        external_message_id="smoke-ai-reply-1",
    )
    assert duplicate.get("duplicate") is True

    human = set_ticket_ai_mode("1548", mode="human", actor_id="smoke", source="smoke")
    assert human["should_respond"] is False
    stale = persist_ai_reply(
        ticket_id="1548",
        message="Esta resposta deve ser bloqueada.",
        control_version=version,
        external_message_id="smoke-ai-stale",
    )
    assert stale.get("suppressed") is True
    assert stale.get("reason") in {"human_takeover", "stale_control_version"}

    # Contrato Make -> VENDRA: uma nova entrada recebe a decisão da automação.
    hook, secret = create_webhook(name="Smoke IA WhatsApp", kind="whatsapp_text")
    client = TestClient(app)
    response = client.post(
        f"/webhooks/configurados/{hook['public_id']}",
        headers={"X-Vendra-Webhook-Secret": secret},
        json={
            "phone": "+55 87 98888-7777",
            "name": "Cliente IA Smoke",
            "message": "Olá, quero atendimento.",
            "external_message_id": "smoke-inbound-ai-001",
        },
    )
    assert response.status_code == 202, response.text
    data = response.json()
    assert data["automation"]["should_respond"] is True
    assert data["automation"]["mode"] == "ai"
    assert int(data["automation"]["control_version"]) >= 1

    # O mesmo segredo autentica o callback da IA.
    ai_response = client.post(
        "/webhooks/make/ai/reply",
        headers={"X-Webhook-Secret": secret},
        json={
            "ticket_id": data["ticket_id"],
            "message": "Olá! Como posso ajudar?",
            "control_version": data["automation"]["control_version"],
            "external_message_id": "smoke-ai-callback-001",
        },
    )
    assert ai_response.status_code == 202, ai_response.text
    assert ai_response.json().get("suppressed") is False

    fetched = client.get(
        f"/webhooks/make/ai/control/{data['ticket_id']}",
        headers={"X-Webhook-Secret": secret},
    )
    assert fetched.status_code == 200
    assert fetched.json()["automation"]["should_respond"] is True

    assert get_ticket_ai_control(data["ticket_id"])["mode"] == "ai"
    print("VENDRA_AI_HANDOFF_SMOKE_OK")


if __name__ == "__main__":
    main()
