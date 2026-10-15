"""Smoke local da Central de Integrações / testes Make do VENDRA 0.0.8."""
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

os.environ["VENDRA_LOCAL_CONFIG"] = str(ROOT / "runtime" / "smoke_integration_diag_credentials.json")
try:
    Path(os.environ["VENDRA_LOCAL_CONFIG"]).unlink()
except FileNotFoundError:
    pass

from fastapi.testclient import TestClient

from app.main import app
from app.services.admin_settings_service import save_ai_settings, save_dispatch_settings
from app.services.auth_service import csrf_token_for_session
from app.services.integration_diagnostics_service import (
    contract_examples,
    integration_channel_overview,
    list_diagnostic_events,
    test_ai_control_webhook,
    test_dispatch_webhook,
)

RECEIVED: list[dict] = []


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        size = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(size).decode("utf-8"))
        RECEIVED.append(payload)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true,"source":"make-stub"}')

    def log_message(self, fmt, *args):
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/hook"
        save_ai_settings(
            enabled=True,
            default_mode="ai",
            assistant_name="IA Diagnóstico",
            control_webhook_enabled=True,
            control_webhook_url=url,
        )
        save_dispatch_settings(enabled=True, webhook_url=url, template_key="teste")

        ai_result = test_ai_control_webhook()
        dispatch_result = test_dispatch_webhook()
        assert ai_result["ok"] is True
        assert dispatch_result["ok"] is True
        assert len(RECEIVED) == 2
        assert RECEIVED[0]["event"] == "vendra.integration.test"
        assert RECEIVED[0]["test_only"] is True
        assert RECEIVED[1]["channel"] == "dispatches"
        assert "phone" not in RECEIVED[1]

        rows = list_diagnostic_events(10)
        assert len(rows) >= 2
        overview = integration_channel_overview()
        assert overview["ai"]["enabled"] is True
        assert overview["ai"]["control_webhook_configured"] is True
        assert overview["dispatches"]["webhook_configured"] is True

        contracts = contract_examples("http://127.0.0.1:8010")
        assert contracts["ai_reply"]["path"] == "/webhooks/make/ai/reply"
        assert "control_version" in contracts["ai_reply"]["payload"]

        client = TestClient(app)
        client.cookies.set("vendra_session", "demo-admin")
        page = client.get("/integracoes")
        assert page.status_code == 200, page.text
        assert "Diagnóstico de conectividade" in page.text
        assert "Fluxo operacional recomendado" in page.text
        assert "/webhooks/make/ai/reply" in page.text

        csrf = csrf_token_for_session("demo-admin")
        routed_ai = client.post("/integracoes/testar/ia", data={"csrf_token": csrf}, follow_redirects=False)
        assert routed_ai.status_code == 303, routed_ai.text
        assert "ai_ok" in routed_ai.headers.get("location", "")
        routed_dispatch = client.post("/integracoes/testar/disparos", data={"csrf_token": csrf}, follow_redirects=False)
        assert routed_dispatch.status_code == 303, routed_dispatch.text
        assert "dispatch_ok" in routed_dispatch.headers.get("location", "")
        assert len(RECEIVED) == 4
        print("VENDRA_INTEGRATION_DIAGNOSTICS_SMOKE_OK")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
