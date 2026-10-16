from contextlib import ExitStack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock,patch
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient


class ComposerRouteTests(TestCase):
    def setUp(self):
        from app.routers import tickets as routes
        self.routes=routes;self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.user={'id':'operator','role':'responsavel','access_level':'comercial','status':'active'}
        app=FastAPI();app.include_router(routes.router);app.dependency_overrides[routes.current_user]=lambda:self.user
        self.client=TestClient(app)
        self.ticket={'id':'ticket','source':'whatsapp','status':'novo'}
        self.read=self.stack.enter_context(patch.object(routes,'get_ticket',return_value=self.ticket))
        self.csrf=self.stack.enter_context(patch.object(routes,'verify_csrf_token',return_value=True))
        self.window=self.stack.enter_context(patch.object(routes,'require_freeform_window'))
        self.mode=self.stack.enter_context(patch.object(routes,'set_ticket_ai_mode',return_value={'mode':'human'}))
        self.add=self.stack.enter_context(patch.object(routes,'add_message',return_value={'id':'message'}))
        self.queue=self.stack.enter_context(patch.object(routes,'queue_whatsapp_outbound'))
        self.upload=self.stack.enter_context(patch.object(routes,'save_attachment',return_value={'id':'attachment'}))
        self.remove_attachment=self.stack.enter_context(patch.object(routes,'delete_attachment'))
        self.remove_message=self.stack.enter_context(patch.object(routes,'delete_message_after_failed_upload'))
        self.stack.enter_context(patch.object(routes,'get_settings',return_value=SimpleNamespace(attachment_max_mb=15,attachment_video_max_mb=50)))
        self.stack.enter_context(patch.object(routes,'_detail_context',side_effect=lambda *a,**kw:kw))
        self.stack.enter_context(patch.object(routes.templates,'TemplateResponse',side_effect=lambda **kw:HTMLResponse(kw['context'].get('composer_error',''),status_code=kw['status_code'])))
    def post(self,data=None,files=None):
        return self.client.post('/atendimentos/ticket/mensagens',data={'body':'Resposta','csrf_token':'test',**(data or {})},files=files,follow_redirects=False)
    def test_csrf_missing_or_invalid_never_reads_or_writes(self):
        self.csrf.return_value=False
        for fields in ({'body':'test'},{'body':'test','csrf_token':'wrong'}):
            self.assertEqual(self.client.post('/atendimentos/ticket/mensagens',data=fields).status_code,403)
        self.read.assert_not_called();self.add.assert_not_called();self.queue.assert_not_called()
    def test_handoff_failure_stops_before_any_message_or_upload(self):
        self.mode.side_effect=ValueError('Atualize o atendimento antes de repetir.')
        r=self.post(files={'files':('teste.txt',b'test','text/plain')})
        self.assertEqual(r.status_code,422);self.assertIn('Atualize',r.text)
        self.add.assert_not_called();self.upload.assert_not_called();self.queue.assert_not_called()
    def test_success_takes_over_before_persistence_and_outbox(self):
        events=[]
        self.mode.side_effect=lambda *a,**kw:events.append('handoff')
        self.add.side_effect=lambda *a,**kw:events.append('message') or {'id':'message'}
        self.queue.side_effect=lambda *a,**kw:events.append('outbox')
        self.assertEqual(self.post().status_code,303);self.assertEqual(events,['handoff','message','outbox'])
        self.assertEqual(self.mode.call_args.kwargs['actor_id'],'operator')
    def test_persistent_text_uses_one_atomic_command_without_legacy_writes(self):
        settings=SimpleNamespace(demo_mode=False,whatsapp_persistent_control_enabled=True)
        with patch.object(self.routes,'get_settings',return_value=settings), patch.object(self.routes,'request_human_text',return_value={'outbox':{'status':'sent'}}) as command:
            self.assertEqual(self.post(data={'request_id':'same-request'}).status_code,303)
        self.assertEqual(command.call_args.kwargs['request_id'],'same-request')
        self.mode.assert_not_called();self.add.assert_not_called();self.queue.assert_not_called()
    def test_uncertain_atomic_result_keeps_nonce_and_never_rolls_back(self):
        settings=SimpleNamespace(demo_mode=False,whatsapp_persistent_control_enabled=True)
        with patch.object(self.routes,'get_settings',return_value=settings), patch.object(self.routes,'request_human_text',side_effect=self.routes.HumanCommandUnavailable('Confira o comando.')), patch.object(self.routes,'_detail_context',return_value={'composer_error':'Confira o comando.'}) as context:
            self.assertEqual(self.post(data={'request_id':'same-request'}).status_code,503)
        self.assertEqual(context.call_args.kwargs['composer_request_id'],'same-request')
        self.mode.assert_not_called();self.add.assert_not_called();self.remove_message.assert_not_called()
    def test_invalid_file_and_empty_form_do_not_take_over(self):
        self.assertEqual(self.post(files={'files':('teste.exe',b'MZ','application/octet-stream')}).status_code,422)
        self.assertEqual(self.post(data={'body':''}).status_code,422)
        self.mode.assert_not_called();self.add.assert_not_called()
    def test_upload_failure_rolls_back_only_created_message_and_files(self):
        self.upload.side_effect=[{'id':'first'},RuntimeError('storage unavailable')]
        r=self.post(files=[('files',('a.txt',b'a','text/plain')),('files',('b.txt',b'b','text/plain'))])
        self.assertEqual(r.status_code,500);self.remove_attachment.assert_called_once_with({'id':'first'})
        self.remove_message.assert_called_once_with('ticket','message');self.queue.assert_not_called()
    def test_internal_note_does_not_take_over_or_queue_whatsapp(self):
        self.assertEqual(self.post(data={'is_internal':'true'}).status_code,303)
        self.mode.assert_not_called();self.queue.assert_not_called()
    def test_expired_window_never_takes_over_or_persists(self):
        self.window.side_effect=self.routes.WhatsAppTemplateRequiredError('Janela encerrada.')
        self.assertEqual(self.post().status_code,422);self.mode.assert_not_called();self.add.assert_not_called()
    def test_seven_attachments_rejected_before_handoff(self):
        r=self.post(files=[('files',(str(i)+'.txt',b'a','text/plain')) for i in range(7)])
        self.assertEqual(r.status_code,422);self.mode.assert_not_called();self.add.assert_not_called()


class ComposerPersistenceTests(TestCase):
    def test_persistent_whatsapp_human_reply_and_note_keep_distinct_channels(self):
        from app.services import ticket_service as service
        db=MagicMock();db.table.return_value.insert.return_value.execute.return_value.data=[{'id':'message'}]
        user={'id':'operator','role':'responsavel'}
        with patch.object(service,'get_settings',return_value=SimpleNamespace(demo_mode=False,whatsapp_persistent_control_enabled=True)),\
             patch.object(service,'get_admin_client',return_value=db),\
             patch.object(service,'get_ticket',return_value={'id':'ticket','source':'whatsapp'}),\
             patch.object(service,'_audit'):
            service.add_message('ticket',user,'Resposta')
            payload=db.table.return_value.insert.call_args.args[0]
            self.assertEqual(payload['channel'],'whatsapp');self.assertEqual(payload['sender_kind'],'human')
            service.add_message('ticket',user,'Nota',is_internal=True)
            payload=db.table.return_value.insert.call_args.args[0]
            self.assertEqual(payload['channel'],'internal');self.assertTrue(payload['is_internal'])
