"""H1-005B7 - testes offline / nunca acionam Meta, Make, outbox ou escritas reais."""
from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

os.environ.update({
    'APP_ENV':'staging', 'DEMO_MODE':'false',
    'VENDRA_STAGING_REF':'exampletest123',
    'SUPABASE_URL':'https://exampletest123.supabase.co',
    'SUPABASE_ANON_KEY':'sb_publishable_mock_for_unit_test_123456789',
    'SUPABASE_SERVICE_ROLE_KEY':'sb_secret_mock_for_unit_test_123456789',
    'SECRET_KEY':'session-secret-unit-test-very-long',
    'META_ACCESS_TOKEN':'','MAKE_WEBHOOK_SECRET':'','SMTP_HOST':'',
})
from app.services import staging_delivery_preflight_service as svc
from app.services import staging_dispatch_preview_service as preview

OPP,CUST,FUN,STAGE,ACTOR = [str(uuid4()) for _ in range(5)]
DATA={
    'opportunities':{'id':OPP,'customer_id':CUST,'funnel_id':FUN,'stage_id':STAGE,
                     'status':'open','archived_at':None,'title':'Negocio exemplo'},
    'customers':{'id':CUST,'status':'active','name':'Cliente Exemplo',
                 'company_name':'Empresa XPTO','phone_normalized':'5511999996094'},
    'sales_funnels':{'id':FUN,'name':'Funil de homologacao'},
    'funnel_stages':{'id':STAGE,'funnel_id':FUN,'name':'Qualificacao'},
}

class CountCall:
    def __init__(self,table,counts):self.table=table;self.counts=counts
    def select(self,*args,**kwargs):
        if args!=('id',) or kwargs!={'count':'exact'}:
            raise AssertionError('Apenas COUNT de id e autorizado')
        return self
    def limit(self,value):
        if value!=1:raise AssertionError('Deve limitar retorno de linhas')
        return self
    def execute(self):return SimpleNamespace(data=[],count=self.counts[self.table])
    def insert(self,*_):raise AssertionError('Escrita proibida no preflight')

class FakeDb:
    def __init__(self,counts=None):
        self.counts={'dispatches':0,'whatsapp_outbox':0,'messages':0,
                     'staging_dispatch_simulations':1}
        if counts:self.counts.update(counts)
        self.tables=[]
    def table(self,name):
        self.tables.append(name)
        return CountCall(name,self.counts)
    def rpc(self,*_):raise AssertionError('RPC proibida no preflight')

class H1005B7(unittest.TestCase):
    def setUp(self):
        self.db=FakeDb()
        self.db_patch=patch.object(svc,'get_admin_client',return_value=self.db)
        self.db_patch.start()
        self.lookup=patch.object(preview,'_get',side_effect=lambda name,_id:DATA.get(name))
        self.lookup.start()
    def tearDown(self):
        self.lookup.stop();self.db_patch.stop()

    def test_01_readiness_empty_real_queues(self):
        report=svc.readiness()
        self.assertTrue(report['real_queue_clean'])
        self.assertFalse(report['ready_to_send'])
        self.assertFalse(report['worker_enabled'])
        self.assertFalse(report['external_sends_enabled'])
        self.assertEqual(report['counts']['staging_dispatch_simulations'],1)
    def test_02_readiness_detects_real_records(self):
        self.db.counts['whatsapp_outbox']=1
        self.assertFalse(svc.readiness()['real_queue_clean'])
    def test_03_blocks_plan_if_outbox_has_rows(self):
        self.db.counts['dispatches']=1
        with self.assertRaisesRegex(ValueError,'registros de envio real'):
            svc.make_plan(opportunity_id=OPP,content='Teste',actor_id=ACTOR)
    def test_04_plan_correct_and_no_persistence(self):
        report=svc.make_plan(opportunity_id=OPP,content='Olá, {{nome}}!',actor_id=ACTOR)
        self.assertEqual(report['rendered_message'],'Olá, Cliente Exemplo!')
        self.assertEqual(report['phone_masked'],'•••• 6094')
        self.assertFalse(report['sent'])
        self.assertFalse(report['queued'])
        self.assertFalse(report['persisted'])
        self.assertEqual(report['delivery_state'],'not_queued')
        self.assertNotIn('5511999996094',repr(report))
    def test_05_same_input_same_reference(self):
        kw={'opportunity_id':OPP,'content':'Olá, {{nome}}!','actor_id':ACTOR}
        a=svc.make_plan(**kw)['idempotency_reference'];b=svc.make_plan(**kw)['idempotency_reference']
        self.assertEqual(a,b)
    def test_06_different_content_new_reference(self):
        kw={'opportunity_id':OPP,'actor_id':ACTOR}
        a=svc.make_plan(**kw,content='Teste 1')['idempotency_reference']
        b=svc.make_plan(**kw,content='Teste 2')['idempotency_reference']
        self.assertNotEqual(a,b)
    def test_07_invalid_phone(self):
        customer={**DATA['customers'],'phone_normalized':'123'}
        with patch.object(preview,'_get',side_effect=lambda n,_id:customer if n=='customers' else DATA.get(n)):
            with self.assertRaisesRegex(ValueError,'Telefone inválido'):
                svc.make_plan(opportunity_id=OPP,content='Teste',actor_id=ACTOR)
    def test_08_closed_opportunity(self):
        closed={**DATA['opportunities'],'status':'won'}
        with patch.object(preview,'_get',side_effect=lambda n,_id:closed if n=='opportunities' else DATA.get(n)):
            with self.assertRaisesRegex(ValueError,'aberta'):
                svc.make_plan(opportunity_id=OPP,content='Teste',actor_id=ACTOR)
    def test_09_inconsistent_stage(self):
        stage={**DATA['funnel_stages'],'funnel_id':str(uuid4())}
        with patch.object(preview,'_get',side_effect=lambda n,_id:stage if n=='funnel_stages' else DATA.get(n)):
            with self.assertRaisesRegex(ValueError,'não pertence'):
                svc.make_plan(opportunity_id=OPP,content='Teste',actor_id=ACTOR)
    def test_10_bad_uuid(self):
        with self.assertRaises(ValueError):
            svc.make_plan(opportunity_id='not-uuid',content='Teste',actor_id=ACTOR)
    def test_11_bad_actor(self):
        with self.assertRaises(ValueError):
            svc.make_plan(opportunity_id=OPP,content='Teste',actor_id='abc')
    def test_12_unknown_template_token(self):
        with self.assertRaises(ValueError):
            svc.make_plan(opportunity_id=OPP,content='{{password}}',actor_id=ACTOR)
    def test_13_fail_closed_missing_count(self):
        self.db.counts['messages']=None
        with self.assertRaises(RuntimeError):svc.readiness()
    def test_14_restrict_table_names(self):
        with self.assertRaises(ValueError):svc._count(self.db,'customers')
    def test_15_requires_staging_env(self):
        with patch.dict(os.environ,{'APP_ENV':'production'}):
            with self.assertRaises(RuntimeError):svc.readiness()

if __name__ == '__main__':unittest.main()
