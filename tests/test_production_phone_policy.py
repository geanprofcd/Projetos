from dataclasses import replace
from datetime import datetime,timezone
from unittest import TestCase
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.whatsapp_callbacks import BridgeConfig,create_app
from tests.test_whatsapp_callbacks import ClientStub
from tests import test_production_wake_guard as wake_guards


class ProductionPhonePolicy(TestCase):
    def setUp(self):
        self.config=BridgeConfig('production','znkjibqcikuigfwfsbjb',
            'https://znkjibqcikuigfwfsbjb.supabase.co','sb_secret_'+'x'*40,'s'*40,'123','456',(),allow_all_phones=True)
        self.body={'phone_number_id':'123','business_account_id':'456','phone':'5511900000001',
            'message':'teste','external_message_id':'wamid-policy',
            'occurred_at':datetime.now(timezone.utc).isoformat()}

    def test_general_scope_cannot_be_enabled_in_staging(self):
        with self.assertRaises(ValueError):replace(self.config,environment='staging').validate()

    def test_general_scope_keeps_secret_and_meta_account_checks(self):
        db=ClientStub()
        with TestClient(create_app(self.config,client=db)) as c:
            self.assertEqual(c.post('/webhooks/make/whatsapp',json=self.body).status_code,401)
            self.assertEqual(c.post('/webhooks/make/whatsapp',json={**self.body,'business_account_id':'999'},
                headers={'X-Webhook-Secret':self.config.webhook_secret}).status_code,403)
            self.assertFalse(db.calls)
            self.assertEqual(c.post('/webhooks/make/whatsapp',json=self.body,
                headers={'X-Webhook-Secret':self.config.webhook_secret}).status_code,202)

    def test_test_scope_remains_default_and_ignores_other_recipient(self):
        db=ClientStub();cfg=replace(self.config,allow_all_phones=False,allowed_phones=('551188765432',))
        with TestClient(create_app(cfg,client=db)) as c:
            r=c.post('/webhooks/make/whatsapp',json=self.body,headers={'X-Webhook-Secret':cfg.webhook_secret})
            self.assertTrue(r.json()['ignored']);self.assertFalse(db.calls)

    def test_general_scope_still_rejects_invalid_phone_before_database(self):
        db=ClientStub()
        with TestClient(create_app(self.config,client=db)) as c:
            self.assertEqual(c.post('/webhooks/make/whatsapp',json={**self.body,'phone':'invalid-phone'},
                headers={'X-Webhook-Secret':self.config.webhook_secret}).status_code,422)
        self.assertFalse(db.calls)


class GeneralWakePolicy(TestCase):
    def setUp(self):
        wake_guards.ProductionWakeGuard.setUp(self)

    def test_general_scope_still_binds_row_and_blocks_processed_output(self):
        self.row['phone']='5511900000001'
        with patch.dict('os.environ',{'VENDRA_BRIDGE_ALLOW_ALL_PHONES':'true'}):
            with patch('app.services.outbox_wake_service._post_json',return_value=(200,'Accepted')) as post:
                from app.services.outbox_wake_service import send_make_outbox_wake
                self.assertTrue(send_make_outbox_wake(self.item)['sent']);post.assert_called_once()
            self.row['status']='claimed'
            with patch('app.services.outbox_wake_service._post_json') as post:
                self.assertFalse(send_make_outbox_wake(self.item)['sent']);post.assert_not_called()
