"""H1-005B9: UX fail-closed tests, sem banco ou requisicoes externas."""
from __future__ import annotations
import os
import sys
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch
from types import ModuleType
from uuid import uuid4
os.environ.update({'APP_ENV':'staging','DEMO_MODE':'false','VENDRA_STAGING_REF':'exampletest123',
 'SUPABASE_URL':'https://exampletest123.supabase.co','SUPABASE_ANON_KEY':'sb_publishable_mock_unit_test_12345',
 'SUPABASE_SERVICE_ROLE_KEY':'sb_secret_mock_unit_test_123456','SECRET_KEY':'session-secret-test-very-long',
 'META_ACCESS_TOKEN':'','MAKE_WEBHOOK_SECRET':'','SMTP_HOST':''})
if importlib.util.find_spec('app.services.local_credentials_service') is None:
 _stub=ModuleType('app.services.local_credentials_service')
 _stub.demo_admin_credentials=lambda: {'email':'nobody@example.test','password':'none','full_name':'Test'}
 sys.modules['app.services.local_credentials_service']=_stub
from app.routers import staging_delivery_preflight as r7
from app.routers import staging_transport_contract as r8
from app.services import staging_delivery_preflight_service as svc
BASE=Path(__file__).resolve().parents[1]
USER={'id':str(uuid4()),'access_level':'administrativo'}
PLAN={'opportunity_title':'Teste','customer_name':'Teste','phone_masked':'•••• 6094',
 'rendered_message':'Ola <script>alert(1)</script>','idempotency_reference':'a'*16,
 'destination':'BLOQUEADO','delivery_state':'not_queued'}
class RequestStub:
 def __init__(self,accept='application/json',query=''):
  self.headers={'accept':accept};self.cookies={'fake':'abc'};self.query_params={'resultado':query}

class H1005B9(unittest.TestCase):
 def submit(self,accept='application/json',exception=None):
  req=RequestStub(accept)
  with patch.object(r7,'require_access'),patch.object(r7,'verify_csrf_token',return_value=True),       patch.object(svc,'readiness',return_value={'real_queue_clean':True}),       patch.object(svc,'make_plan',side_effect=exception) if exception else patch.object(svc,'make_plan',return_value=PLAN):
   return r7.plan(req,opportunity_id=str(uuid4()),content='ola',csrf_token='valid',user=USER)
 def test_01_json_response_success(self):
  response=self.submit();self.assertEqual(response.status_code,200)
  self.assertIn(b'"ok":true',response.body)
 def test_02_result_has_no_send_fields(self):
  response=self.submit();self.assertNotIn(b'"queued":true',response.body.lower());self.assertNotIn(b'"sent":true',response.body.lower());self.assertNotIn(b'provider_message_id',response.body)
 def test_03_json_not_cached(self):
  response=self.submit();self.assertEqual(response.headers['cache-control'],'no-store')
 def test_04_fallback_is_303_prg(self):
  response=self.submit('text/html');self.assertEqual(response.status_code,303);self.assertEqual(response.headers['location'],'/disparos/prontidao?resultado=validado')
 def test_05_fallback_url_no_sensitive_data(self):
  response=self.submit('text/html');self.assertNotIn('6094',response.headers['location']);self.assertNotIn('Ola',response.headers['location'])
 def test_06_bad_input_json_422(self):
  response=self.submit(exception=ValueError('Oportunidade invalida'));self.assertEqual(response.status_code,422)
 def test_07_bad_input_no_post_reload(self):
  response=self.submit('text/html',exception=ValueError('Indisponivel'));self.assertEqual(response.status_code,303)
 def test_08_unavailable_service_fail_closed(self):
  response=self.submit(exception=RuntimeError('sensitive internal error'));self.assertEqual(response.status_code,503);self.assertNotIn(b'sensitive internal error',response.body)
 def test_09_csrf_fail_closed(self):
  from fastapi import HTTPException
  with patch.object(r7,'require_access'),patch.object(r7,'verify_csrf_token',return_value=False):
   with self.assertRaises(HTTPException) as cm:
    r7.plan(RequestStub(),opportunity_id=str(uuid4()),content='ola',csrf_token='invalid',user=USER)
  self.assertEqual(cm.exception.status_code,403)
 def test_10_no_script_in_html_preview(self):
  html=(BASE/'app/templates/staging/delivery_preflight.html').read_text(encoding='utf-8')
  self.assertIn('staging-h1-005b9.js',html);self.assertIn('vendra-b9-result',html)
 def test_11_client_render_is_text_content_only(self):
  js=(BASE/'app/static/js/staging-h1-005b9.js').read_text(encoding='utf-8')
  self.assertIn('.textContent',js);self.assertNotIn('.innerHTML',js)
 def test_12_no_browser_storage(self):
  js=(BASE/'app/static/js/staging-h1-005b9.js').read_text(encoding='utf-8')
  self.assertNotIn('sessionStorage',js);self.assertNotIn('localStorage',js)
 def test_13_render_not_serialized_to_url(self):
  route=(BASE/'app/routers/staging_delivery_preflight.py').read_text(encoding='utf-8')
  self.assertIn('resultado=validado',route);self.assertNotIn('quote(content)',route)
 def test_14_contract_prg_kept(self):
  route=(BASE/'app/routers/staging_transport_contract.py').read_text(encoding='utf-8')
  self.assertIn('status_code=303',route)
 def test_15_old_routes_still_included(self):
  runtime=(BASE/'app/staging_h1_005b9.py').read_text(encoding='utf-8')
  self.assertIn('staging_delivery_preflight.router',runtime)
  self.assertIn('staging_transport_contract.router',runtime)
 def test_16_start_only_on_port_8011(self):
  start=(BASE/'tools/staging_start.py').read_text(encoding='utf-8')
  self.assertIn('staging_h1_005b9:app',start);self.assertIn('port=8011',start)
 def test_17_response_security_headers(self):
  runtime=(BASE/'app/staging_h1_005b9.py').read_text(encoding='utf-8')
  self.assertIn('no-store',runtime);self.assertIn('no-referrer',runtime)
 def test_18_staging_guard_not_removed(self):
  runtime=(BASE/'app/staging_h1_005b9.py').read_text(encoding='utf-8')
  self.assertIn('assert_staging()',runtime);self.assertNotIn('app.main:app',runtime)
 def test_19_b8_feedback_is_generic(self):
  route=(BASE/'app/routers/staging_transport_contract.py').read_text(encoding='utf-8')
  self.assertIn('resultado=preparado',route);self.assertIn('resultado=alterado',route)
 def test_20_route_does_not_import_external_transport(self):
  route=(BASE/'app/routers/staging_delivery_preflight.py').read_text(encoding='utf-8')
  self.assertNotIn('claim_whatsapp_outbox',route);self.assertNotIn('send_whatsapp',route)
if __name__=='__main__':unittest.main()
