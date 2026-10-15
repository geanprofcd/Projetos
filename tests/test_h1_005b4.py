"""H1-005B4 testes offline: nao usam credenciais ou Supabase real."""
import os,unittest
from unittest.mock import patch
from uuid import uuid4
from pathlib import Path
os.environ.update({'APP_ENV':'staging','DEMO_MODE':'false','SUPABASE_URL':'https://exampletest123.supabase.co',
 'VENDRA_STAGING_REF':'exampletest123','SUPABASE_ANON_KEY':'sb_publishable_some-mock-key-for-tests-abc',
 'SUPABASE_SERVICE_ROLE_KEY':'sb_secret_some-mock-key-for-tests-abc','SECRET_KEY':'sample-25-characters-session-key',
 'META_ACCESS_TOKEN':'','MAKE_WEBHOOK_SECRET':'','SMTP_HOST':''})
from fastapi.testclient import TestClient
from app.dependencies.auth import current_user
from app.services.auth_service import COOKIE_NAME,csrf_token_for_session
from app.services import staging_crm_service as svc
from app.routers import staging_crm
import app.staging_h1_005b4 as module

ACTOR={'id':str(uuid4()),'full_name':'Admin Teste','access_level':'administrativo','status':'active','role':'administrador'}
TICKET=str(uuid4());STAGE=str(uuid4());OPP=str(uuid4());FUNNEL=str(uuid4())
FUNNELS=[{'id':FUNNEL,'name':'Funil Comercial','is_active':True,
         'stages':[{'id':STAGE,'funnel_id':FUNNEL,'name':'Novo Lead','is_active':True,'position':1}]}]
OPPS=[{'id':OPP,'title':'Oportunidade Teste','customer_name':'Cliente Teste',
       'funnel_id':FUNNEL,'stage_id':STAGE,'funnel_name':'Funil Comercial','stage_name':'Novo Lead',
       'lock_version':1,'status':'open','archived_at':None}]
TICKETS=[{'id':TICKET,'title':'Interno','customer_name':'Cliente Teste'}]

class H1005B4(unittest.TestCase):
 def setUp(self):
  module.app.dependency_overrides[current_user]=lambda: ACTOR
  self.ses=patch.object(module,'get_session_user',return_value=ACTOR);self.ses.start()
  self.data=patch.object(svc,'list_crm',return_value=(FUNNELS,OPPS,TICKETS));self.data.start()
  self.client=TestClient(module.app)
  self.client.cookies.set(COOKIE_NAME,'cookie-test')
  self.csrf=csrf_token_for_session('cookie-test')
 def tearDown(self):
  self.client.close();self.data.stop();self.ses.stop();module.app.dependency_overrides.clear()
 def test_health_and_external_routes(self):
  self.assertEqual(self.client.get('/health').json()['stage'],'H1-005B4')
  paths=set(module.app.openapi().get('paths',{}))
  self.assertIn('/oportunidades/{opportunity_id}/mover', paths)
  self.assertFalse(any(p.startswith(('/webhooks','/disparos','/integracoes')) for p in paths))
 def test_legacy_ticket_paths(self):
  paths=set(module.app.openapi().get('paths',{}))
  self.assertIn('/atendimentos/{ticket_id}/notas',paths)
  self.assertIn('/atendimentos/novo',paths)
 def test_crm_render(self):
  r=self.client.get('/oportunidades')
  self.assertEqual(r.status_code,200,r.text[:700])
  self.assertIn('Nova oportunidade',r.text)
 def test_csrf_prevents_create(self):
  with patch.object(svc,'create_opportunity') as cr:
   r=self.client.post('/oportunidades/novo',data={'ticket_id':TICKET,'stage_id':STAGE,'title':'Oportunidade','csrf_token':'wrong'})
   self.assertEqual(r.status_code,403);cr.assert_not_called()
 def test_funnel_create_admin(self):
  with patch.object(svc,'create_funnel',return_value=FUNNEL) as cf:
   r=self.client.post('/oportunidades/funis/novo',data={'name':'Funil','stages':'Novo Lead\nQualificação','csrf_token':self.csrf},follow_redirects=False)
   self.assertEqual(r.status_code,303,r.text);cf.assert_called_once()
 def test_funnel_denied_commercial(self):
  module.app.dependency_overrides[current_user]=lambda:dict(ACTOR,access_level='comercial',role='responsavel')
  with patch.object(svc,'create_funnel') as cf:
   r=self.client.post('/oportunidades/funis/novo',data={'name':'Funil','stages':'Lead\nQualificação','csrf_token':self.csrf})
   self.assertEqual(r.status_code,403);cf.assert_not_called()
 def test_commercial_can_create_opportunity(self):
  module.app.dependency_overrides[current_user]=lambda:dict(ACTOR,access_level='comercial',role='responsavel')
  with patch.object(svc,'create_opportunity',return_value=OPP) as cf:
   r=self.client.post('/oportunidades/novo',data={'ticket_id':TICKET,'stage_id':STAGE,'title':'Teste','csrf_token':self.csrf},follow_redirects=False)
   self.assertEqual(r.status_code,303);cf.assert_called_once()
 def test_comum_denied_create(self):
  module.app.dependency_overrides[current_user]=lambda:dict(ACTOR,access_level='comum',role='responsavel')
  with patch.object(svc,'create_opportunity') as cr:
   r=self.client.post('/oportunidades/novo',data={'ticket_id':TICKET,'stage_id':STAGE,'title':'Teste','csrf_token':self.csrf})
   self.assertEqual(r.status_code,403);cr.assert_not_called()
 def test_move_calls_rpc_with_version(self):
  with patch.object(svc,'move_opportunity',return_value=2) as mo:
   r=self.client.post(f'/oportunidades/{OPP}/mover',data={'stage_id':STAGE,'lock_version':'1','csrf_token':self.csrf},follow_redirects=False)
   self.assertEqual(r.status_code,303);self.assertEqual(mo.call_args.kwargs['lock_version'],1)
 def test_reject_bad_form_before_rpc(self):
  with patch.object(svc,'get_admin_client') as db:
   with self.assertRaises(ValueError):svc.create_opportunity(ticket_id='bad',stage_id=STAGE,title='X',actor_id=ACTOR['id'])
   db.assert_not_called()
 def test_distinct_stage_validation(self):
  with patch.object(svc,'get_admin_client') as db:
   with self.assertRaises(ValueError):svc.create_funnel(name='Funil',stages_text='Lead\nlead',actor_id=ACTOR['id'])
   db.assert_not_called()
 def test_rpc_name_arguments(self):
  class Resp: data=OPP
  class RPC:
   def execute(self):return Resp()
  class DB:
   def __init__(self):self.name=None;self.args=None
   def rpc(self,n,a):self.name=n;self.args=a;return RPC()
  db=DB()
  with patch.object(svc,'get_admin_client',return_value=db):
   svc.create_opportunity(ticket_id=TICKET,stage_id=STAGE,title='  ABC  ',actor_id=ACTOR['id'])
  self.assertEqual(db.name,'vendra_staging_create_opportunity')
  self.assertEqual(db.args['p_title'],'ABC')
 def test_sql_has_transaction_and_acl(self):
  p=Path(__file__).resolve().parents[1]/'sql'/'01_APLICAR_RPC_H1_005B4_STAGING.sql'
  s=p.read_text()
  self.assertIn('BEGIN;',s);self.assertIn('COMMIT;',s)
  self.assertIn('FOR UPDATE',s);self.assertIn('lock_version=lock_version+1',s)
  self.assertIn('REVOKE ALL ON FUNCTION',s)

if __name__=='__main__':unittest.main()
