import base64
from dataclasses import replace
from datetime import datetime,timezone
import hashlib
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.whatsapp_callbacks import BridgeConfig,create_app
from app.whatsapp_inbound_media import prepare_received_file,MediaInvalid,MAX_BASE64_CHARS


def encoded(value):return base64.b64encode(value).decode()


class ReceivedMediaTests(TestCase):
    def setUp(self):
        self.content=b'%PDF-1.7\nCODEX'
        self.args=dict(message_id='wamid-inbound',media_type='document',mime_type='application/pdf',
                       file_name='CODEX.pdf',content_base64=encoded(self.content),expected_sha256=hashlib.sha256(self.content).hexdigest())
    def test_checksum_format_signature_and_private_path(self):
        result=prepare_received_file(**{**self.args,'expected_sha256':encoded(hashlib.sha256(self.content).digest()),'file_name':'../../Teste.exe'})
        self.assertEqual(result.metadata['file_name'],'Teste.pdf')
        self.assertTrue(result.metadata['storage_path'].startswith('whatsapp-inbound/'))
        self.assertNotIn('wamid-inbound',result.metadata['storage_path'])
        for changes in ({'expected_sha256':'a'*64},{'mime_type':'image/png'},
                        {'content_base64':'invalid'},{'mime_type':'application/octet-stream'},
                        {'content_base64':encoded(b'bad'),'expected_sha256':hashlib.sha256(b'bad').hexdigest()}):
            with self.subTest(changes=changes),self.assertRaises(MediaInvalid):prepare_received_file(**{**self.args,**changes})
    def test_oversize_rejected_before_base64_decode(self):
        with self.assertRaises(MediaInvalid):prepare_received_file(**{**self.args,'content_base64':'A'*(MAX_BASE64_CHARS+1)})
    def test_ogg_requires_opus(self):
        for content,accepted in [(b'OggS'+b'OpusHead',True),(b'OggS'+b'Vorbis',False)]:
            args={**self.args,'media_type':'audio','mime_type':'audio/ogg','content_base64':encoded(content),'expected_sha256':hashlib.sha256(content).hexdigest()}
            if accepted:self.assertEqual(prepare_received_file(**args).metadata['mime_type'],'audio/ogg')
            else:
                with self.assertRaises(MediaInvalid):prepare_received_file(**args)
    def test_pdf_accepts_above_old_limit_and_rejects_above_25_mib(self):
        content=b'%PDF-1.7\n'+b'x'*(16*1024*1024)
        args={**self.args,'content_base64':encoded(content),'expected_sha256':hashlib.sha256(content).hexdigest()}
        self.assertEqual(prepare_received_file(**args).metadata['size_bytes'],len(content))
        content=b'%PDF-'+b'x'*(25*1024*1024)
        with self.assertRaises(MediaInvalid):prepare_received_file(**{**args,'content_base64':encoded(content),'expected_sha256':hashlib.sha256(content).hexdigest()})
    def test_private_download_failure_is_controlled_without_secret(self):
        from app.services.attachment_service import signed_download_url,AttachmentError
        with patch('app.services.attachment_service.get_admin_client') as db:
            db.return_value.storage.from_.return_value.create_signed_url.side_effect=RuntimeError('private secret')
            with self.assertRaises(AttachmentError) as error:signed_download_url({'storage_path':'private/file.pdf'})
            self.assertNotIn('private secret',str(error.exception))


class InboundMediaBridgeTests(TestCase):
    def setUp(self):
        self.config=BridgeConfig('staging','a'*20,'https://'+'a'*20+'.supabase.co','sb_secret_'+'x'*40,
            's'*40,'123','456',('551100000000',),inbound_media_enabled=True)
        self.db=MagicMock();self.db.rpc.return_value.execute.return_value.data={'accepted':True,'duplicate':False,
            'ticket_id':'ticket-test','message_id':'message-test','attachment_id':'attachment-test','media_stored':True}
        self.bucket=self.db.storage.from_.return_value
        self.client=TestClient(create_app(self.config,client=self.db));self.addCleanup(self.client.close)
        self.content=b'%PDF-1.7\nCODEX'
        self.payload=dict(phone_number_id='123',business_account_id='456',phone='5511900000000',
            occurred_at=datetime.now(timezone.utc).isoformat(),external_message_id='wamid-media-unit',
            media_id='123456',media_type='document',mime_type='application/pdf',
            name_base64=encoded('José'.encode()),caption_base64=encoded('Orçamento "atual"'.encode()),
            file_name_base64=encoded(b'CODEX.pdf'),content_base64=encoded(self.content),sha256=hashlib.sha256(self.content).hexdigest())
        self.headers={'X-Webhook-Secret':self.config.webhook_secret};self.path='/webhooks/make/whatsapp/media'
    def post(self,**changes):return self.client.post(self.path,json={**self.payload,**changes},headers=self.headers)
    def test_disabled_by_default(self):
        with TestClient(create_app(replace(self.config,inbound_media_enabled=False),client=self.db)) as client:
            self.assertEqual(client.post(self.path,json=self.payload,headers=self.headers).status_code,404)
        self.db.rpc.assert_not_called();self.bucket.upload.assert_not_called()
    def test_auth_scope_account_before_storage(self):
        self.assertEqual(self.client.post(self.path,json=self.payload).status_code,401)
        self.assertEqual(self.post(business_account_id='999').status_code,403)
        self.assertTrue(self.post(phone='551100000001').json()['ignored'])
        self.db.rpc.assert_not_called();self.bucket.upload.assert_not_called()
    def test_message_file_and_automation_contract(self):
        response=self.post();self.assertEqual(response.status_code,202)
        self.assertFalse(response.json()['automation']['route_to_ai'])
        name,args=self.db.rpc.call_args.args
        self.assertEqual(name,'vendra_whatsapp_media_receive_v1');self.assertEqual(args['p_name'],'José')
        self.assertIn('Orçamento "atual"',args['p_body']);self.assertEqual(args['p_media_id'],'123456')
        self.assertEqual(self.bucket.upload.call_args.args[1],self.content)
    def test_mime_codec_parameters_are_canonicalized(self):
        self.assertEqual(self.post(mime_type='Application/PDF; charset=binary').status_code,202)
        self.assertEqual(self.db.rpc.call_args.args[1]['p_attachment']['mime_type'],'application/pdf')
    def test_invalid_payload_never_uploads_or_echoes_file(self):
        for changes in ({'sha256':'0'*64},{'caption_base64':'invalid'},{'mime_type':'text/html'},
                        {'media_id':'url:https://example.org'},{'occurred_at':'2026-01-01'}):
            r=self.post(**changes);self.assertEqual(r.status_code,422);self.assertNotIn(self.payload['content_base64'],r.text)
        self.db.rpc.assert_not_called();self.bucket.upload.assert_not_called()
    def test_duplicate_upload_is_verified_never_overwritten(self):
        self.bucket.upload.side_effect=type('Duplicate',(Exception,),{'status_code':409})()
        self.bucket.download.return_value=self.content
        self.assertEqual(self.post().status_code,202)
        self.bucket.download.return_value=b'changed'
        self.assertEqual(self.post().status_code,409)
        self.assertEqual(self.db.rpc.call_count,1)
    def test_storage_failure_stops_before_rpc(self):
        self.bucket.upload.side_effect=RuntimeError('private-key')
        r=self.post();self.assertEqual(r.status_code,503);self.assertNotIn('private-key',r.text)
        self.db.rpc.assert_not_called();self.bucket.remove.assert_not_called()
    def test_uncertain_rpc_preserves_file_for_same_event_retry(self):
        self.db.rpc.return_value.execute.side_effect=RuntimeError('secret')
        self.assertEqual(self.post().status_code,503);self.bucket.remove.assert_not_called()
    def test_definitive_rejection_only_removes_unreferenced_upload(self):
        self.db.rpc.return_value.execute.side_effect=type('Conflict',(Exception,),{'code':'PT409'})()
        self.db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[]
        self.assertEqual(self.post().status_code,409);self.bucket.remove.assert_called_once()
        self.bucket.remove.reset_mock()
        self.db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[{'id':'existing'}]
        self.assertEqual(self.post().status_code,409);self.bucket.remove.assert_not_called()
    def test_future_timestamp_rejected_before_storage(self):
        self.assertEqual(self.post(occurred_at='2100-01-01T00:00:00Z').status_code,422)
        self.bucket.upload.assert_not_called();self.db.rpc.assert_not_called()
    def test_text_route_keeps_small_limit(self):
        response=self.client.post('/webhooks/make/whatsapp',content=b'x'*65537,headers=self.headers)
        self.assertEqual(response.status_code,413)
