"""Testes offline sem acesso ao Supabase real ou a servicos externos."""
import os
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from uuid import uuid4

os.environ.update({
 'APP_ENV':'staging','DEMO_MODE':'false','SUPABASE_URL':'https://exampletest123.supabase.co',
 'VENDRA_STAGING_REF':'exampletest123','SUPABASE_ANON_KEY':'sb_publishable_some-mock-key-for-tests-abc',
 'SUPABASE_SERVICE_ROLE_KEY':'sb_secret_some-mock-key-for-tests-abc',
 'SECRET_KEY':'sample-25-characters-session-key','MAKE_WEBHOOK_SECRET':'','META_ACCESS_TOKEN':'','SMTP_HOST':''})

from fastapi.testclient import TestClient
from app.dependencies.auth import current_user
from app.services.auth_service import COOKIE_NAME,csrf_token_for_session
import app.services.staging_attendance_service as svc
import app.routers.staging_attendance as routes
import app.staging_h1_005b3 as module

ACTOR={'id':str(uuid4()),'full_name':'Admin Teste','access_level':'administrativo','role':'administrador','status':'active'}
CLIENT={'id':str(uuid4()),'name':'Cliente Ficticio','status':'active'}

class FakeBuilder:
 def __init__(self, db,name):self.db=db;self.name=name;self.filters=[];self.action='list';self.content=None;self.order_arg=None;self._limit=None
 def select(self,*a):self.action='list';return self
 def eq(self,k,v):self.filters.append((k,str(v)));return self
 def in_(self,k,vals):self.filters.append((k,{str(v) for v in vals}));return self
 def limit(self,x):self._limit=x;return self
 def order(self,k,desc=False):self.order_arg=(k,desc);return self
 def insert(self,data):self.action='insert';self.content=dict(data);return self
 def execute(self):
  if self.action=='insert':
   row=dict(self.content,id=str(uuid4()),created_at='2026-10-12T18:00:00+00:00')
   self.db.store[self.name].append(row)
   return SimpleNamespace(data=[dict(row)])
  rows=[dict(x) for x in self.db.store.get(self.name,[])]
  for k,v in self.filters:
   rows=[x for x in rows if (str(x.get(k))==v if isinstance(v,str) else str(x.get(k)) in v)]
  if self.order_arg:
   k,desc=self.order_arg; rows.sort(key=lambda r:str(r.get(k) or ''),reverse=desc)
  if self._limit is not None:rows=rows[:self._limit]
  return SimpleNamespace(data=rows)
class FakeDB:
 def __init__(self):self.store={'customers':[dict(CLIENT)],'profiles':[dict(ACTOR)],'tickets':[],'internal_notes':[], 'sales_funnels':[], 'funnel_stages':[], 'opportunities':[]}
 def table(self,name):return FakeBuilder(self,name)

class StagingH1005B3(unittest.TestCase):
 def setUp(self):
  self.db=FakeDB()
  self.patch=patch.object(svc,'get_admin_client',return_value=self.db)
  self.patch.start()
  module.app.dependency_overrides[current_user]=lambda:ACTOR
  self.middlepatch=patch.object(module,'get_session_user',return_value=ACTOR)
  self.middlepatch.start()
  self.customerpatch=patch.object(routes,'list_customers',side_effect=lambda *a,**kw:[dict(CLIENT)])
  self.customerpatch.start()
  self.client=TestClient(module.app)
  self.client.cookies.set(COOKIE_NAME,'staging-test-cookie')
  self.csrf=csrf_token_for_session('staging-test-cookie')
 def tearDown(self):
  self.client.close()
  self.patch.stop()
  self.middlepatch.stop()
  self.customerpatch.stop()
  module.app.dependency_overrides.clear()

 def test_routes_no_external_paths(self):
  all_routes=set(module.app.openapi().get('paths', {}))
  for prefix in ('/disparos','/webhooks','/integracoes','/configuracoes/ia'):
   self.assertFalse(any(x.startswith(prefix) for x in all_routes))
  self.assertIn('/atendimentos/novo',all_routes)
  self.assertIn('/oportunidades',all_routes)

 def test_health_is_staging(self):
  response=self.client.get('/health')
  self.assertEqual(response.status_code,200)
  self.assertFalse(response.json()['external_sends_enabled'])
  self.assertEqual(response.json()['stage'],'H1-005B3')

 def test_create_ticket_requires_csrf(self):
  response=self.client.post('/atendimentos/novo',data={'title':'Teste', 'customer_id':CLIENT['id'],'csrf_token':'invalido'},follow_redirects=False)
  self.assertEqual(response.status_code,403)
  self.assertEqual(len(self.db.store['tickets']),0)

 def test_create_list_and_detail_ticket(self):
  r=self.client.post('/atendimentos/novo',data={'title':'  Homologacao interna  ','customer_id':CLIENT['id'],'priority':'normal','csrf_token':self.csrf},follow_redirects=False)
  self.assertEqual(r.status_code,303,r.text)
  self.assertEqual(len(self.db.store['tickets']),1)
  ticket=self.db.store['tickets'][0]
  self.assertEqual(ticket['source'],'interno')
  self.assertEqual(ticket['assigned_user_id'],ACTOR['id'])
  self.assertEqual(self.client.get('/atendimentos').status_code,200)
  r=self.client.get('/atendimentos/'+ticket['id'])
  self.assertEqual(r.status_code,200)
  self.assertIn('Homologacao interna',r.text)

 def test_no_create_for_invalid_customer(self):
  r=self.client.post('/atendimentos/novo',data={'title':'Teste','customer_id':str(uuid4()),'csrf_token':self.csrf},follow_redirects=False)
  self.assertEqual(r.status_code,422)
  self.assertEqual(len(self.db.store['tickets']),0)

 def test_internal_note_no_external_message(self):
  ticket=svc.create_internal_ticket(actor_id=ACTOR['id'], title='Teste',customer_id=CLIENT['id'])
  r=self.client.post('/atendimentos/'+ticket['id']+'/notas',data={'content':'Nota sem enviar', 'csrf_token':self.csrf},follow_redirects=False)
  self.assertEqual(r.status_code,303)
  self.assertEqual(len(self.db.store['internal_notes']),1)
  self.assertEqual(self.db.store['internal_notes'][0]['content'],'Nota sem enviar')
  self.assertFalse(self.db.store.get('whatsapp_outbox'))
  self.assertFalse(self.db.store.get('messages'))
  self.assertIn('Nota sem enviar',self.client.get('/atendimentos/'+ticket['id']).text)

 def test_cannot_note_external_ticket(self):
  ticket=dict(id=str(uuid4()),customer_id=CLIENT['id'],status='novo',source='whatsapp')
  self.db.store['tickets'].append(ticket)
  r=self.client.post('/atendimentos/'+ticket['id']+'/notas',data={'content':'Nunca','csrf_token':self.csrf},follow_redirects=False)
  self.assertEqual(r.status_code,404)
  self.assertEqual(len(self.db.store['internal_notes']),0)

 def test_crm_is_read_only(self):
  r=self.client.get('/oportunidades')
  self.assertEqual(r.status_code,200)
  self.assertIn('CRM Comercial',r.text)
  paths=set(module.app.openapi().get('paths', {}))
  self.assertFalse(any('/oportunidades/' in r or r.endswith('/mover') for r in paths))
  self.assertEqual(self.client.post('/oportunidades/novo').status_code,404)

 def test_regular_user_not_allowed(self):
  module.app.dependency_overrides[current_user]=lambda:dict(ACTOR, access_level='comum',role='responsavel')
  self.assertEqual(self.client.get('/atendimentos').status_code,403)
  self.assertEqual(self.client.get('/oportunidades').status_code,403)

 def test_commercial_user_allowed(self):
  module.app.dependency_overrides[current_user]=lambda:dict(ACTOR, access_level='comercial',role='responsavel')
  self.assertEqual(self.client.get('/atendimentos').status_code,200)
  self.assertEqual(self.client.get('/oportunidades').status_code,200)

if __name__=='__main__':unittest.main()
