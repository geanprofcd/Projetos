from dataclasses import replace
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4
from datetime import datetime,timezone
from copy import deepcopy
from unittest.mock import MagicMock,patch
import asyncio
from fastapi.testclient import TestClient
from app.whatsapp_callbacks import BridgeConfig,create_app


class HumanDatabase:
    def __init__(self,oid,tid,cid):
        self.calls=[];self.query_table='';self.error=None
        self.rows={'whatsapp_outbox':{'id':oid,'phone':'551100000000','ticket_id':tid},
            'tickets':{'id':tid,'source':'whatsapp','customer_id':cid},
            'customers':{'id':cid,'phone_normalized':'551100000000'}}
        self.result={'accepted':True,'authorized':True,'outbox_id':oid,'outbox':{
            'id':oid,'phone':'551100000000','body':'Resposta humana','claim_token':str(uuid4()),
            'delivery_policy':{'authorized_to_send':True,'template_required':False}}}
    def table(self,name):self.query_table=name;return self
    def select(self,*a):return self
    def eq(self,*a):return self
    def limit(self,*a):return self
    def execute(self):return SimpleNamespace(data=[self.rows[self.query_table]])
    def rpc(self,name,args):
        self.calls.append((name,args))
        if self.error:raise self.error
        return SimpleNamespace(execute=lambda:SimpleNamespace(data=deepcopy(self.result)))


class HumanBridgeTests(TestCase):
    def setUp(self):
        self.oid=str(uuid4());self.tid=str(uuid4());self.cid=str(uuid4())
        self.config=BridgeConfig('staging','a'*20,'https://'+'a'*20+'.supabase.co',
            'sb_secret_'+'x'*40,'s'*40,'123','456',('551100000000',),human_enabled=True)
        self.db=HumanDatabase(self.oid,self.tid,self.cid)
        self.client=TestClient(create_app(self.config,client=self.db));self.addCleanup(self.client.close)
        self.url='/webhooks/make/whatsapp/outbox/'+self.oid+'/prepare-human'
        self.payload={'phone_number_id':'123','business_account_id':'456','phone':'5511900000000',
            'occurred_at':datetime.now(timezone.utc).isoformat()}
        self.headers={'X-Webhook-Secret':self.config.webhook_secret}
    def post(self,payload=None,headers=None):return self.client.post(self.url,json=payload or self.payload,headers=self.headers if headers is None else headers)
    def test_route_absent_without_explicit_flag(self):
        with TestClient(create_app(replace(self.config,human_enabled=False),client=self.db)) as client:
            self.assertEqual(client.post(self.url,json=self.payload,headers=self.headers).status_code,404)
        self.assertFalse(self.db.calls)
    def test_authentication_and_account_rejected_before_reservation(self):
        self.assertEqual(self.post(headers={}).status_code,401)
        self.assertEqual(self.post(payload={**self.payload,'business_account_id':'999'}).status_code,403)
        self.assertFalse(self.db.calls)
    def test_unapproved_phone_rejected_without_rpc(self):
        self.assertEqual(self.post(payload={**self.payload,'phone':'551100000001'}).status_code,403)
        self.assertFalse(self.db.calls)
    def test_entity_phone_and_channel_rejected_without_rpc(self):
        self.db.rows['whatsapp_outbox']['phone']='551100000001'
        self.assertEqual(self.post().status_code,403)
        self.db.rows['whatsapp_outbox']['phone']='551100000000';self.db.rows['tickets']['source']='portal'
        self.assertEqual(self.post().status_code,403);self.assertFalse(self.db.calls)
    def test_human_prepare_uses_only_requested_outbox(self):
        r=self.post();self.assertEqual(r.status_code,202);self.assertTrue(r.json()['authorized'])
        self.assertEqual(self.db.calls,[('vendra_whatsapp_human_prepare_v1',{'p_outbox_id':self.oid})])
    def test_expected_ticket_rejects_other_outbox_before_reservation(self):
        self.assertEqual(self.post(payload={**self.payload,'expected_ticket_id':str(uuid4())}).status_code,403)
        self.assertFalse(self.db.calls)
        self.assertEqual(self.post(payload={**self.payload,'expected_ticket_id':self.tid}).status_code,202)
    def test_repeat_suppression_has_no_body_or_claim_token(self):
        self.db.result={'accepted':True,'authorized':False,'suppressed':True,'duplicate':True,'reason':'already_reserved_or_final'}
        r=self.post();self.assertEqual(r.status_code,202);self.assertNotIn('outbox',r.json())
        self.assertNotIn('claim_token',r.text)
    def test_missing_or_malformed_authorization_fails_closed(self):
        for result in [{'accepted':True},{'accepted':True,'authorized':1},{'accepted':True,'authorized':False,'outbox':{}}]:
            self.db.result=result;self.assertEqual(self.post().status_code,503)
    def test_invalid_reserved_payload_never_reaches_make_as_success(self):
        valid=deepcopy(self.db.result)
        for delta in [{'id':str(uuid4())},{'body':''},{'claim_token':'short'},
                      {'delivery_policy':None},{'delivery_policy':'invalid'},
                      {'delivery_policy':{'authorized_to_send':False,'template_required':False}}]:
            self.db.result=deepcopy(valid);self.db.result['outbox'].update(delta)
            self.assertEqual(self.post().status_code,503)
        self.db.result=valid;self.db.result['outbox']['phone']='551100000001'
        self.assertEqual(self.post().status_code,403)
    def test_database_failure_does_not_leak_diagnostics(self):
        self.db.error=RuntimeError('PRIVATE DATABASE KEY')
        r=self.post();self.assertEqual(r.status_code,503);self.assertNotIn('PRIVATE',r.text)

    def test_owned_transport_is_closed_on_app_shutdown(self):
        transport=MagicMock()
        with patch('httpx.Client',return_value=transport),patch('supabase.create_client',return_value=self.db):
            app=create_app(self.config)
        async def lifecycle():
            async with app.router.lifespan_context(app):
                transport.close.assert_not_called()
        asyncio.run(lifecycle());transport.close.assert_called_once()
