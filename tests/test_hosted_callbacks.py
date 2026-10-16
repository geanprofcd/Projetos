import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.hosted_callbacks import configuration_from_environment, mount_callbacks


class HostedCallbacks(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(app_env='production', demo_mode=False,
            supabase_url='https://znkjibqcikuigfwfsbjb.supabase.co',
            supabase_service_role_key='sb_secret_'+'x'*40)
        self.values = {'VENDRA_BRIDGE_ENABLED':'true', 'VENDRA_BRIDGE_WEBHOOK_SECRET':'s'*40,
            'META_PHONE_NUMBER_ID':'123', 'META_WABA_ID':'456',
            'VENDRA_BRIDGE_ALLOWED_PHONES':'5511900000000'}

    def test_disabled_bridge_does_not_require_credentials(self):
        self.assertIsNone(configuration_from_environment(SimpleNamespace(), {}))

    def test_staging_database_cannot_be_hosted_as_original(self):
        self.settings.supabase_url='https://ljufhqnadzltqbtdaulv.supabase.co'
        with self.assertRaises(ValueError):configuration_from_environment(self.settings,self.values)

    def test_missing_secret_or_ambiguous_flag_stops_startup(self):
        for changes in ({'VENDRA_BRIDGE_WEBHOOK_SECRET':''},{'VENDRA_BRIDGE_AI_ENABLED':'yes'}):
            with self.assertRaises(ValueError):configuration_from_environment(self.settings,dict(self.values,**changes))

    def test_mount_preserves_portal_and_authenticates_callback(self):
        from tests.test_whatsapp_callbacks import ClientStub
        portal=FastAPI()
        @portal.get('/health')
        def health():return {'portal':'unchanged'}
        db=ClientStub();config=configuration_from_environment(self.settings,self.values)
        body={'phone_number_id':'123','business_account_id':'456','phone':'551100000000',
            'message':'teste','external_message_id':'wamid-hosted',
            'occurred_at':datetime.now(timezone.utc).isoformat()}
        with TestClient(mount_callbacks(portal,config,client=db)) as c:
            self.assertEqual(c.get('/health').json(),{'portal':'unchanged'})
            self.assertEqual(c.post('/callbacks/webhooks/make/whatsapp',json=body).status_code,401)
            self.assertFalse(db.calls)
            self.assertEqual(c.post('/callbacks/webhooks/make/whatsapp',json=body,
                headers={'X-Webhook-Secret':config.webhook_secret}).status_code,202)
            self.assertEqual(len(db.calls),1)

    def test_both_lifespans_are_entered_and_closed(self):
        events=[]
        @asynccontextmanager
        async def portal_life(app):
            events.append('portal_start');yield;events.append('portal_stop')
        @asynccontextmanager
        async def bridge_life(app):
            events.append('bridge_start');yield;events.append('bridge_stop')
        with patch('app.hosted_callbacks.create_app',return_value=FastAPI(lifespan=bridge_life)):
            with TestClient(mount_callbacks(FastAPI(lifespan=portal_life),None)):
                self.assertEqual(events,['portal_start','bridge_start'])
        self.assertEqual(events,['portal_start','bridge_start','bridge_stop','portal_stop'])
