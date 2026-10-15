"""Smoke v0.0.15: mapa padrão #1/#2/#3 -> Novo Lead/Qualificação/Proposta."""
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ["VENDRA_LOCAL_CONFIG"] = str(ROOT / "runtime" / "smoke_ai_routing_0015_credentials.json")
try:
    Path(os.environ["VENDRA_LOCAL_CONFIG"]).unlink()
except FileNotFoundError:
    pass
try:
    (ROOT / ".vendra-data" / "demo_state.json").unlink()
except FileNotFoundError:
    pass

from app.services.admin_settings_service import get_ai_routing_settings, save_ai_routing_settings
from app.services.ai_routing_service import route_contract


def main() -> None:
    auto = get_ai_routing_settings()
    assert auto["enabled"] is True, auto
    assert auto.get("source") == "standard_default", auto
    assert auto["routes"]["1"] == {"funnel_id": "funnel-demo-commercial", "stage_id": "stage-demo-1"}, auto
    assert auto["routes"]["2"] == {"funnel_id": "funnel-demo-commercial", "stage_id": "stage-demo-2"}, auto
    assert auto["routes"]["3"] == {"funnel_id": "funnel-demo-commercial", "stage_id": "stage-demo-3"}, auto

    contract = route_contract()
    assert contract["enabled"] is True, contract
    assert contract["routes"]["1"]["stage_name"].casefold() == "novo lead", contract
    assert contract["routes"]["2"]["stage_name"].casefold() == "qualificação", contract
    assert contract["routes"]["3"]["stage_name"].casefold() == "proposta", contract

    # Uma decisão explícita do administrador continua soberana.
    save_ai_routing_settings(enabled=False, routes={"1": {}, "2": {}, "3": {}})
    explicit = get_ai_routing_settings()
    assert explicit["enabled"] is False, explicit
    assert explicit.get("updated_at"), explicit
    print("VENDRA_AI_ROUTING_DEFAULTS_SMOKE_OK")


if __name__ == "__main__":
    main()
