"""Smoke end-to-end local: Disparo -> resposta do lead -> IA -> handoff humano -> reconexão."""
from __future__ import annotations
import json, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
os.environ["VENDRA_LOCAL_CONFIG"]=str(ROOT/"runtime"/"smoke_ai_conversation_credentials.json")
try: Path(os.environ["VENDRA_LOCAL_CONFIG"]).unlink()
except FileNotFoundError: pass
from fastapi.testclient import TestClient
from app.main import app
from app.services.admin_settings_service import create_webhook, save_ai_settings, save_dispatch_settings
from app.services.automation_service import get_ticket_ai_control, disconnect_ticket_from_ai, connect_ticket_to_ai
from app.services.demo_store import DEMO_MESSAGES, DEMO_WHATSAPP_OUTBOX
from app.services.dispatch_service import create_dispatch
from app.services.auth_service import csrf_token_for_session

RECEIVED=[]
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        size=int(self.headers.get("Content-Length","0")); payload=json.loads(self.rfile.read(size).decode())
        RECEIVED.append(payload); self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}')
    def log_message(self,fmt,*args): return

def main():
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler); threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        url=f"http://127.0.0.1:{server.server_port}/hook"
        save_ai_settings(enabled=True, default_mode="ai", assistant_name="IA Conversa", control_webhook_enabled=True, control_webhook_url=url)
        save_dispatch_settings(enabled=True, webhook_url=url, template_key="lead_inicio")
        d=create_dispatch(name="Lead Conversa 0012", phone="+55 87 96666-5512", requested_by="admin")
        ticket_id=str(d["ticket_id"]); ctl=get_ticket_ai_control(ticket_id)
        assert ctl["route_to_ai"] is True and ctl["connected"] is True
        assert any(x.get("event")=="whatsapp.dispatch.requested" and x.get("ticket_id")==ticket_id for x in RECEIVED)
        dp=next(x for x in RECEIVED if x.get("event")=="whatsapp.dispatch.requested" and x.get("ticket_id")==ticket_id)
        assert dp["automation"]["route_to_ai"] is True

        hook,secret=create_webhook(name="Smoke conversa 0012",kind="whatsapp_text")
        client=TestClient(app)
        inbound=client.post(f"/webhooks/configurados/{hook['public_id']}",headers={"X-Vendra-Webhook-Secret":secret},json={"phone":"+55 87 96666-5512","name":"Lead Conversa 0012","message":"Quero saber mais","external_message_id":"smoke-0012-in-1"})
        assert inbound.status_code==202, inbound.text
        data=inbound.json(); assert str(data["ticket_id"])==ticket_id
        assert data["automation"]["route_to_ai"] is True
        assert data["automation"]["make_instruction"]=="ROUTE_TO_AI"
        version=int(data["automation"]["control_version"])

        reply=client.post("/webhooks/make/ai/reply",headers={"X-Webhook-Secret":secret},json={"ticket_id":ticket_id,"message":"Resposta IA visível no VENDRA","control_version":version,"external_message_id":"smoke-0012-ai-1"})
        assert reply.status_code==202 and reply.json().get("suppressed") is False, reply.text
        assert any(m.get("body")=="Resposta IA visível no VENDRA" and m.get("sender_kind")=="ai" for m in DEMO_MESSAGES[ticket_id])
        assert any(str(o.get("ticket_id"))==ticket_id for o in DEMO_WHATSAPP_OUTBOX)
        client.cookies.set("vendra_session","demo-admin")
        page=client.get(f"/atendimentos/{ticket_id}")
        assert page.status_code==200 and "Resposta IA visível no VENDRA" in page.text
        assert "Desconectar IA" in page.text

        csrf=csrf_token_for_session("demo-admin")
        ui_disconnect=client.post(f"/atendimentos/{ticket_id}/ia/desconectar",data={"csrf_token":csrf},follow_redirects=False)
        assert ui_disconnect.status_code==303
        human=get_ticket_ai_control(ticket_id)
        assert human["route_to_ai"] is False and human["connection_state"]=="disconnected"
        inbound2=client.post(f"/webhooks/configurados/{hook['public_id']}",headers={"X-Vendra-Webhook-Secret":secret},json={"phone":"+55 87 96666-5512","name":"Lead Conversa 0012","message":"Humano?","external_message_id":"smoke-0012-in-2"})
        d2=inbound2.json(); assert d2["automation"]["route_to_ai"] is False and d2["automation"]["make_instruction"]=="STOP_AT_VENDRA"
        stale=client.post("/webhooks/make/ai/reply",headers={"X-Webhook-Secret":secret},json={"ticket_id":ticket_id,"message":"Não pode sair","control_version":version,"external_message_id":"smoke-0012-ai-stale"})
        assert stale.status_code==202 and stale.json().get("suppressed") is True

        disconnected_page=client.get(f"/atendimentos/{ticket_id}")
        assert "Reconectar IA" in disconnected_page.text
        ui_connect=client.post(f"/atendimentos/{ticket_id}/ia/conectar",data={"csrf_token":csrf},follow_redirects=False)
        assert ui_connect.status_code==303
        re=get_ticket_ai_control(ticket_id)
        assert re["route_to_ai"] is True and int(re["control_version"])>version
        print("VENDRA_AI_CONVERSATION_FLOW_SMOKE_OK")
    finally:
        server.shutdown(); server.server_close()
if __name__=="__main__": main()
