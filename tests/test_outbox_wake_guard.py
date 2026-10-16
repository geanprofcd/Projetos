from types import SimpleNamespace
from uuid import uuid4
from unittest import TestCase
from unittest.mock import patch,MagicMock
from app.services import outbox_wake_service as service


class WakeGuardTests(TestCase):
    def setUp(self):
        self.tid,self.mid,self.oid=[str(uuid4()) for _ in range(3)]
        self.settings=SimpleNamespace(app_env='staging',demo_mode=False,whatsapp_persistent_control_enabled=True,
            supabase_url='https://ljufhqnadzltqbtdaulv.supabase.co',whatsapp_staging_wake_enabled=True,
            whatsapp_staging_wake_url='https://hook.us2.make.com/'+'a'*32,whatsapp_staging_wake_token='PRIVATE'+'s'*40,
            whatsapp_staging_wake_ticket_id=self.tid,whatsapp_staging_wake_phone='5511988765432')
        self.item=dict(id=self.oid,ticket_id=self.tid,message_id=self.mid)
        self.row={**self.item,'phone':'551188765432','status':'pending','provider_message_id':None}
        self.db=MagicMock();self.db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[self.row]
        for target,value in [('app.services.outbox_wake_service.get_settings',self.settings),('app.db.supabase.get_admin_client',self.db)]:
            p=patch(target,return_value=value);p.start();self.addCleanup(p.stop)
    def test_default_off_does_not_notify_or_read_database(self):
        self.settings.whatsapp_staging_wake_enabled=False
        with patch.object(service,'_post_json') as post:
            self.assertFalse(service.notify_make_outbox_async(self.item))
            self.assertFalse(service.send_make_outbox_wake(self.item)['sent']);post.assert_not_called()
        self.db.table.assert_not_called()
    def test_only_configured_staging_hook_and_project_are_accepted(self):
        for field,value in [('whatsapp_staging_wake_url','https://evil.invalid/'+('a'*32)),('supabase_url','https://original.supabase.co'),('whatsapp_staging_wake_token','short')]:
            before=getattr(self.settings,field);setattr(self.settings,field,value)
            with patch.object(service,'_post_json') as post:self.assertFalse(service.send_make_outbox_wake(self.item)['sent']);post.assert_not_called()
            setattr(self.settings,field,before)
    def test_other_ticket_and_processed_outbox_never_notify(self):
        with patch.object(service,'_post_json') as post:
            self.assertFalse(service.send_make_outbox_wake({**self.item,'ticket_id':str(uuid4())})['sent'])
            self.row['status']='claimed'
            self.assertFalse(service.send_make_outbox_wake(self.item)['sent']);post.assert_not_called()
    def test_phone_mismatch_never_notifies(self):
        self.row['phone']='558700000000'
        with patch.object(service,'_post_json') as post:self.assertFalse(service.send_make_outbox_wake(self.item)['sent']);post.assert_not_called()
    def test_valid_item_has_secret_and_only_identifiers_not_message_content(self):
        with patch.object(service,'_post_json',return_value=(200,'Accepted')) as post:
            self.assertTrue(service.send_make_outbox_wake(self.item)['sent'])
        payload=post.call_args.args[1]
        self.assertEqual(payload['wake_secret'],self.settings.whatsapp_staging_wake_token)
        self.assertNotIn('body',payload);self.assertNotIn('phone',payload)
    def test_errors_never_expose_private_url_token(self):
        with patch.object(service,'_post_json',side_effect=RuntimeError('PRIVATE URL TOKEN')):
            result=service.send_make_outbox_wake(self.item)
        self.assertFalse(result['sent']);self.assertNotIn('PRIVATE',str(result))
