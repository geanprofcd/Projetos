"""Smoke local v0.0.13: Meta/Make normalizado -> VENDRA -> IA -> VENDRA -> Make/Meta + funil."""
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
os.environ["VENDRA_LOCAL_CONFIG"]=str(ROOT/"runtime"/"smoke_ai_make_meta_0013_credentials.json")
try: Path(os.environ["VENDRA_LOCAL_CONFIG"]).unlink()
except FileNotFoundError: pass
try: (ROOT/".vendra-data"/"demo_state.json").unlink()
except FileNotFoundError: pass
from fastapi.testclient import TestClient
from app.main import app
from app.services.admin_settings_service import create_webhook, save_ai_settings, get_ai_routing_settings
from app.services.automation_service import disconnect_ticket_from_ai
from app.services.opportunity_service import list_opportunities


def main():
    save_ai_settings(enabled=True, default_mode="ai", assistant_name="IA VENDRA", control_webhook_enabled=False, control_webhook_url="")
    routing_defaults = get_ai_routing_settings()
    assert routing_defaults["enabled"] is True, routing_defaults
    assert routing_defaults["routes"]["1"]["stage_id"] == "stage-demo-1", routing_defaults
    assert routing_defaults["routes"]["2"]["stage_id"] == "stage-demo-2", routing_defaults
    assert routing_defaults["routes"]["3"]["stage_id"] == "stage-demo-3", routing_defaults
    hook,secret=create_webhook(name="Smoke Make Meta 0013",kind="whatsapp_text")
    c=TestClient(app)
    inbound=c.post(f"/webhooks/configurados/{hook['public_id']}",headers={"X-Vendra-Webhook-Secret":secret},json={
        "phone":"+55 87 95555-1313","name":"Lead Bridge 0013","message":"Olá, quero saber mais","external_message_id":"wamid-in-0013-a"
    })
    assert inbound.status_code==202, inbound.text
    data=inbound.json(); ticket_id=str(data["ticket_id"]); auto=data["automation"]
    assert auto["route_to_ai"] is True and auto["thread_id"]==f"VENDRA-{ticket_id}"
    version=int(auto["control_version"])

    reply=c.post("/webhooks/make/ai/reply",headers={"X-Webhook-Secret":secret},json={
        "ticket_id":ticket_id,"message":"Resposta IA #1","control_version":version,
        "route_code":"#1","delivery_mode":"inline_make","external_message_id":"ai-run-0013-a"
    })
    assert reply.status_code==202, reply.text
    r=reply.json(); assert r["suppressed"] is False and r["outbox"]["status"]=="claimed"
    assert r["routing"]["applied"] is True and r["routing"]["stage_id"]=="stage-demo-1"
    outbox_id=r["outbox_id"]
    status=c.post(f"/webhooks/make/whatsapp/outbox/{outbox_id}/status",headers={"X-Webhook-Secret":secret},json={"status":"sent","provider_message_id":"wamid-out-0013-a"})
    assert status.status_code==200, status.text

    inbound2=c.post(f"/webhooks/configurados/{hook['public_id']}",headers={"X-Vendra-Webhook-Secret":secret},json={
        "phone":"+55 87 95555-1313","name":"Lead Bridge 0013","message":"Como funciona?","external_message_id":"wamid-in-0013-b"
    })
    d2=inbound2.json(); assert str(d2["ticket_id"])==ticket_id
    version2=int(d2["automation"]["control_version"])
    reply2=c.post("/webhooks/make/ai/reply",headers={"X-Webhook-Secret":secret},json={
        "ticket_id":ticket_id,"message":"Resposta IA #2","control_version":version2,
        "route_code":"2","delivery_mode":"inline_make","external_message_id":"ai-run-0013-b"
    })
    assert reply2.status_code==202 and reply2.json()["routing"]["stage_id"]=="stage-demo-2", reply2.text
    opps=list_opportunities(status="open",ticket_id=ticket_id); assert len(opps)==1 and opps[0]["stage_id"]=="stage-demo-2"

    inbound3=c.post(f"/webhooks/configurados/{hook['public_id']}",headers={"X-Vendra-Webhook-Secret":secret},json={
        "phone":"+55 87 95555-1313","name":"Lead Bridge 0013","message":"Quero agendar","external_message_id":"wamid-in-0013-c"
    })
    d3=inbound3.json(); version3=int(d3["automation"]["control_version"])
    reply3=c.post("/webhooks/make/ai/reply",headers={"X-Webhook-Secret":secret},json={
        "ticket_id":ticket_id,"message":"Vamos avançar","control_version":version3,
        "route_code":"3","delivery_mode":"inline_make","external_message_id":"ai-run-0013-c"
    })
    assert reply3.status_code==202 and reply3.json()["routing"]["stage_id"]=="stage-demo-3", reply3.text
    opps=list_opportunities(status="open",ticket_id=ticket_id); assert len(opps)==1 and opps[0]["stage_id"]=="stage-demo-3"

    disconnect_ticket_from_ai(ticket_id,actor_id="admin",source="smoke")
    stale=c.post("/webhooks/make/ai/reply",headers={"X-Webhook-Secret":secret},json={
        "ticket_id":ticket_id,"message":"Não deve sair","control_version":version3,
        "route_code":"3","delivery_mode":"inline_make","external_message_id":"ai-run-0013-stale"
    })
    assert stale.status_code==202 and stale.json()["suppressed"] is True, stale.text
    opps=list_opportunities(status="open",ticket_id=ticket_id); assert opps[0]["stage_id"]=="stage-demo-3"

    c.cookies.set("vendra_session","demo-admin")
    settings=c.get("/configuracoes")
    assert settings.status_code==200 and "Roteamento comercial da IA" in settings.text and "Salvar roteamento" in settings.text
    integrations=c.get("/integracoes")
    assert integrations.status_code==200 and "delivery_mode" in integrations.text and "route_code" in integrations.text
    print("VENDRA_AI_MAKE_META_BRIDGE_SMOKE_OK")

if __name__=="__main__": main()
