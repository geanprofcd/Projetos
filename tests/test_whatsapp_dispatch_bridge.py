from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4
import base64
import unittest
from fastapi.testclient import TestClient
from app.whatsapp_callbacks import BridgeConfig, DispatchBinding, create_app
from tests.test_whatsapp_control_bridge import DatabaseStub


class DispatchBridgeSecurity(unittest.TestCase):
    def setUp(self):
        self.ticket,self.customer,self.outbox,self.dispatch=[str(uuid4()) for _ in range(4)]
        self.config=BridgeConfig('staging','a'*20,'https://'+'a'*20+'.supabase.co',
            'sb_secret_'+'x'*40,'s'*40,'123','456',('551100000000',),dispatch_enabled=True)
        self.db=DatabaseStub(self.ticket,self.customer,self.outbox)
        self.db.rows['dispatches']={self.dispatch:{'phone':'551100000000','ticket_id':self.ticket}}
        self.client=TestClient(create_app(self.config,client=self.db))
        self.headers={'X-Webhook-Secret':self.config.webhook_secret}
        self.meta={'phone_number_id':'123','business_account_id':'456','occurred_at':datetime.now(timezone.utc).isoformat()}
        self.prepare=dict(self.meta,phone='551100000000',name='CODEX',template_key='continuar_atendimento_vendra')
        self.binding=dict(self.meta,outbox_id=self.outbox,recipient_id='551100000000',provider_message_id='wamid-unit',claim_token='c'*36)
        self.prepare_url='/webhooks/make/disparos/'+self.dispatch+'/prepare'
        self.bind_url='/webhooks/make/disparos/'+self.dispatch+'/status'
    def tearDown(self):self.client.close()

    def test_disabled_flag_registers_no_dispatch_route(self):
        with TestClient(create_app(replace(self.config,dispatch_enabled=False),client=self.db)) as client:
            for url,body in [(self.prepare_url,self.prepare),(self.bind_url,self.binding)]:
                self.assertEqual(client.post(url,json=body,headers=self.headers).status_code,404)
        self.assertFalse(self.db.reads);self.assertFalse(self.db.rpc_calls)

    def test_secret_and_meta_account_checked_before_database(self):
        for url,body in [(self.prepare_url,self.prepare),(self.bind_url,self.binding)]:
            self.assertEqual(self.client.post(url,json=body).status_code,401)
            self.assertEqual(self.client.post(url,json=dict(body,phone_number_id='999'),headers=self.headers).status_code,403)
        self.assertFalse(self.db.reads);self.assertFalse(self.db.rpc_calls)

    def test_forged_dispatch_and_customer_scope_rejected(self):
        for table,key,field in [('dispatches',self.dispatch,'phone'),('customers',self.customer,'phone_normalized')]:
            self.db.rows[table][key][field]='551100000001'
            self.assertEqual(self.client.post(self.prepare_url,json=self.prepare,headers=self.headers).status_code,403)
            self.db.rows[table][key][field]='551100000000'
        self.assertFalse(self.db.rpc_calls)

    def test_outbox_scope_rejected_before_binding(self):
        self.db.rows['whatsapp_outbox'][self.outbox]['phone']='551100000001'
        self.assertEqual(self.client.post(self.bind_url,json=self.binding,headers=self.headers).status_code,403)
        self.assertFalse(self.db.rpc_calls)

    def test_payload_validation_rejects_unsupported_template_and_ambiguous_name(self):
        for delta in [{'template_key':'other'},{'name_base64':'Q09ERVg='},{'name':''}]:
            self.assertEqual(self.client.post(self.prepare_url,json=dict(self.prepare,**delta),headers=self.headers).status_code,422)
        self.assertFalse(self.db.rpc_calls)

    def test_unicode_name_decoded_before_atomic_reservation(self):
        text='Nome "teste" 😀';body=dict(self.prepare,name_base64=base64.b64encode(text.encode()).decode());body.pop('name')
        self.db.responses['vendra_dispatch_prepare_v1']={'accepted':True,'authorized':False,'suppressed':True}
        self.assertEqual(self.client.post(self.prepare_url,json=body,headers=self.headers).status_code,202)
        name,args=self.db.rpc_calls[0];self.assertEqual(name,'vendra_dispatch_prepare_v1');self.assertEqual(args['p_name'],text)

    def test_authorized_reservation_phone_rechecked_after_rpc(self):
        self.db.responses['vendra_dispatch_prepare_v1']={'accepted':True,'authorized':True,'outbox':{'phone':'551100000001'}}
        self.assertEqual(self.client.post(self.prepare_url,json=self.prepare,headers=self.headers).status_code,403)

    def test_missing_authorized_reservation_is_not_success(self):
        self.db.responses['vendra_dispatch_prepare_v1']={'accepted':True,'authorized':True}
        self.assertEqual(self.client.post(self.prepare_url,json=self.prepare,headers=self.headers).status_code,503)

    def test_duplicate_stays_suppressed_without_token(self):
        expected={'accepted':True,'authorized':False,'suppressed':True,'duplicate':True}
        self.db.responses['vendra_dispatch_prepare_v1']=expected
        response=self.client.post(self.prepare_url,json=self.prepare,headers=self.headers)
        self.assertEqual(response.status_code,202);self.assertEqual(response.json(),expected)

    def test_binding_uses_dispatch_and_outbox_ids_and_secret_token(self):
        response=self.client.post(self.bind_url,json=self.binding,headers=self.headers)
        self.assertEqual(response.status_code,202)
        name,args=self.db.rpc_calls[0];self.assertEqual(name,'vendra_dispatch_bind_v1')
        self.assertEqual(args['p_dispatch_id'],self.dispatch);self.assertEqual(args['p_outbox_id'],self.outbox)
        self.assertEqual(args['p_claim_token'],'c'*36)
        self.assertNotIn('c'*36,repr(DispatchBinding(**self.binding)))

    def test_provider_wrapper_only_in_explicit_dispatch_profile(self):
        status=dict(self.meta,provider_message_id='wamid-unit',status='read',recipient_id='551100000000')
        self.assertEqual(self.client.post('/webhooks/make/whatsapp/provider-status',json=status,headers=self.headers).status_code,202)
        self.assertEqual(self.db.rpc_calls[0][0],'vendra_dispatch_provider_status_v1')

    def test_dispatch_flag_must_be_boolean(self):
        with self.assertRaises(ValueError):replace(self.config,dispatch_enabled='true').validate()


if __name__=='__main__':unittest.main()
