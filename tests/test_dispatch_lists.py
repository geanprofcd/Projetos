import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
from app.services import dispatch_list_service as service

class DispatchLists(unittest.TestCase):
    def test_manual_list_send_when_channel_off_does_not_reserve(self):
        with patch.object(service,'enabled',return_value=True),patch.object(service.command,'channel_ready',return_value=False),patch.object(service,'get_admin_client') as db:
            with self.assertRaises(ValueError):service.send_item(item_id='item',requested_by='actor',batch_id='batch')
            db.assert_not_called()

    def test_idle_worker_does_not_resolve_funnel_or_call_rpc(self):
        db=MagicMock();db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[]
        with patch.object(service,'get_settings',return_value=SimpleNamespace(dispatch_lists_enabled=True)),patch.object(service,'get_admin_client',return_value=db),patch.object(service.command,'_new_lead_destination') as destination:
            self.assertFalse(service.process_one());destination.assert_not_called();db.rpc.assert_not_called()
    def test_disabled_lists_do_not_query_or_start_worker(self):
        with patch.object(service,'get_settings',return_value=SimpleNamespace(demo_mode=False,dispatch_lists_enabled=False)),patch.object(service,'get_admin_client') as db:
            self.assertFalse(service.enabled());self.assertEqual(service.batches(),[])
            stop,worker=service.start_worker();self.assertIsNone(worker);db.assert_not_called()

    def test_import_normalizes_mobile_aliases_and_excludes_bad_rows(self):
        db=MagicMock();db.rpc.return_value.execute.return_value.data={'id':'list'}
        csv=b'Nome;Telefone\nAna;+55 11 99999-1234\nAna repetida;551199991234\nInvalido;123\n'
        with patch.object(service,'enabled',return_value=True),patch.object(service,'get_admin_client',return_value=db):
            service.import_file(filename='contatos.csv',content=csv,imported_by='11111111-1111-4111-8111-111111111111')
        name,params=db.rpc.call_args.args
        self.assertEqual(name,'vendra_dispatch_list_import_v1')
        self.assertEqual([r['status'] for r in params['p_records']],['ready','duplicate','invalid'])
        self.assertEqual(params['p_records'][0]['phone'],params['p_records'][1]['phone'])

    def test_quantity_outside_ready_range_never_starts_queue(self):
        with patch.object(service,'enabled',return_value=True),patch.object(service.command,'channel_ready',return_value=True),patch.object(service,'items',return_value=[{'status':'ready'}]),patch.object(service,'get_admin_client') as db:
            for qty in (0,2,-1):
                with self.assertRaises(ValueError):service.start(batch_id='list',requested_by='actor',quantity=qty)
            db.assert_not_called()

    def test_empty_atomic_claim_never_transmits(self):
        db=MagicMock();db.rpc.return_value.execute.return_value.data={'claimed':False}
        with patch.object(service,'get_settings',return_value=SimpleNamespace(dispatch_lists_enabled=True)),patch.object(service,'enabled',return_value=True),patch.object(service.command,'channel_ready',return_value=True),patch.object(service.command,'_new_lead_destination',return_value=('funnel','stage')),patch.object(service,'get_admin_client',return_value=db),patch.object(service,'_finish') as finish:
            self.assertFalse(service.process_one());finish.assert_not_called()

    def test_atomic_claim_uses_same_committed_dispatch(self):
        result={'claimed':True,'item_id':'item','batch_id':'batch','dispatch':{'id':'dispatch'}}
        db=MagicMock();db.rpc.return_value.execute.return_value.data=result
        with patch.object(service,'get_settings',return_value=SimpleNamespace(dispatch_lists_enabled=True)),patch.object(service,'enabled',return_value=True),patch.object(service.command,'channel_ready',return_value=True),patch.object(service.command,'_new_lead_destination',return_value=('funnel','stage')),patch.object(service,'get_admin_client',return_value=db),patch.object(service,'_finish') as finish,patch.object(service,'state'):
            self.assertTrue(service.process_one());finish.assert_called_once_with(result)

    def test_uncertain_transport_preserves_pending_and_does_not_retry(self):
        db=MagicMock();row={'id':'dispatch','status':'pending'}
        with patch.object(service,'get_admin_client',return_value=db),patch.object(service.command,'transmit_dispatch',side_effect=TimeoutError) as send:
            result=service._finish({'dispatch':row,'item_id':'item'})
            send.assert_called_once_with(row)
            self.assertEqual(result['dispatch']['status'],'pending')
            self.assertEqual(db.table.return_value.update.call_args.args[0]['status'],'pending')
