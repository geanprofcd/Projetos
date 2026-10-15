"""H1-005B5: testes offline. Nunca chamam API real Meta/Make/Supabase."""
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

os.environ.update({
    'APP_ENV': 'staging', 'DEMO_MODE': 'false',
    'SUPABASE_URL': 'https://exampletest123.supabase.co',
    'VENDRA_STAGING_REF': 'exampletest123',
    'SUPABASE_ANON_KEY': 'sb_publishable_some-mock-key-for-tests-abc',
    'SUPABASE_SERVICE_ROLE_KEY': 'sb_secret_some-mock-key-for-tests-abc',
    'SECRET_KEY': 'sample-25-characters-session-key',
    'META_ACCESS_TOKEN': '', 'MAKE_WEBHOOK_SECRET': '', 'SMTP_HOST': '',
})

from fastapi.testclient import TestClient
from app.dependencies.auth import current_user
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session
from app.services import staging_dispatch_preview_service as svc
import app.staging_h1_005b5 as module

ACTOR={'id':str(uuid4()),'full_name':'Administrador de Teste',
       'access_level':'administrativo','status':'active','role':'administrador'}
OPP_ID=str(uuid4()); CUSTOMER_ID=str(uuid4()); FUNNEL_ID=str(uuid4());STAGE_ID=str(uuid4())
CHOICES=[{'id':OPP_ID,'title':'Oportunidade Teste','customer_name':'Cliente Fictício'}]
PREVIEW={'opportunity_title':'Oportunidade Teste','customer_name':'Cliente Fictício',
         'phone_masked':'•••• 9999','message':'Olá, Cliente Fictício!',
         'fingerprint':'abcde123456789ab','sent':False,'queued':False}

class Response:
    def __init__(self, data):self.data=data

class FakeAuditTable:
    def __init__(self, owner):self.owner=owner
    def insert(self, value):self.owner.records.append(value);return self
    def execute(self):return Response([{'id':str(uuid4())}])

class FakeDB:
    def __init__(self):self.records=[];self.tables=[]
    def table(self,name):
        self.tables.append(name)
        if name!='audit_log':raise AssertionError('Nenhuma tabela de envio pode ser escrita: '+name)
        return FakeAuditTable(self)


def fake_records(table,identifier):
    mapping = {
        'opportunities': {'id':OPP_ID,'title':'Oportunidade Teste',
                          'status':'open','archived_at':None,'customer_id':CUSTOMER_ID,
                          'funnel_id':FUNNEL_ID,'stage_id':STAGE_ID},
        'customers': {'id':CUSTOMER_ID,'name':'Cliente Fictício','status':'active',
                      'phone_normalized':'5511999999999','company_name':'Empresa Demo'},
        'sales_funnels': {'id':FUNNEL_ID,'name':'Funil Teste'},
        'funnel_stages': {'id':STAGE_ID,'funnel_id':FUNNEL_ID,'name':'Qualificação'},
    }
    return mapping.get(table)


class StagingH1005B5(unittest.TestCase):
    def setUp(self):
        module.app.dependency_overrides[current_user]=lambda: ACTOR
        self.session=patch.object(module,'get_session_user',return_value=ACTOR)
        self.session.start()
        self.available=patch.object(svc,'list_dispatch_candidates',return_value=CHOICES)
        self.available.start()
        self.client=TestClient(module.app)
        self.client.cookies.set(COOKIE_NAME,'test-cookie-h1-005b5')
        self.csrf=csrf_token_for_session('test-cookie-h1-005b5')
    def tearDown(self):
        self.client.close(); self.available.stop();self.session.stop()
        module.app.dependency_overrides.clear()

    def test_health_and_safe_route_surface(self):
        payload=self.client.get('/health').json()
        self.assertEqual(payload['stage'],'H1-005B5')
        self.assertFalse(payload['external_sends_enabled'])
        self.assertTrue(payload['dispatch_preview_only'])
        paths=set(module.app.openapi().get('paths', {}))
        self.assertIn('/disparos',paths)
        self.assertIn('/disparos/simular',paths)
        self.assertFalse(any(p.startswith(('/webhooks','/integracoes','/api/whatsapp')) for p in paths))

    def test_get_preview_ui(self):
        r=self.client.get('/disparos')
        self.assertEqual(r.status_code,200,r.text[:400])
        self.assertIn('NÃO envia mensagens',r.text)
        self.assertIn('Oportunidade Teste',r.text)

    def test_csrf_rejected_before_simulation(self):
        with patch.object(svc,'simulate_dispatch') as simulator:
            r=self.client.post('/disparos/simular',data={'opportunity_id':OPP_ID,
                        'content':'Olá','csrf_token':'token-incorreto'})
            self.assertEqual(r.status_code,403)
            simulator.assert_not_called()

    def test_preview_calls_service_and_never_sends(self):
        with patch.object(svc,'simulate_dispatch',return_value=PREVIEW) as simulator:
            r=self.client.post('/disparos/simular',data={'opportunity_id':OPP_ID,
                'content':'Olá {{nome}}','csrf_token':self.csrf})
            self.assertEqual(r.status_code,200,r.text[:600])
            self.assertIn('Sem envio externo',r.text)
            simulator.assert_called_once()

    def test_comum_cannot_simulate(self):
        module.app.dependency_overrides[current_user]=lambda: dict(ACTOR,access_level='comum',role='responsavel')
        with patch.object(svc,'simulate_dispatch') as simulator:
            r=self.client.post('/disparos/simular',data={'opportunity_id':OPP_ID,
                'content':'Olá','csrf_token':self.csrf})
            self.assertEqual(r.status_code,403)
            simulator.assert_not_called()

    def test_render_supported_variables(self):
        txt=svc._render('Olá {{nome}} da {{empresa}}!',{'name':'Pessoa Teste','company_name':'Empresa X'})
        self.assertEqual(txt,'Olá Pessoa Teste da Empresa X!')

    def test_render_rejects_unapproved_variables(self):
        with self.assertRaises(ValueError):svc._render('{{instrucoes_secretas}}',{})
        with self.assertRaises(ValueError):svc._render('{{nome',{})

    def test_success_writes_audit_only(self):
        db=FakeDB()
        with patch.object(svc,'_get',side_effect=fake_records),patch.object(svc,'get_admin_client',return_value=db):
            result=svc.simulate_dispatch(opportunity_id=OPP_ID,content='Olá, {{nome}}!',actor_id=ACTOR['id'])
        self.assertEqual(db.tables,['audit_log'])
        self.assertEqual(len(db.records),1)
        entry=db.records[0]
        self.assertEqual(entry['action'],'simulated')
        self.assertNotIn('phone',str(entry))
        self.assertNotIn('Cliente Fictício',str(entry))
        self.assertFalse(result['sent'])
        self.assertFalse(result['queued'])
        self.assertIn('Cliente Fictício',result['message'])

    def test_invalid_phone_fails_before_audit(self):
        db=FakeDB()
        def record(table,identifier):
            r=fake_records(table,identifier)
            if table=='customers':return dict(r,phone_normalized='1234')
            return r
        with patch.object(svc,'_get',side_effect=record),patch.object(svc,'get_admin_client',return_value=db):
            with self.assertRaises(ValueError):
                svc.simulate_dispatch(opportunity_id=OPP_ID,content='Teste',actor_id=ACTOR['id'])
        self.assertEqual(db.tables,[])

    def test_closed_opportunity_fails_before_audit(self):
        db=FakeDB()
        def record(table,identifier):
            r=fake_records(table,identifier)
            if table=='opportunities':return dict(r,status='won')
            return r
        with patch.object(svc,'_get',side_effect=record),patch.object(svc,'get_admin_client',return_value=db):
            with self.assertRaises(ValueError):
                svc.simulate_dispatch(opportunity_id=OPP_ID,content='Teste',actor_id=ACTOR['id'])
        self.assertEqual(db.tables,[])

if __name__=='__main__':unittest.main()
