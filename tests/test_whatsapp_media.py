import unittest
from unittest.mock import patch,MagicMock
from types import SimpleNamespace
from app.services.whatsapp_media_service import validate_media,media_type,notify_media_batch


class MediaPolicyTests(unittest.TestCase):
    def prepared(self,mime,size=1,content=b'x'):
        return SimpleNamespace(mime_type=mime,size_bytes=size,content=content)

    def test_image_five_megabyte_boundary(self):
        self.assertEqual(validate_media(self.prepared('image/png',5*1024*1024)),'image')
        with self.assertRaises(ValueError):validate_media(self.prepared('image/png',5*1024*1024+1))

    def test_video_sixteen_megabyte_boundary(self):
        self.assertEqual(validate_media(self.prepared('video/mp4',16*1024*1024)),'video')
        with self.assertRaises(ValueError):validate_media(self.prepared('video/mp4',16*1024*1024+1))

    def test_ogg_requires_opus(self):
        with self.assertRaises(ValueError):validate_media(self.prepared('audio/ogg',content=b'OggS vorbis'))
        self.assertEqual(validate_media(self.prepared('audio/ogg',content=b'OggS OpusHead')),'audio')

    def test_internal_formats_are_not_silently_sent_as_other_types(self):
        for mime in ('image/gif','audio/wav','video/quicktime','video/webm','text/csv'):
            with self.subTest(mime=mime),self.assertRaises(ValueError):validate_media(self.prepared(mime))

    def test_pdf_text_and_supported_audio_types(self):
        for mime,expected in [('application/pdf','document'),('text/plain','document'),('audio/mpeg','audio'),('audio/mp4','audio')]:
            self.assertEqual(validate_media(self.prepared(mime)),expected)

    def test_batch_preserves_order_and_stops_on_uncertain_result(self):
        class InlineThread:
            def __init__(self,*,target,**kwargs):self.target=target
            def start(self):self.target()
        db=MagicMock();db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[{'status':'sent','provider_message_id':'provider'}]
        with patch('app.services.whatsapp_media_service.get_admin_client',return_value=db),patch('app.services.whatsapp_media_service.threading.Thread',InlineThread),patch('app.services.outbox_wake_service.send_make_outbox_wake',side_effect=[{'sent':True},{'sent':False}]) as wake:
            notify_media_batch([{'id':'done','status':'read'},{'id':'text','status':'pending'},{'id':'file1','status':'pending'},{'id':'file2','status':'pending'}])
        self.assertEqual([c.args[0]['id'] for c in wake.call_args_list],['text','file1'])

    def test_http_accepted_without_provider_binding_does_not_release_next_file(self):
        class InlineThread:
            def __init__(self,*,target,**kwargs):self.target=target
            def start(self):self.target()
        db=MagicMock();db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[{'status':'claimed','provider_message_id':None,'claimed_by':'claim-token'}]
        with patch('app.services.whatsapp_media_service.get_admin_client',return_value=db),patch('app.services.whatsapp_media_service.threading.Thread',InlineThread),patch('app.services.outbox_wake_service.send_make_outbox_wake',return_value={'sent':True}) as wake:
            notify_media_batch([{'id':'file1','status':'pending'},{'id':'file2','status':'pending'}])
        wake.assert_called_once()
        db.rpc.assert_called_once_with('vendra_whatsapp_uncertain_v1',{'p_outbox_id':'file1','p_claim_token':'claim-token'})
