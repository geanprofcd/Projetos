"""Smoke local da aba Disparos / integração Make do VENDRA 0.0.7."""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["VENDRA_LOCAL_CONFIG"] = str(ROOT / "runtime" / "smoke_dispatch_credentials.json")
try:
    Path(os.environ["VENDRA_LOCAL_CONFIG"]).unlink()
except FileNotFoundError:
    pass

from fastapi.testclient import TestClient

from app.main import app
from app.services.admin_settings_service import create_webhook, save_dispatch_settings
from app.services.dispatch_service import create_dispatch, update_dispatch_status

RECEIVED: list[dict] = []


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        size = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(size).decode("utf-8"))
        RECEIVED.append(payload)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, fmt, *args):
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/dispatch"
        save_dispatch_settings(enabled=True, webhook_url=url, template_key="smoke_template")
        row = create_dispatch(name="Cliente Disparo Smoke", phone="+55 87 97777-6666", requested_by="smoke")
        assert row["status"] == "submitted", row
        assert RECEIVED, "O stub do Make não recebeu o webhook."
        payload = RECEIVED[-1]
        assert payload["event"] == "whatsapp.dispatch.requested"
        assert payload["name"] == "Cliente Disparo Smoke"
        assert payload["phone"] == "5587977776666"
        assert payload["template_key"] == "smoke_template"
        assert payload["idempotency_key"]
        assert row.get("ticket_id")
        assert row.get("message_id")

        # Se o cliente responder ao disparo, a entrada deve cair no mesmo atendimento.
        hook, secret = create_webhook(name="Smoke Disparo WhatsApp", kind="whatsapp_text")
        client = TestClient(app)
        inbound = client.post(
            f"/webhooks/configurados/{hook['public_id']}",
            headers={"X-Vendra-Webhook-Secret": secret},
            json={
                "phone": "+55 87 97777-6666",
                "name": "Cliente Disparo Smoke",
                "message": "Recebi a mensagem e quero saber mais.",
                "external_message_id": "smoke-dispatch-reply-001",
            },
        )
        assert inbound.status_code == 202, inbound.text
        assert str(inbound.json()["ticket_id"]) == str(row["ticket_id"])

        delivered = update_dispatch_status(
            dispatch_id=row["id"],
            status="delivered",
            provider_message_id="wamid.smoke",
        )
        assert delivered["status"] == "delivered"
        assert delivered["provider_message_id"] == "wamid.smoke"

        client.cookies.set("vendra_session", "demo-admin")
        page = client.get("/disparos")
        assert page.status_code == 200
        assert "Cliente Disparo Smoke" in page.text
        assert "Disparos" in page.text
        print("VENDRA_DISPATCHES_SMOKE_OK")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
