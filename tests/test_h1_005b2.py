import os
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ.update({
 'APP_ENV':'staging','DEMO_MODE':'false', 'SUPABASE_URL':'https://exampletest123.supabase.co',
 'VENDRA_STAGING_REF':'exampletest123','SUPABASE_ANON_KEY':'sb_publishable_some-mock-key-for-tests-abc','SUPABASE_SERVICE_ROLE_KEY':'sb_secret_some-mock-key-for-tests-abc',
 'SECRET_KEY':'sample-25-characters-session-key','MAKE_WEBHOOK_SECRET':'','META_ACCESS_TOKEN':'','SMTP_HOST':''})
from tools.staging_guard import check_staging
from fastapi.testclient import TestClient
from app.services.auth_service import csrf_token_for_session,COOKIE_NAME
from app.dependencies.auth import current_user
from app.staging_h1_005b2 import app

ACTOR={'id':'some-admin-id','role':'administrador','access_level':'administrativo','full_name':'Admin Teste','email':'test@example.local','status':'active'}
class H1Tests(unittest.TestCase):
 def test_guard_rejects_other_project(self):
    env=dict(os.environ, SUPABASE_URL='https://productionref.supabase.co')
    self.assertTrue(check_staging(env))
 def test_guard_rejects_make(self):
    env=dict(os.environ, MAKE_WEBHOOK_SECRET='real')
    self.assertTrue(check_staging(env))
 def test_routes_not_loaded(self):
    paths={r.path for r in app.routes}
    self.assertIn('/clientes',paths)
    self.assertIn('/usuarios',paths)
    self.assertNotIn('/disparos',paths)
    self.assertFalse(any(p.startswith('/webhooks') for p in paths))
 def test_login_unauthenticated(self):
    with TestClient(app) as client:
      self.assertEqual(client.get('/login').status_code,200)
      self.assertEqual(client.get('/clientes',follow_redirects=False).status_code,303)
 def test_access_levels(self):
    from app.services.access_service import allowed
    self.assertFalse(allowed({'access_level':'comum'},'clientes'))
    self.assertTrue(allowed({'access_level':'comercial'},'clientes'))
    self.assertFalse(allowed({'access_level':'comercial'},'usuarios'))
    self.assertTrue(allowed(ACTOR,'usuarios'))
 def test_auth_creates_hashed_session(self):
    from app.services import auth_service as service
    from types import SimpleNamespace
    class Builder:
      def __init__(self):self.kind=None;self.payload=None
      def select(self,*args):self.kind='select';return self
      def eq(self,*args):return self
      def limit(self,*args):return self
      def insert(self,row):self.kind='insert';self.payload=row;return self
      def execute(self):
        if self.kind=='select':return SimpleNamespace(data=[dict(ACTOR)])
        if self.kind=='insert':return SimpleNamespace(data=[self.payload])
    class FakeDB:
      def __init__(self):self.rows=[]
      def table(self,name):
        obj=Builder();self.rows.append((name,obj));return obj
    db=FakeDB()
    auth=SimpleNamespace(auth=SimpleNamespace(sign_in_with_password=lambda p:SimpleNamespace(user=SimpleNamespace(id=ACTOR['id']))))
    with patch.object(service,'get_auth_client',return_value=auth), patch.object(service,'get_admin_client',return_value=db):
      token,profile=service.authenticate('fake@test.local','not-the-real-password')
      self.assertEqual(profile['access_level'],'administrativo')
      self.assertTrue(len(token)>40)
      session=[b.payload for name,b in db.rows if name=='app_sessions'][0]
      self.assertNotEqual(session['token_hash'],token)
 def test_csrf_denied(self):
    app.dependency_overrides[current_user]=lambda: ACTOR
    try:
      with TestClient(app) as client:
        self.assertEqual(client.post('/clientes/novo',data={'name':'Cliente Fake','csrf_token':''},follow_redirects=False).status_code,403)
    finally:app.dependency_overrides.clear()
 def test_customer_fake_crud(self):
    # No network calls. Test routing, forms, and CSRF with an in-memory stand-in.
    import app.routers.staging_customers as router
    fake=[]
    def create(**kw):
      c=dict(kw,id='5b2-test-id',status='active');fake.append(c);return c
    def get(cid):return next((x for x in fake if x['id']==cid),None)
    def update(cid,**kw):
      c=get(cid)
      c.update(kw)
      return c
    app.dependency_overrides[current_user]=lambda:ACTOR
    try:
      with patch.object(router,'create_customer',side_effect=create),patch.object(router,'get_customer',side_effect=get),patch.object(router,'update_customer',side_effect=update),patch.object(router,'list_customers',side_effect=lambda q:fake),patch.object(router,'record_audit'),patch('app.staging_h1_005b2.get_session_user',return_value=ACTOR):
        with TestClient(app) as client:
          session='test-session-token'
          client.cookies.set(COOKIE_NAME,session)
          csrf=csrf_token_for_session(session)
          self.assertEqual(client.get('/clientes/novo').status_code,200)
          res=client.post('/clientes/novo',data={'name':'Teste Fake', 'phone':'55999999999','csrf_token':csrf},follow_redirects=False)
          self.assertEqual(res.status_code,303)
          self.assertEqual(client.get('/clientes/5b2-test-id').status_code,200)
          self.assertEqual(client.get('/clientes/5b2-test-id/editar').status_code,200)
          res=client.post('/clientes/5b2-test-id/editar',data={'name':'Novo nome','csrf_token':csrf},follow_redirects=False)
          self.assertEqual(res.status_code,303)
          self.assertEqual(fake[0]['name'],'Novo nome')
    finally: app.dependency_overrides.clear()

if __name__=='__main__':unittest.main()
