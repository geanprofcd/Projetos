from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import base64
import unittest
from fastapi.testclient import TestClient
from app.whatsapp_callbacks import BridgeConfig, create_app, load_config


class DatabaseStub:
    def __init__(self, ticket, customer, outbox):
        self.rpc_calls = []
        self.reads = []
        self.responses = {}
        self.rows = {'tickets': {ticket: {'customer_id': customer, 'source': 'whatsapp'}},
                     'customers': {customer: {'phone_normalized': '551100000000'}},
                     'whatsapp_outbox': {outbox: {'phone': '551100000000'}}}
        self.read_error = False

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        result = self.responses.get(name, {'accepted': True})
        class Call:
            def execute(self):
                if isinstance(result, Exception): raise result
                return type('Result', (), {'data': dict(result)})()
        return Call()

    def table(self, name):
        database = self
        class Query:
            def select(self, columns): return self
            def eq(self, field, value): self.entity = value; return self
            def limit(self, size): return self
            def execute(self):
                database.reads.append((name, self.entity))
                if database.read_error: raise RuntimeError('private database diagnostic')
                row = database.rows[name].get(self.entity)
                return type('Result', (), {'data': [row] if row else []})()
        return Query()


class ControlBridgeSecurity(unittest.TestCase):
    def setUp(self):
        self.ticket, self.customer, self.outbox, self.inbound = [str(uuid4()) for _ in range(4)]
        self.config = BridgeConfig('staging', 'a'*20, 'https://'+'a'*20+'.supabase.co',
            'sb_secret_'+'x'*40, 's'*40, '123', '456', ('5511900000000',), ai_enabled=True)
        self.db = DatabaseStub(self.ticket, self.customer, self.outbox)
        self.client = TestClient(create_app(self.config, client=self.db))
        self.headers = {'X-Webhook-Secret': self.config.webhook_secret}
        self.meta = {'phone_number_id': '123', 'business_account_id': '456',
                     'occurred_at': datetime.now(timezone.utc).isoformat()}
        self.reply = dict(self.meta, phone='551100000000', message='Olá! #1',
            external_message_id='trace-unit', ticket_id=self.ticket,
            inbound_message_id=self.inbound, control_version=2)
        self.binding = dict(self.meta, recipient_id='551100000000', provider_message_id='wamid-unit',
                            claim_token='c'*36, status='sent')
        self.bind_url = '/webhooks/make/whatsapp/outbox/'+self.outbox+'/status'

    def tearDown(self): self.client.close()

    def test_disabled_profile_does_not_register_ai_endpoints(self):
        with TestClient(create_app(replace(self.config, ai_enabled=False), client=self.db)) as client:
            self.assertEqual(client.post('/webhooks/make/ai/reply', json=self.reply, headers=self.headers).status_code, 404)
            self.assertEqual(client.get('/webhooks/make/ai/control/'+self.ticket, headers=self.headers).status_code, 404)
        self.assertFalse(self.db.reads); self.assertFalse(self.db.rpc_calls)

    def test_reply_and_binding_auth_before_entity_lookup(self):
        for url, body in [('/webhooks/make/ai/reply', self.reply), (self.bind_url, self.binding)]:
            self.assertEqual(self.client.post(url, json=body).status_code, 401)
            self.assertEqual(self.client.post(url, json=dict(body, business_account_id='999'), headers=self.headers).status_code, 403)
        self.assertFalse(self.db.reads); self.assertFalse(self.db.rpc_calls)

    def test_control_requires_secret_before_lookup(self):
        self.assertEqual(self.client.get('/webhooks/make/ai/control/'+self.ticket).status_code, 401)
        self.assertFalse(self.db.reads)

    def test_forged_allowed_phone_cannot_prepare_other_customer_reply(self):
        self.db.rows['customers'][self.customer]['phone_normalized'] = '551100000001'
        r = self.client.post('/webhooks/make/ai/reply', json=self.reply, headers=self.headers)
        self.assertEqual(r.status_code, 403); self.assertFalse(self.db.rpc_calls)

    def test_forged_allowed_phone_cannot_bind_other_customer_outbox(self):
        self.db.rows['whatsapp_outbox'][self.outbox]['phone'] = '551100000001'
        self.assertEqual(self.client.post(self.bind_url, json=self.binding, headers=self.headers).status_code, 403)
        self.assertFalse(self.db.rpc_calls)

    def test_control_denies_outside_scope_and_wrong_channel(self):
        url = '/webhooks/make/ai/control/'+self.ticket
        self.db.rows['tickets'][self.ticket]['source'] = 'interno'
        self.assertEqual(self.client.get(url, headers=self.headers).status_code, 403)
        self.db.rows['tickets'][self.ticket]['source'] = 'whatsapp'
        self.db.rows['customers'][self.customer]['phone_normalized'] = '551100000001'
        self.assertEqual(self.client.get(url, headers=self.headers).status_code, 403)
        self.assertFalse(self.db.rpc_calls)

    def test_missing_entity_and_lookup_failure_do_not_authorize(self):
        self.db.rows['tickets'].clear()
        r = self.client.post('/webhooks/make/ai/reply', json=self.reply, headers=self.headers)
        self.assertEqual(r.status_code, 404)
        self.db.read_error = True
        r = self.client.post('/webhooks/make/ai/reply', json=self.reply, headers=self.headers)
        self.assertEqual(r.status_code, 503); self.assertNotIn('private', r.text)
        self.assertFalse(self.db.rpc_calls)

    def test_reply_decodes_unicode_and_removes_only_trailing_marker(self):
        text = 'Posição #2: "Olá"\nPode confirmar? 😀 #3'
        body = dict(self.reply, message_base64=base64.b64encode(text.encode()).decode(), route_code='3')
        body.pop('message')
        r = self.client.post('/webhooks/make/ai/reply', json=body, headers=self.headers)
        self.assertEqual(r.status_code, 202)
        function, args = self.db.rpc_calls[0]
        self.assertEqual(function, 'vendra_whatsapp_ai_prepare_v1')
        self.assertEqual(args, {'p_ticket_id': self.ticket, 'p_inbound_message_id': self.inbound,
                               'p_body': text[:-3].strip(), 'p_expected_version': 2})

    def test_empty_marker_and_invalid_delivery_contract_do_not_prepare(self):
        for delta in ({'message': '#1'}, {'delivery_mode': 'queue'}, {'route_code': '4'},
                      {'control_version': 0}, {'inbound_message_id': 'forged'}):
            r = self.client.post('/webhooks/make/ai/reply', json=dict(self.reply, **delta), headers=self.headers)
            self.assertEqual(r.status_code, 422)
        self.assertFalse(self.db.rpc_calls)

    def test_stale_control_and_duplicate_are_forwarded_without_authorization(self):
        for reason in ('stale_control_version', 'already_prepared'):
            self.db.responses['vendra_whatsapp_ai_prepare_v1'] = {'accepted': True,
                'authorized': False, 'suppressed': True, 'reason': reason}
            r = self.client.post('/webhooks/make/ai/reply', json=self.reply, headers=self.headers)
            self.assertEqual(r.status_code, 202); self.assertFalse(r.json()['authorized'])
            self.assertNotIn('outbox', r.json())

    def test_binding_available_with_ai_disabled_and_passes_token(self):
        self.db.responses['vendra_whatsapp_bind_v1'] = {'accepted': True, 'status': 'read', 'reconciled': 2}
        with TestClient(create_app(replace(self.config, ai_enabled=False), client=self.db)) as client:
            r = client.post(self.bind_url, json=self.binding, headers=self.headers)
        self.assertEqual(r.status_code, 202); self.assertEqual(r.json()['status'], 'read')
        self.assertEqual(self.db.rpc_calls[0][1], {'p_outbox_id': self.outbox,
            'p_provider_message_id': 'wamid-unit', 'p_claim_token': 'c'*36})
        self.assertNotIn('claim_token', r.text)

    def test_bad_binding_token_or_status_cannot_reconcile(self):
        for delta in ({'claim_token': 'short'}, {'status': 'read'}, {'recipient_id': '551100000001'}):
            r = self.client.post(self.bind_url, json=dict(self.binding, **delta), headers=self.headers)
            self.assertIn(r.status_code, (403, 422))
        self.assertFalse(self.db.rpc_calls)

    def test_backend_permission_error_is_forbidden_without_diagnostic_leak(self):
        self.db.responses['vendra_whatsapp_bind_v1'] = type('Denied', (Exception,), {'code': '42501'})('private token')
        r = self.client.post(self.bind_url, json=self.binding, headers=self.headers)
        self.assertEqual(r.status_code, 403); self.assertNotIn('private', r.text)

    def test_duplicate_inbound_never_routes_to_ai(self):
        for duplicate in (False, True):
            self.db.responses['vendra_whatsapp_receive_v1'] = {'accepted': True, 'duplicate': duplicate, 'ticket_id': self.ticket}
            self.db.responses['vendra_whatsapp_control_v1'] = {'accepted': True, 'route_to_ai': True, 'control_version': 2}
            body = {k: self.reply[k] for k in (*self.meta.keys(), 'phone', 'message', 'external_message_id')}
            r = self.client.post('/webhooks/make/whatsapp', json=body, headers=self.headers)
            self.assertEqual(r.status_code, 202)
            self.assertEqual(r.json()['automation']['route_to_ai'], not duplicate)

    def test_global_disabled_control_never_routes_to_ai(self):
        self.db.responses['vendra_whatsapp_receive_v1'] = {'accepted': True, 'duplicate': False, 'ticket_id': self.ticket}
        self.db.responses['vendra_whatsapp_control_v1'] = {'accepted': True, 'route_to_ai': False, 'enabled': False}
        body = {k: self.reply[k] for k in (*self.meta.keys(), 'phone', 'message', 'external_message_id')}
        r = self.client.post('/webhooks/make/whatsapp', json=body, headers=self.headers)
        self.assertFalse(r.json()['automation']['route_to_ai'])

    def test_explicit_config_flag_defaults_off_and_rejects_ambiguous_values(self):
        contents = '\n'.join(['APP_ENV=staging', 'VENDRA_BRIDGE_PROJECT_REF='+'a'*20,
            'SUPABASE_URL=https://'+'a'*20+'.supabase.co', 'SUPABASE_SERVICE_ROLE_KEY=sb_secret_'+'x'*40,
            'MAKE_WEBHOOK_SECRET='+'s'*40, 'META_PHONE_NUMBER_ID=123', 'META_WABA_ID=456',
            'VENDRA_BRIDGE_ALLOWED_PHONES=551100000000'])
        with TemporaryDirectory() as folder:
            path = Path(folder)/'bridge.env'; path.write_text(contents, encoding='utf-8')
            self.assertFalse(load_config(path).ai_enabled)
            path.write_text(contents+'\nVENDRA_BRIDGE_AI_ENABLED=true', encoding='utf-8')
            self.assertTrue(load_config(path).ai_enabled)
            path.write_text(contents+'\nVENDRA_BRIDGE_AI_ENABLED=yes', encoding='utf-8')
            with self.assertRaises(ValueError): load_config(path)


if __name__ == '__main__': unittest.main()
