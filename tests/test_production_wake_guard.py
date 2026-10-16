from unittest import TestCase
from unittest.mock import MagicMock,patch
from types import SimpleNamespace
from uuid import uuid4
from app.services import outbox_wake_service as service


class ProductionWakeGuard(TestCase):
    def setUp(self):
        self.settings=SimpleNamespace(app_env='production',demo_mode=False,
            whatsapp_persistent_control_enabled=True,supabase_url='https://znkjibqcikuigfwfsbjb.supabase.co')
        self.item={k:str(uuid4()) for k in ('id','ticket_id','message_id')}
        self.row={**self.item,'status':'pending','phone':'551188765432','provider_message_id':None}
        self.db=MagicMock();self.db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[self.row]
        for target,value in [('app.services.outbox_wake_service.get_settings',self.settings),
            ('app.services.outbox_wake_service.get_make_outbox_settings',{'enabled':True,'wake_url':'https://hook.us2.make.com/'+'a'*32}),
            ('app.db.supabase.get_admin_client',self.db)]:
            p=patch(target,return_value=value);p.start();self.addCleanup(p.stop)
        p=patch.dict('os.environ',{'VENDRA_OUTBOX_WAKE_SECRET':'s'*40,'VENDRA_BRIDGE_ALLOWED_PHONES':'5511988765432'});p.start();self.addCleanup(p.stop)

    def test_missing_secret_or_staging_database_never_notifies(self):
        with patch.dict('os.environ',{'VENDRA_OUTBOX_WAKE_SECRET':''}),patch.object(service,'_post_json') as post:
            self.assertFalse(service.send_make_outbox_wake(self.item)['sent']);post.assert_not_called()
        self.settings.supabase_url='https://ljufhqnadzltqbtdaulv.supabase.co'
        with patch.object(service,'_post_json') as post:
            self.assertFalse(service.send_make_outbox_wake(self.item)['sent']);post.assert_not_called()

    def test_processed_or_other_recipient_never_notifies(self):
        for changes in ({'status':'claimed'},{'phone':'558700000000'}):
            self.row.update(changes)
            with patch.object(service,'_post_json') as post:
                self.assertFalse(service.send_make_outbox_wake(self.item)['sent']);post.assert_not_called()
            self.row.update(status='pending',phone='551188765432')

    def test_identifiers_are_bound_to_persisted_row(self):
        with patch.object(service,'_post_json') as post:
            self.assertFalse(service.send_make_outbox_wake({**self.item,'message_id':str(uuid4())})['sent']);post.assert_not_called()

    def test_valid_production_notification_is_authenticated_without_content(self):
        with patch.object(service,'_post_json',return_value=(200,'Accepted')) as post:
            self.assertTrue(service.send_make_outbox_wake(self.item)['sent'])
        payload=post.call_args.args[1]
        self.assertEqual(payload['wake_secret'],'s'*40)
        self.assertNotIn('body',payload);self.assertNotIn('phone',payload)
