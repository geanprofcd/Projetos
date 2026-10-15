from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import base64
import unittest
from fastapi.testclient import TestClient
from app.whatsapp_callbacks import BridgeConfig, canonical_phone, create_app, load_config


class ClientStub:
    def __init__(self): self.calls = []; self.error = None
    def rpc(self, name, params):
        self.calls.append((name, params)); return self
    def execute(self):
        if self.error: raise self.error
        return type('Result', (), {'data': {'accepted': True, 'ticket_id': 'ticket-unit'}})()


class CallbackSecurity(unittest.TestCase):
    def setUp(self):
        self.config = BridgeConfig('staging', 'a'*20, 'https://'+'a'*20+'.supabase.co',
            'sb_secret_'+'x'*40, 's'*40, '123', '456', ('5511900000000',))
        self.db = ClientStub()
        self.client = TestClient(create_app(self.config, client=self.db))
        self.body = {'phone_number_id': '123', 'business_account_id': '456',
            'phone': '551100000000', 'name': 'CODEX', 'message': 'teste',
            'external_message_id': 'wamid-unit', 'occurred_at': datetime.now(timezone.utc).isoformat()}
        self.headers = {'X-Webhook-Secret': self.config.webhook_secret}
    def tearDown(self): self.client.close()
    def test_missing_or_wrong_secret_never_calls_db(self):
        for secret in ('', 'wrong'):
            self.assertEqual(self.client.post('/webhooks/make/whatsapp', json=self.body,
                headers={'X-Webhook-Secret': secret}).status_code, 401)
        self.assertFalse(self.db.calls)
    def test_wrong_account_never_calls_db(self):
        body = dict(self.body, business_account_id='999')
        self.assertEqual(self.client.post('/webhooks/make/whatsapp', json=body, headers=self.headers).status_code, 403)
        self.assertFalse(self.db.calls)
    def test_outside_scope_acknowledged_without_persistence(self):
        body = dict(self.body, phone='5511900000001')
        r = self.client.post('/webhooks/make/whatsapp', json=body, headers=self.headers)
        self.assertTrue(r.json()['ignored']); self.assertFalse(self.db.calls)
    def test_timestamp_required_and_timezone_required(self):
        for stamp in (None, '2026-10-14T13:00:00'):
            self.assertEqual(self.client.post('/webhooks/make/whatsapp',
                json=dict(self.body, occurred_at=stamp), headers=self.headers).status_code, 422)
        self.assertFalse(self.db.calls)
    def test_original_timestamp_preserved_ai_disabled(self):
        r = self.client.post('/webhooks/make/whatsapp', json=self.body, headers=self.headers)
        self.assertEqual(r.status_code, 202)
        self.assertFalse(r.json()['automation']['route_to_ai'])
        self.assertEqual(self.db.calls[0][1]['p_occurred_at'], self.body['occurred_at'])
    def test_db_conflict_and_failure_are_not_success(self):
        self.db.error = type('Conflict', (Exception,), {'code': 'PT409'})('private diagnostic')
        r = self.client.post('/webhooks/make/whatsapp', json=self.body, headers=self.headers)
        self.assertEqual(r.status_code, 409); self.assertNotIn('private', r.text)
        self.db.error = RuntimeError('backend key private')
        r = self.client.post('/webhooks/make/whatsapp', json=self.body, headers=self.headers)
        self.assertEqual(r.status_code, 503); self.assertNotIn('private', r.text)
    def test_no_admin_queue_ai_or_openapi_routes(self):
        for path in ('/docs', '/openapi.json', '/clientes', '/webhooks/make/whatsapp/outbox', '/webhooks/make/ai/reply'):
            self.assertEqual(self.client.get(path).status_code, 404)
    def test_oversized_payload_never_calls_db(self):
        r = self.client.post('/webhooks/make/whatsapp', content=b'x'*65537, headers=self.headers)
        self.assertEqual(r.status_code, 413); self.assertFalse(self.db.calls)
    def test_status_recipient_scope(self):
        body = {'phone_number_id': '123', 'business_account_id': '456', 'occurred_at': self.body['occurred_at'],
                'provider_message_id': 'wamid-unit', 'status': 'read', 'recipient_id': '5511900000001'}
        r = self.client.post('/webhooks/make/whatsapp/provider-status', json=body, headers=self.headers)
        self.assertTrue(r.json()['ignored']); self.assertFalse(self.db.calls)
        body['recipient_id'] = '551100000000'
        self.assertEqual(self.client.post('/webhooks/make/whatsapp/provider-status', json=body, headers=self.headers).status_code, 202)
        self.assertEqual(self.db.calls[0][0], 'vendra_whatsapp_status_v1')
    def test_config_fails_closed_and_has_no_secret_repr(self):
        for override in ({'allowed_phones': ()}, {'project_ref': 'b'*20}, {'webhook_secret': ''}):
            with self.assertRaises(ValueError): replace(self.config, **override).validate()
        self.assertNotIn(self.config.backend_key, repr(self.config))
        self.assertNotIn(self.config.webhook_secret, repr(self.config))
        with TemporaryDirectory() as folder:
            path = Path(folder)/'missing.env'
            with self.assertRaises(ValueError): load_config(path)
            path.write_text('APP_ENV=staging\n', encoding='utf-8')
            with self.assertRaises(ValueError): load_config(path)
    def test_meta_mobile_alias(self):
        self.assertEqual(canonical_phone('+55 11 90000-0000'), canonical_phone('551100000000'))
    def test_encoded_make_text_preserves_quotes_newlines_and_unicode(self):
        text = 'Aspas "teste"\nOlá \\ caminho 😀'
        body = dict(self.body)
        body.pop('message')
        body['message_base64'] = base64.b64encode(text.encode()).decode()
        r = self.client.post('/webhooks/make/whatsapp', json=body, headers=self.headers)
        self.assertEqual(r.status_code, 202)
        self.assertEqual(self.db.calls[0][1]['p_body'], text)
    def test_invalid_or_ambiguous_encoding_never_calls_db(self):
        body = dict(self.body, message_base64='invalid')
        self.assertEqual(self.client.post('/webhooks/make/whatsapp', json=body, headers=self.headers).status_code, 422)
        body.pop('message')
        self.assertEqual(self.client.post('/webhooks/make/whatsapp', json=body, headers=self.headers).status_code, 422)
        self.assertFalse(self.db.calls)


if __name__ == '__main__': unittest.main()
