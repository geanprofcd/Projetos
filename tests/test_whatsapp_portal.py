from contextlib import ExitStack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4
from app.services import whatsapp_portal_service as service


class ConversationServiceTests(TestCase):
    def setUp(self):
        self.ticket_id = str(uuid4())
        self.user = {'id': str(uuid4()), 'status': 'active', 'access_level': 'administrativo'}
        self.settings = SimpleNamespace(app_env='staging', demo_mode=False)
        self.db = MagicMock()
        self.detail = {'ticket': {'status': 'novo'}, 'control': {'enabled': True,
            'window_open': True, 'control_version': 2}}
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(service, 'get_settings', return_value=self.settings))
        self.stack.enter_context(patch.object(service, 'get_admin_client', return_value=self.db))

    def change(self, **kwargs):
        args = dict(ticket_id=self.ticket_id, mode='human', version=2, user=self.user)
        args.update(kwargs)
        return service.change_mode(**args)

    def test_non_staging_and_demo_never_open_database(self):
        for env, demo in [('production', False), ('staging', True)]:
            self.settings.app_env=env; self.settings.demo_mode=demo
            with self.assertRaises(ValueError):service.list_conversations()
        service.get_admin_client.assert_not_called()

    def test_invalid_ticket_never_opens_database(self):
        with self.assertRaises(ValueError):service.get_conversation('invalid')
        service.get_admin_client.assert_not_called()

    def test_non_admin_or_inactive_cannot_change_control(self):
        for change in [{'access_level':'comercial'}, {'access_level':'gerencial'}, {'status':'inactive'}]:
            with self.subTest(change=change),self.assertRaises(PermissionError):
                self.change(user={**self.user, **change})
        self.db.rpc.assert_not_called()

    def test_invalid_mode_and_version_never_call_rpc(self):
        for change in [{'mode':'invalid'}, {'version':0}, {'version':True}, {'version':'2'}]:
            with self.subTest(change=change),self.assertRaises(ValueError):self.change(**change)
        self.db.rpc.assert_not_called()

    def test_closed_or_missing_conversation_blocks_control(self):
        for detail in [None, {'ticket':{'status':'cancelado'}}, {'ticket':{'status':'finalizado'}}]:
            with patch.object(service,'get_conversation',return_value=detail),self.assertRaises(ValueError):self.change()
        self.db.rpc.assert_not_called()

    def test_stale_form_returns_conflict_before_rpc(self):
        with patch.object(service,'get_conversation',return_value=self.detail),self.assertRaises(service.ConversationConflict):
            self.change(version=1)
        self.db.rpc.assert_not_called()

    def test_resume_requires_global_enable_and_open_window(self):
        for field in ['enabled','window_open']:
            detail={'ticket':{'status':'novo'},'control':{**self.detail['control'],field:False}}
            with patch.object(service,'get_conversation',return_value=detail),self.assertRaises(ValueError):self.change(mode='ai')
        self.db.rpc.assert_not_called()

    def test_takeover_works_when_global_automation_disabled(self):
        detail={'ticket':{'status':'novo'},'control':{**self.detail['control'],'enabled':False}}
        self.db.rpc.return_value.execute.return_value.data={'mode':'human'}
        with patch.object(service,'get_conversation',return_value=detail):self.assertEqual(self.change()['mode'],'human')
        self.assertEqual(self.db.rpc.call_args.args,('vendra_whatsapp_mode_v1',{
            'p_ticket_id':self.ticket_id,'p_mode':'human','p_expected_version':2,'p_actor_id':self.user['id']}))

    def test_database_concurrent_conflict_is_sanitized(self):
        error=RuntimeError('PRIVATE SQL');error.code='PT409'
        self.db.rpc.return_value.execute.side_effect=error
        with patch.object(service,'get_conversation',return_value=self.detail),self.assertRaises(service.ConversationConflict) as caught:self.change()
        self.assertNotIn('PRIVATE',str(caught.exception))

    def test_missing_database_confirmation_is_failure(self):
        self.db.rpc.return_value.execute.return_value.data=None
        with patch.object(service,'get_conversation',return_value=self.detail),self.assertRaises(RuntimeError):self.change()


class ConversationRouteTests(TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.routers import whatsapp_conversations as routes
        self.routes=routes
        self.user={'id':str(uuid4()),'full_name':'CODEX-TESTE','status':'active','access_level':'administrativo'}
        self.ticket_id=str(uuid4())
        self.detail={'ticket':{'id':self.ticket_id,'customer_name':'Teste','title':'Teste','status':'novo'},
            'messages':[{'body':'<script>alert(1)</script>','direction':'inbound','sender_kind':'customer',
                'created_at':'2026-10-15T16:00:00+00:00','delivery_status':'received'}],
            'control':{'mode':'ai','enabled':True,'window_open':True,'control_version':2}}
        app=FastAPI();app.include_router(routes.router)
        app.dependency_overrides[routes.current_user]=lambda:self.user
        self.client=TestClient(app)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(routes.service,'get_conversation',return_value=self.detail))
        self.change=self.stack.enter_context(patch.object(routes.service,'change_mode',return_value={'mode':'human'}))
        self.csrf=self.stack.enter_context(patch.object(routes,'verify_csrf_token',return_value=True))

    def post(self,**changes):
        data={'mode':'human','version':2,'csrf_token':'test'};data.update(changes)
        return self.client.post('/conversas/'+self.ticket_id+'/modo',data=data,follow_redirects=False)

    def test_common_cannot_read_or_change(self):
        self.user['access_level']='comum'
        self.assertEqual(self.client.get('/conversas/'+self.ticket_id).status_code,403)
        self.assertEqual(self.post().status_code,403);self.change.assert_not_called()

    def test_commercial_reads_escaped_messages_without_control(self):
        self.user['access_level']='comercial'
        response=self.client.get('/conversas/'+self.ticket_id)
        self.assertEqual(response.status_code,200)
        self.assertIn('&lt;script&gt;',response.text);self.assertNotIn('<script>alert(1)</script>',response.text)
        self.assertNotIn('Assumir atendimento</button>',response.text)
        self.assertEqual(self.post().status_code,403);self.change.assert_not_called()

    def test_admin_can_takeover_with_valid_form(self):
        self.assertEqual(self.post().status_code,303)
        self.assertEqual(self.change.call_args.kwargs['version'],2)

    def test_csrf_failure_does_not_change_state(self):
        self.csrf.return_value=False
        self.assertEqual(self.post().status_code,403);self.change.assert_not_called()

    def test_conflict_shows_fresh_control_and_returns409(self):
        self.change.side_effect=service.ConversationConflict('Outra pessoa alterou o controle.')
        response=self.post();self.assertEqual(response.status_code,409)
        self.assertIn('Outra pessoa alterou',response.text);self.assertIn('name="version" value="2"',response.text)

    def test_database_failure_does_not_leak_details(self):
        self.change.side_effect=RuntimeError('PRIVATE KEY SQL')
        response=self.post();self.assertEqual(response.status_code,503);self.assertNotIn('PRIVATE',response.text)

    def test_non_whatsapp_or_missing_ticket_returns404(self):
        self.routes.service.get_conversation.return_value=None
        self.assertEqual(self.client.get('/conversas/'+self.ticket_id).status_code,404)
