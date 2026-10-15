"""H1-005B6: testes offline, sem Meta, Make ou chamadas reais ao Supabase."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from pathlib import Path

os.environ.update({
    'APP_ENV':'staging','DEMO_MODE':'false',
    'SUPABASE_URL':'https://exampletest123.supabase.co',
    'VENDRA_STAGING_REF':'exampletest123',
    'SUPABASE_ANON_KEY':'sb_publishable_some-mock-key-for-tests-abc',
    'SUPABASE_SERVICE_ROLE_KEY':'sb_secret_some-mock-key-for-tests-abc',
    'SECRET_KEY':'sample-25-characters-session-key',
    'META_ACCESS_TOKEN':'','MAKE_WEBHOOK_SECRET':'','SMTP_HOST':''})

from fastapi.testclient import TestClient
from app.dependencies.auth import current_user
from app.services.auth_service import COOKIE_NAME,csrf_token_for_session
from app.services import staging_dispatch_lifecycle_service as service
from app.services import staging_dispatch_preview_service as preview
import app.staging_h1_005b6 as module

ACTOR={'id':str(uuid4()),'full_name':'Admin Teste','access_level':'administrativo',
       'role':'administrador','status':'active'}
OPP=str(uuid4()); CUST=str(uuid4()); FUN=str(uuid4()); STAGE=str(uuid4()); SIM=str(uuid4())
CHOICES=[{'id':OPP,'title':'Oportunidade Mock','customer_name':'Cliente Mock'}]
SIMULATIONS=[{'id':SIM,'opportunity_id':OPP,'title':'Oportunidade Mock',
              'state':'prepared','state_label':'Preparado','attempt_count':0,
              'lock_version':1}]
RECORDS={
 'opportunities':{'id':OPP,'customer_id':CUST,'funnel_id':FUN,'stage_id':STAGE,
                  'title':'Oportunidade Mock','status':'open','archived_at':None},
 'customers':{'id':CUST,'name':'Cliente Mock','company_name':'Empresa Mock',
              'phone_normalized':'5511999999999','status':'active'},
 'sales_funnels':{'id':FUN,'name':'Funil Mock'},
 'funnel_stages':{'id':STAGE,'funnel_id':FUN,'name':'Qualificação'},
}

class FakeRpcCall:
    def __init__(self,db,method,args):self.db=db;self.method=method;self.args=args
    def execute(self):return SimpleNamespace(data=(SIM if self.method.endswith('prepare_dispatch') else 2))

class FakeDb:
    def __init__(self):self.calls=[]
    def rpc(self,method,args):
        self.calls.append((method,args))
        if method not in {'vendra_staging_prepare_dispatch',
                          'vendra_staging_change_dispatch_simulation'}:
            raise AssertionError('RPC externa proibida: '+method)
        return FakeRpcCall(self,method,args)
    def table(self,name):raise AssertionError('Escrita/leitura direta inesperada: '+name)

class H1005B6Service(unittest.TestCase):
    def test_prepare_uses_staging_rpc_only(self):
        db=FakeDb()
        with patch.object(preview,'_get',side_effect=lambda name,_id:RECORDS.get(name)), \
             patch.object(service,'get_admin_client',return_value=db):
            result=service.prepare_simulation(opportunity_id=OPP,
                                content='Olá, {{nome}}!',actor_id=ACTOR['id'])
        self.assertEqual(len(db.calls),1)
        method,args=db.calls[0]
        self.assertEqual(method,'vendra_staging_prepare_dispatch')
        self.assertEqual(args['p_opportunity_id'],OPP)
        self.assertEqual(len(args['p_fingerprint']),64)
        self.assertFalse(result['sent']);self.assertFalse(result['queued'])
        self.assertIn('Cliente Mock',result['message'])
        self.assertNotIn('Cliente Mock',str(args))
        self.assertNotIn('5511999999999',str(args))

    def test_invalid_phone_is_blocked_before_rpc(self):
        db=FakeDb()
        def source(name,_id):
            row=RECORDS.get(name)
            if name=='customers':return {**row,'phone_normalized':'123'}
            return row
        with patch.object(preview,'_get',side_effect=source), \
             patch.object(service,'get_admin_client',return_value=db):
            with self.assertRaises(ValueError):
                service.prepare_simulation(opportunity_id=OPP,content='Teste',actor_id=ACTOR['id'])
        self.assertFalse(db.calls)

    def test_closed_opportunity_rejected(self):
        db=FakeDb()
        def source(name,_id):
            row=RECORDS.get(name)
            return {**row,'status':'won'} if name=='opportunities' else row
        with patch.object(preview,'_get',side_effect=source), \
             patch.object(service,'get_admin_client',return_value=db):
            with self.assertRaises(ValueError):
                service.prepare_simulation(opportunity_id=OPP,content='Teste',actor_id=ACTOR['id'])
        self.assertFalse(db.calls)

    def test_state_transition_calls_staging_rpc_only(self):
        db=FakeDb()
        with patch.object(service,'get_admin_client',return_value=db):
            v=service.change_state(simulation_id=SIM,action='simulate_failure',
                                   lock_version=1,actor_id=ACTOR['id'])
        self.assertEqual(v,2)
        self.assertEqual(db.calls[0][0],'vendra_staging_change_dispatch_simulation')
        self.assertEqual(db.calls[0][1]['p_action'],'simulate_failure')

    def test_invalid_action_never_calls_rpc(self):
        with patch.object(service,'get_admin_client') as db:
            with self.assertRaises(ValueError):
                service.change_state(simulation_id=SIM,action='send_whatsapp',
                                     lock_version=1,actor_id=ACTOR['id'])
            db.assert_not_called()

    def test_invalid_version_never_calls_rpc(self):
        with patch.object(service,'get_admin_client') as db:
            with self.assertRaises(ValueError):
                service.change_state(simulation_id=SIM,action='simulate_success',
                                     lock_version=0,actor_id=ACTOR['id'])
            db.assert_not_called()

class H1005B6Web(unittest.TestCase):
    def setUp(self):
        module.app.dependency_overrides[current_user]=lambda:ACTOR
        self.session=patch.object(module,'get_session_user',return_value=ACTOR)
        self.session.start()
        self.p_candidates=patch.object(preview,'list_dispatch_candidates',return_value=CHOICES)
        self.p_simulations=patch.object(service,'list_simulations',return_value=SIMULATIONS)
        self.p_candidates.start();self.p_simulations.start()
        self.client=TestClient(module.app)
        self.client.cookies.set(COOKIE_NAME,'cookie-test-005b6')
        self.csrf=csrf_token_for_session('cookie-test-005b6')
    def tearDown(self):
        self.client.close();self.session.stop()
        self.p_candidates.stop();self.p_simulations.stop()
        module.app.dependency_overrides.clear()

    def test_health_never_external(self):
        data=self.client.get('/health').json()
        self.assertEqual(data['stage'],'H1-005B6')
        self.assertFalse(data['external_sends_enabled'])
        self.assertTrue(data['simulation_only'])
        paths=set(module.app.openapi().get('paths',{}))
        self.assertIn('/disparos/simulacoes',paths)
        self.assertFalse(any(p.startswith(('/webhooks','/integracoes','/api/whatsapp')) for p in paths))

    def test_page_has_safe_labels(self):
        r=self.client.get('/disparos/simulacoes')
        self.assertEqual(r.status_code,200,r.text[:400])
        self.assertIn('Nenhum WhatsApp é enviado',r.text)
        self.assertIn('Oportunidade Mock',r.text)

    def test_create_requires_csrf(self):
        with patch.object(service,'prepare_simulation') as fn:
            r=self.client.post('/disparos/simulacoes/preparar',data={
                'opportunity_id':OPP,'content':'Olá','csrf_token':'errado'})
            self.assertEqual(r.status_code,403);fn.assert_not_called()

    def test_prepare_success(self):
        out={'id':SIM,'title':'Oportunidade Mock','phone_masked':'•••• 9999',
             'message':'Olá, Cliente Mock!','sent':False,'queued':False}
        with patch.object(service,'prepare_simulation',return_value=out) as fn:
            r=self.client.post('/disparos/simulacoes/preparar',data={
                'opportunity_id':OPP,'content':'Olá {{nome}}','csrf_token':self.csrf})
            self.assertEqual(r.status_code,200,r.text[:400]);fn.assert_called_once()
            self.assertIn('Nenhum envio externo',r.text)

    def test_change_requires_csrf(self):
        with patch.object(service,'change_state') as fn:
            r=self.client.post('/disparos/simulacoes/'+SIM+'/estado',data={
                'action':'simulate_success','lock_version':'1','csrf_token':'errado'})
            self.assertEqual(r.status_code,403);fn.assert_not_called()

    def test_change_valid_action(self):
        with patch.object(service,'change_state',return_value=2) as fn:
            r=self.client.post('/disparos/simulacoes/'+SIM+'/estado',data={
                'action':'simulate_success','lock_version':'1','csrf_token':self.csrf},
                follow_redirects=False)
            self.assertEqual(r.status_code,303)
            self.assertEqual(r.headers['location'],'/disparos/simulacoes')
            fn.assert_called_once()

    def test_common_user_cannot_access(self):
        module.app.dependency_overrides[current_user]=lambda:{**ACTOR,'access_level':'comum','role':'comum'}
        r=self.client.get('/disparos/simulacoes')
        self.assertEqual(r.status_code,403)

if __name__=='__main__':unittest.main()
