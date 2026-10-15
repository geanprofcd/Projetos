from __future__ import annotations
import threading
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import dispatch_service
from app.services.dispatch_import_service import import_contact_file, start_bulk_dispatch, get_bulk_dispatch_state, list_import_items


def main() -> None:
    active = 0
    max_active = 0
    calls: list[str] = []
    lock = threading.Lock()

    def fake_post(url, payload, timeout=7.0):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
            calls.append(str(payload.get("phone") or ""))
        time.sleep(0.05)
        with lock:
            active -= 1
        return 200, "ok"

    dispatch_service._post_json = fake_post
    dispatch_service.get_dispatch_settings = lambda: {
        "enabled": True,
        "webhook_url": "http://127.0.0.1:9999/test",
        "template_key": "smoke",
    }
    batch = import_contact_file(
        filename="bulk-smoke.csv",
        content=b"Nome,Telefone\nAna,5587999993001\nBruno,5587999993002\nCaio,5587999993003\n",
        imported_by="00000000-0000-0000-0000-000000000001",
    )
    state = start_bulk_dispatch(batch_id=str(batch["id"]), requested_by="00000000-0000-0000-0000-000000000001")
    assert state["total"] == 3, state
    for _ in range(100):
        state = get_bulk_dispatch_state(str(batch["id"]))
        if state["status"] not in {"queued", "running"}:
            break
        time.sleep(0.05)
    assert state["status"] == "completed", state
    assert state["processed"] == 3, state
    assert max_active == 1, max_active
    assert len(calls) == 3, calls
    assert all(row["status"] == "submitted" for row in list_import_items(str(batch["id"])))
    print("dispatch bulk smoke: OK")


if __name__ == "__main__":
    main()
