from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock,patch
from uuid import uuid4
from app.services import dispatch_service as service


class CommercialHistoryTests(TestCase):
    def setUp(self):
        self.settings=SimpleNamespace(demo_mode=False,whatsapp_persistent_control_enabled=True)
        self.db=MagicMock()
        self.chain=self.db.table.return_value.select.return_value
        self.row={'id':str(uuid4()),'name':'Teste','phone':'558700000000','status':'read'}
    def test_real_history_is_bounded_and_uses_existing_status_labels(self):
        self.chain.order.return_value.limit.return_value.execute.return_value.data=[self.row]
        with patch.object(service,'get_settings',return_value=self.settings),patch.object(service,'get_admin_client',return_value=self.db):
            rows=service.list_dispatches(9999)
        self.assertEqual(rows[0]['status_label'],'Lido');self.chain.order.return_value.limit.assert_called_once_with(500)
        self.assertNotIn('make_response',self.db.table.return_value.select.call_args.args[0])
    def test_disabled_flag_keeps_previous_behavior_without_database(self):
        self.settings.whatsapp_persistent_control_enabled=False
        with patch.object(service,'get_settings',return_value=self.settings),patch.object(service,'get_admin_client') as db:
            self.assertEqual(service.list_dispatches(),[]);self.assertIsNone(service.get_dispatch(self.row['id']))
        db.assert_not_called()
    def test_invalid_dispatch_id_never_queries_database(self):
        with patch.object(service,'get_settings',return_value=self.settings),patch.object(service,'get_admin_client') as db:
            self.assertIsNone(service.get_dispatch('invalid'))
        db.assert_not_called()
    def test_real_retry_stays_blocked_without_transport_or_database(self):
        with patch.object(service,'get_settings',return_value=self.settings),patch.object(service,'get_admin_client') as db,patch.object(service,'_post_json') as transport:
            with self.assertRaises(ValueError):service.retry_dispatch(self.row['id'],requested_by='operator')
        db.assert_not_called();transport.assert_not_called()
    def test_real_get_dispatch_reads_one_record(self):
        self.chain.eq.return_value.limit.return_value.execute.return_value.data=[self.row]
        with patch.object(service,'get_settings',return_value=self.settings),patch.object(service,'get_admin_client',return_value=self.db):
            self.assertEqual(service.get_dispatch(self.row['id']),self.row)
        self.chain.eq.assert_called_once_with('id',self.row['id'])
