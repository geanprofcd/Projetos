"""Smoke VENDRA 0.0.17: provider_message_id + sent/delivered/read/failed por wamid."""
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
os.environ["VENDRA_LOCAL_CONFIG"]=str(ROOT/"runtime"/"smoke_provider_status_0017_credentials.json")
try: Path(os.environ["VENDRA_LOCAL_CONFIG"]).unlink()
except FileNotFoundError: pass
try: (ROOT/".vendra-data"/"demo_state.json").unlink()
except FileNotFoundError: pass

from fastapi.testclient import TestClient
from app.main import app
from app.services.admin_settings_service import create_webhook, save_ai_settings
from app.services.integration_service import get_outbox_item


def create_ai_reply(c: TestClient, hook: dict, secret: str, suffix: str):
    inbound=c.post(f"/webhooks/configurados/{hook['public_id']}",headers={"X-Vendra-Webhook-Secret":secret},json={
        "phone":"+55 87 94444-1717","name":"Lead Status 0017","message":f"Mensagem {suffix}","external_message_id":f"wamid-in-0017-{suffix}"
    })
    assert inbound.status_code==202, inbound.text
    d=inbound.json(); ticket_id=str(d["ticket_id"]); version=int(d["automation"]["control_version"])
    reply=c.post("/webhooks/make/ai/reply",headers={"X-Webhook-Secret":secret},json={
        "ticket_id":ticket_id,"message":f"Resposta {suffix}","control_version":version,
        "route_code":"1","delivery_mode":"inline_make","external_message_id":f"ai-0017-{suffix}"
    })
    assert reply.status_code==202, reply.text
    return ticket_id, reply.json()["outbox_id"], reply.json()["message_id"]


def main():
    save_ai_settings(enabled=True, default_mode="ai", assistant_name="IA VENDRA", control_webhook_enabled=False, control_webhook_url="")
    hook,secret=create_webhook(name="Smoke provider status 0017",kind="whatsapp_text")
    c=TestClient(app)

    ticket_id,outbox_id,message_id=create_ai_reply(c,hook,secret,"a")
    wamid="wamid.HBgMSTATUS0017A"
    sent=c.post(f"/webhooks/make/whatsapp/outbox/{outbox_id}/status",headers={"X-Webhook-Secret":secret},json={"status":"sent","provider_message_id":wamid})
    assert sent.status_code==200 and sent.json()["status"]=="sent", sent.text

    delivered=c.post("/webhooks/make/whatsapp/provider-status",headers={"X-Webhook-Secret":secret},json={
        "provider_message_id":wamid,"status":"delivered","occurred_at":"1791302400","recipient_id":"5587944441717"
    })
    assert delivered.status_code==200 and delivered.json()["updated"] is True and delivered.json()["status"]=="delivered", delivered.text

    duplicate=c.post("/webhooks/make/whatsapp/provider-status",headers={"X-Webhook-Secret":secret},json={
        "provider_message_id":wamid,"status":"delivered","occurred_at":"1791302400","recipient_id":"5587944441717"
    })
    assert duplicate.status_code==200 and duplicate.json()["ignored"] is True, duplicate.text

    read=c.post("/webhooks/make/whatsapp/provider-status",headers={"X-Webhook-Secret":secret},json={
        "provider_message_id":wamid,"status":"read","occurred_at":1791302460,"recipient_id":"5587944441717"
    })
    assert read.status_code==200 and read.json()["updated"] is True and read.json()["status"]=="read", read.text

    late=c.post("/webhooks/make/whatsapp/provider-status",headers={"X-Webhook-Secret":secret},json={
        "provider_message_id":wamid,"status":"delivered","occurred_at":1791302420,"recipient_id":"5587944441717"
    })
    assert late.status_code==200 and late.json()["ignored"] is True and late.json()["status"]=="read", late.text

    failed_after_read=c.post("/webhooks/make/whatsapp/provider-status",headers={"X-Webhook-Secret":secret},json={
        "provider_message_id":wamid,"status":"failed","occurred_at":1791302470,"recipient_id":"5587944441717","error_message":"late failure"
    })
    assert failed_after_read.status_code==200 and failed_after_read.json()["ignored"] is True and failed_after_read.json()["status"]=="read", failed_after_read.text

    c.cookies.set("vendra_session","demo-admin")
    feed=c.get(f"/atendimentos/{ticket_id}/mensagens.json")
    assert feed.status_code==200, feed.text
    msg=next(row for row in feed.json()["messages"] if row["id"]==message_id)
    assert msg["delivery_status"]=="read", msg

    # Corrida segura: status chega antes do callback sent que vincula o wamid.
    ticket_id2,outbox_id2,_=create_ai_reply(c,hook,secret,"b")
    wamid2="wamid.HBgMSTATUS0017B"
    early=c.post("/webhooks/make/whatsapp/provider-status",headers={"X-Webhook-Secret":secret},json={
        "provider_message_id":wamid2,"status":"delivered","occurred_at":1791302500,"recipient_id":"5587944441717"
    })
    assert early.status_code==200 and early.json()["pending_match"] is True, early.text
    sent2=c.post(f"/webhooks/make/whatsapp/outbox/{outbox_id2}/status",headers={"X-Webhook-Secret":secret},json={"status":"sent","provider_message_id":wamid2})
    assert sent2.status_code==200, sent2.text
    row=get_outbox_item(outbox_id2)
    assert row and row["status"]=="delivered", row

    # Falha normal antes de delivered/read deve ser persistida.
    ticket_id3,outbox_id3,_=create_ai_reply(c,hook,secret,"c")
    wamid3="wamid.HBgMSTATUS0017C"
    sent3=c.post(f"/webhooks/make/whatsapp/outbox/{outbox_id3}/status",headers={"X-Webhook-Secret":secret},json={"status":"sent","provider_message_id":wamid3})
    assert sent3.status_code==200
    failed=c.post("/webhooks/make/whatsapp/provider-status",headers={"X-Webhook-Secret":secret},json={
        "provider_message_id":wamid3,"status":"failed","occurred_at":1791302600,"recipient_id":"5587944441717","error_message":"provider failed"
    })
    assert failed.status_code==200 and failed.json()["status"]=="failed" and failed.json()["updated"] is True, failed.text

    print("VENDRA_PROVIDER_STATUS_SMOKE_OK")

if __name__=="__main__": main()
