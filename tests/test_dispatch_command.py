from __future__ import annotations

from contextlib import ExitStack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4
from urllib.error import URLError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.services import dispatch_command_service as service


class CommandTests(TestCase):
    def setUp(self):
        self.user = {'id':str(uuid4()),'status':'active','access_level':'comercial'}
        self.nonce = str(uuid4())
        self.row = {'id':str(uuid4()),'name':'Teste','phone':'551188765432',
                    'template_key':'continuar_atendimento_vendra','created':True,'status':'pending'}
        self.settings = SimpleNamespace(demo_mode=False, app_env='staging', dispatch_transport_enabled=True,
            dispatch_transport_url='https://hook.us2.make.com/'+'a'*32,
            dispatch_transport_secret='s'*48, dispatch_allowed_phones='5511988765432')
        self.db = Mock()
        self.db.rpc.return_value.execute.return_value.data = self.row
        self.db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        self.opener = MagicMock()
        self.opener.open.return_value.__enter__.return_value.status = 200
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(service,'get_settings',return_value=self.settings))
        self.stack.enter_context(patch.object(service,'get_admin_client',return_value=self.db))
        self.stack.enter_context(patch.object(service,'_new_lead_destination',return_value=(str(uuid4()),str(uuid4()))))
        self.stack.enter_context(patch.object(service.urllib.request,'build_opener',return_value=self.opener))

    def request(self, **changes):
        args={'user':self.user,'name':'Teste','phone':'+55 (11) 98876-5432','request_id':self.nonce}
        args.update(changes)
        return service.request_dispatch(**args)

    def test_valid_form_uses_atomic_command_and_same_dispatch_id(self):
        import json
        result=self.request()
        args=self.db.rpc.call_args.args[1]
        self.assertEqual(args['p_actor_id'],self.user['id'])
        self.assertEqual(args['p_request_id'],self.nonce)
        self.assertEqual(args['p_phone'],'551188765432')
        payload=json.loads(self.opener.open.call_args.args[0].data)
        self.assertEqual(payload['dispatch_id'],self.row['id'])
        self.assertTrue(result['transport_confirmed'])
        self.assertEqual(self.opener.open.call_count,1)

    def test_disabled_transport_creates_nothing(self):
        self.settings.dispatch_transport_enabled=False
        with self.assertRaises(ValueError):self.request()
        self.db.rpc.assert_not_called();self.opener.open.assert_not_called()

    def test_demo_mode_never_uses_real_command(self):
        self.settings.demo_mode=True
        with self.assertRaises(ValueError):self.request()
        self.db.rpc.assert_not_called()

    def test_common_and_inactive_users_cannot_create_command(self):
        for change in ({'access_level':'comum'},{'status':'inactive'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.request(user={**self.user,**change})
        self.db.rpc.assert_not_called()

    def test_malformed_nonce_or_phone_never_reaches_database(self):
        for change in ({'request_id':'invalid'},{'phone':'123'},{'name':' '*3},{'phone':'+1 202 555 0190'}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.request(**change)
        self.db.rpc.assert_not_called()

    def test_staging_target_must_be_allowlisted(self):
        for allowed in ('','5511999999999'):
            self.settings.dispatch_allowed_phones=allowed
            with self.assertRaises(ValueError):self.request()
        self.db.rpc.assert_not_called()

    def test_untrusted_url_and_short_secret_block_before_database(self):
        good=self.settings.dispatch_transport_url
        for url in ('http://hook.us2.make.com/'+'a'*32, 'https://example.com/'+'a'*32,good+'?token=abc'):
            self.settings.dispatch_transport_url=url
            with self.assertRaises(ValueError):self.request()
        self.settings.dispatch_transport_url=good;self.settings.dispatch_transport_secret='short'
        with self.assertRaises(ValueError):self.request()
        self.db.rpc.assert_not_called()

    def test_reserved_duplicate_does_not_call_transport(self):
        self.row.update(created=False,status='submitted')
        result=self.request()
        self.assertEqual(result['id'],self.row['id'])
        self.opener.open.assert_not_called()

    def test_timeout_keeps_same_request_and_does_not_retry(self):
        self.opener.open.side_effect=URLError('timeout: private detail')
        result=self.request()
        self.assertFalse(result['transport_confirmed'])
        self.assertEqual(result['id'],self.row['id'])
        self.assertEqual(self.db.rpc.call_count,1);self.assertEqual(self.opener.open.call_count,1)
        values=self.db.table.return_value.update.call_args.args[0]
        self.assertNotIn('status',values)
        self.assertNotIn('private detail',values['last_error'])

    def test_divergent_database_target_is_not_sent(self):
        self.row['phone']='551199999999'
        with self.assertRaises(RuntimeError):self.request()
        self.opener.open.assert_not_called()

    def test_concurrent_provider_status_is_not_overwritten(self):
        self.request()
        values=self.db.table.return_value.update.call_args.args[0]
        self.assertNotIn('status',values)
        self.db.table.return_value.update.return_value.eq.return_value.eq.assert_called_with('status','pending')


class CommandRouteTests(TestCase):
    def setUp(self):
        # Import UI/auth after suite discovery sets its isolated STAGING environment.
        global routes
        from app.routers import dispatch_commands as routes
        from app.dependencies.auth import current_user
        self.user={'id':str(uuid4()),'status':'active','access_level':'administrativo',
                   'full_name':'Teste','role':'administrador','email':'fixture@example.local'}
        app=FastAPI();app.include_router(routes.router)
        app.dependency_overrides[current_user]=lambda:self.user
        self.client=TestClient(app)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(routes.service,'list_dispatches',return_value=[]))
        self.stack.enter_context(patch.object(routes.service,'channel_ready',return_value=True))
        self.stack.enter_context(patch.object(routes,'csrf_token_for_session',return_value='csrf-test'))
        self.csrf=self.stack.enter_context(patch.object(routes,'verify_csrf_token',return_value=True))
        self.request=self.stack.enter_context(patch.object(routes.service,'request_dispatch',return_value={'id':str(uuid4()),'transport_confirmed':True}))
        self.data={'name':'Teste','phone':'5511988765432','request_id':str(uuid4()),'csrf_token':'csrf-test'}

    def test_common_profile_cannot_read_or_post(self):
        self.user['access_level']='comum'
        self.assertEqual(self.client.get('/disparos/envio').status_code,403)
        self.assertEqual(self.client.post('/disparos/envio',data=self.data).status_code,403)
        self.request.assert_not_called()

    def test_bad_csrf_cannot_create(self):
        self.csrf.return_value=False
        self.assertEqual(self.client.post('/disparos/envio',data=self.data).status_code,403)
        self.request.assert_not_called()

    def test_success_redirects_refresh_to_get(self):
        response=self.client.post('/disparos/envio',data=self.data,follow_redirects=False)
        self.assertEqual(response.status_code,303)
        self.assertEqual(response.headers['location'],'/disparos/envio?resultado=recebido')
        self.assertEqual(self.client.get(response.headers['location']).status_code,200)
        self.assertEqual(self.request.call_count,1)

    def test_uncertain_transport_is_not_reported_as_sent(self):
        self.request.return_value={'transport_confirmed':False}
        response=self.client.post('/disparos/envio',data=self.data,follow_redirects=False)
        self.assertIn('resultado=pendente',response.headers['location'])

    def test_backend_exception_does_not_expose_details(self):
        self.request.side_effect=RuntimeError('private service token')
        response=self.client.post('/disparos/envio',data=self.data)
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private service token',response.text)
        self.assertIn(self.data['request_id'],response.text)

    def test_html_customer_content_is_escaped(self):
        self.request.side_effect=ValueError('Nome inválido')
        self.data['name']='<script>alert(1)</script>'
        response=self.client.post('/disparos/envio',data=self.data)
        self.assertEqual(response.status_code,422)
        self.assertNotIn('<script>alert(1)</script>',response.text)
        self.assertIn('&lt;script&gt;',response.text)


class ExplicitConfigurationTests(TestCase):
    def test_explicit_profile_mode_does_not_read_implicit_env(self):
        import os
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from app.core.config import get_settings
        previous=Path.cwd()
        try:
            with TemporaryDirectory() as directory, patch.dict(os.environ, {'VENDRA_ENV_FILE':''}, clear=True):
                try:
                    os.chdir(directory)
                    Path('.env').write_text('SUPABASE_URL=https://wrong-project.supabase.co\n',encoding='utf8')
                    get_settings.cache_clear()
                    self.assertIsNone(get_settings().supabase_url)
                finally:
                    os.chdir(previous)
        finally:
            os.chdir(previous)
            get_settings.cache_clear()
