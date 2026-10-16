from types import SimpleNamespace
from uuid import uuid4
from unittest import TestCase
from unittest.mock import patch, MagicMock

from app.services import whatsapp_human_command_service as service


class HumanCommandTests(TestCase):
    def setUp(self):
        self.actor, self.ticket, self.key, self.mid, self.oid = [str(uuid4()) for _ in range(5)]
        self.args = dict(actor_id=self.actor, ticket_id=self.ticket, body=' Olá ', request_id=self.key)
        self.settings = SimpleNamespace(demo_mode=False, whatsapp_persistent_control_enabled=True,
                                       app_env='staging', supabase_configured=True)
        self.db = MagicMock()
        self.value = dict(accepted=True, duplicate=False, message_id=self.mid, outbox_id=self.oid,
            message=dict(id=self.mid, ticket_id=self.ticket, sender_id=self.actor, body='Olá',
                         direction='outbound', is_internal=False, sender_kind='human', channel='whatsapp'),
            outbox=dict(id=self.oid, ticket_id=self.ticket, message_id=self.mid, status='pending', claim_token='PRIVATE'))
        self.db.rpc.return_value.execute.return_value.data = self.value
        for name, value in [('get_settings', self.settings), ('get_admin_client', self.db)]:
            p = patch.object(service, name, return_value=value); p.start(); self.addCleanup(p.stop)

    def test_duplicate_recovers_same_ids_and_never_exposes_claim(self):
        for duplicate in (False, True):
            self.value['duplicate'] = duplicate
            result = service.request_human_text(**self.args)
            self.assertEqual(result['outbox_id'], self.oid)
            self.assertEqual(result['duplicate'], duplicate)
            self.assertNotIn('claim_token', result['outbox'])

    def test_invalid_identity_body_and_disabled_mode_never_calls_rpc(self):
        for changes in ({'request_id': None}, {'actor_id':'wrong'}, {'body':' '}, {'body':'a'*4097}):
            with self.assertRaises(ValueError): service.request_human_text(**{**self.args, **changes})
        self.settings.demo_mode = True
        with self.assertRaises(ValueError): service.request_human_text(**self.args)
        self.db.rpc.assert_not_called()

    def test_uncertain_result_is_not_retried_and_error_is_private(self):
        self.db.rpc.return_value.execute.side_effect = RuntimeError('PRIVATE token')
        with self.assertRaises(service.HumanCommandUnavailable) as error:
            service.request_human_text(**self.args)
        self.assertNotIn('PRIVATE', str(error.exception)); self.db.rpc.assert_called_once()

    def test_mismatched_message_is_rejected(self):
        self.value['message']['ticket_id'] = str(uuid4())
        with self.assertRaises(service.HumanCommandUnavailable): service.request_human_text(**self.args)

    def test_conflict_maps_without_raw_database_error(self):
        class Conflict(Exception): code = 'PT409'
        self.db.rpc.return_value.execute.side_effect = Conflict('PRIVATE')
        with self.assertRaises(service.HumanCommandConflict): service.request_human_text(**self.args)
