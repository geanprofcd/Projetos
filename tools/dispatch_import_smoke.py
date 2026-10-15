"""Smoke local da importação de listas e disparo individual do VENDRA 0.0.11.

O teste preserva/restaura as coleções demo e usa um arquivo local separado para
as configurações de integração. Nenhuma mensagem real é enviada ao Meta.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["VENDRA_LOCAL_CONFIG"] = str(ROOT / "runtime" / "smoke_dispatch_import_credentials.json")
try:
    Path(os.environ["VENDRA_LOCAL_CONFIG"]).unlink()
except FileNotFoundError:
    pass

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import app
from app.services.admin_settings_service import save_dispatch_settings
from app.services.auth_service import csrf_token_for_session
from app.services.demo_store import (
    DEMO_CUSTOMERS,
    DEMO_DISPATCHES,
    DEMO_DISPATCH_IMPORT_BATCHES,
    DEMO_DISPATCH_IMPORT_ITEMS,
    DEMO_MESSAGES,
    DEMO_TICKETS,
    persist_demo_state,
)
from app.services.dispatch_import_service import import_contact_file, list_import_items, parse_contact_file

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
    snapshot = {
        "customers": deepcopy(DEMO_CUSTOMERS),
        "tickets": deepcopy(DEMO_TICKETS),
        "messages": deepcopy(DEMO_MESSAGES),
        "dispatches": deepcopy(DEMO_DISPATCHES),
        "batches": deepcopy(DEMO_DISPATCH_IMPORT_BATCHES),
        "items": deepcopy(DEMO_DISPATCH_IMPORT_ITEMS),
    }
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/hook"
        save_dispatch_settings(enabled=True, webhook_url=url, template_key="smoke-template")

        csv_data = (
            "Nome;Telefone\n"
            "Contato Um;+5587999991001\n"
            "Contato Dois;5587999991002\n"
            "Contato Duplicado;5587999991002\n"
            "Sem Telefone;abc\n"
        ).encode("utf-8")
        parsed, _ = parse_contact_file(filename="contatos.csv", content=csv_data)
        assert len(parsed) == 4
        batch = import_contact_file(filename="contatos.csv", content=csv_data, imported_by="u-admin")
        items = list_import_items(str(batch["id"]))
        assert batch["valid_count"] == 2, batch
        assert batch["duplicate_count"] == 1, batch
        assert batch["invalid_count"] == 1, batch
        assert [row["status"] for row in items].count("ready") == 2

        wb = Workbook()
        ws = wb.active
        ws.append(["Cliente", "WhatsApp"])
        ws.append(["Excel Um", "5587999992001"])
        ws.append(["Excel Dois", "5587999992002"])
        stream = BytesIO()
        wb.save(stream)
        excel_rows, _ = parse_contact_file(filename="contatos.xlsx", content=stream.getvalue())
        assert len(excel_rows) == 2

        client = TestClient(app)
        client.cookies.set("vendra_session", "demo-admin")
        csrf = csrf_token_for_session("demo-admin")
        upload = client.post(
            "/disparos/importar",
            data={"csrf_token": csrf},
            files={"arquivo": ("rota.csv", "Nome,Telefone\nRota Um,5587999993001\nRota Dois,5587999993002\n", "text/csv")},
            follow_redirects=False,
        )
        assert upload.status_code == 303, upload.text
        location = upload.headers["location"]
        assert "list=" in location
        batch_id = location.split("list=", 1)[1].split("&", 1)[0].split("#", 1)[0]

        page = client.get(f"/disparos?list={batch_id}")
        assert page.status_code == 200, page.text
        assert "Contatos importados" in page.text
        assert "Rota Um" in page.text
        assert "Enviar todos" in page.text

        route_items = list_import_items(batch_id)
        first = next(row for row in route_items if row["status"] == "ready")
        sent = client.post(
            f"/disparos/listas/{batch_id}/contatos/{first['id']}/disparar",
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        assert sent.status_code == 303, sent.text
        assert len(RECEIVED) == 1, RECEIVED
        assert RECEIVED[0]["phone"] == "5587999993001"
        after = list_import_items(batch_id)
        assert next(row for row in after if row["id"] == first["id"])["status"] == "submitted"
        assert sum(1 for row in after if row.get("dispatch_id")) == 1
        print("VENDRA_DISPATCH_IMPORT_SMOKE_OK")
    finally:
        server.shutdown()
        server.server_close()
        DEMO_CUSTOMERS[:] = snapshot["customers"]
        DEMO_TICKETS[:] = snapshot["tickets"]
        DEMO_MESSAGES.clear(); DEMO_MESSAGES.update(snapshot["messages"])
        DEMO_DISPATCHES[:] = snapshot["dispatches"]
        DEMO_DISPATCH_IMPORT_BATCHES[:] = snapshot["batches"]
        DEMO_DISPATCH_IMPORT_ITEMS[:] = snapshot["items"]
        persist_demo_state()
        try:
            Path(os.environ["VENDRA_LOCAL_CONFIG"]).unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
