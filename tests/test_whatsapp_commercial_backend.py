from contextlib import ExitStack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock,patch
from uuid import uuid4
from app.services import whatsapp_control_service as service


class PersistentControlTests(TestCase):
    def setUp(self):
        self.ticket=str(uuid4());self.actor=str(uuid4())
        self.settings=SimpleNamespace(demo_mode=False,whatsapp_persistent_control_enabled=True,
            app_env='staging',supabase_configured=True)
        self.db=MagicMock();self.value={'accepted':True,'mode':'ai','enabled':True,'connected':True,
            'route_to_ai':True,'control_version':2,'window_open':True}
        self.db.rpc.return_value.execute.return_value.data=self.value
        self.db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[
            {'access_level':'administrativo','status':'active'}]
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(service,'get_settings',return_value=self.settings))
        self.stack.enter_context(patch.object(service,'get_admin_client',return_value=self.db))

    def test_disabled_flag_or_demo_opens_no_database(self):
        for flag,demo in [(False,False),(True,True)]:
            self.settings.whatsapp_persistent_control_enabled=flag;self.settings.demo_mode=demo
            with self.assertRaises(ValueError):service.read_control(self.ticket)
        service.get_admin_client.assert_not_called()

    def test_control_maps_existing_commercial_ui_contract(self):
        result=service.read_control(self.ticket,assistant_name='Dario')
        self.assertTrue(result['should_respond']);self.assertEqual(result['connection_state'],'connected')
        self.assertEqual(result['control_version'],2);self.assertEqual(result['assistant_name'],'Dario')
        self.assertFalse(result['requires_migration'])

    def test_expired_window_does_not_hide_disconnect_action(self):
        self.value.update(route_to_ai=False,window_open=False)
        result=service.read_control(self.ticket)
        self.assertTrue(result['should_respond']);self.assertFalse(result['route_to_ai'])

    def test_missing_or_malformed_control_is_rejected(self):
        for value in [None,{},dict(self.value,control_version=True),dict(self.value,mode='invalid')]:
            self.db.rpc.return_value.execute.return_value.data=value
            with self.assertRaises(ValueError):service.read_control(self.ticket)

    def test_read_error_does_not_expose_provider_details(self):
        self.db.rpc.return_value.execute.side_effect=RuntimeError('PRIVATE SQL TOKEN')
        with self.assertRaises(ValueError) as caught:service.read_control(self.ticket)
        self.assertNotIn('PRIVATE',str(caught.exception))

    def test_mode_change_uses_real_actor_and_compare_and_swap(self):
        self.db.rpc.return_value.execute.side_effect=[SimpleNamespace(data=self.value),
            SimpleNamespace(data={**self.value,'mode':'human','connected':False,'route_to_ai':False,'control_version':3})]
        result=service.change_mode(self.ticket,mode='human',actor_id=self.actor)
        self.assertEqual(result['mode'],'human')
        self.assertEqual(self.db.rpc.call_args.args,('vendra_whatsapp_mode_v1',{
            'p_ticket_id':self.ticket,'p_mode':'human','p_expected_version':2,'p_actor_id':self.actor}))

    def test_common_inactive_and_missing_profiles_never_write(self):
        for profiles in [[],[{'access_level':'comum','status':'active'}],
                         [{'access_level':'comercial','status':'inactive'}],
                         [{'access_level':'gerencial','status':'inactive'}]]:
            self.db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=profiles
            with self.assertRaises(ValueError):service.change_mode(self.ticket,mode='human',actor_id=self.actor)
        self.db.rpc.assert_not_called()

    def test_active_commercial_and_manager_use_their_own_identity(self):
        for level in ('comercial','gerencial'):
            self.db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[
                {'access_level':level,'status':'active'}]
            self.db.rpc.return_value.execute.side_effect=[SimpleNamespace(data=self.value),
                SimpleNamespace(data={**self.value,'mode':'human','connected':False,'route_to_ai':False,'control_version':3})]
            self.assertEqual(service.change_mode(self.ticket,mode='human',actor_id=self.actor)['mode'],'human')
            self.assertEqual(self.db.rpc.call_args.args[1]['p_actor_id'],self.actor)

    def test_stale_expected_version_never_writes(self):
        with self.assertRaises(service.ControlConflict):
            service.change_mode(self.ticket,mode='human',actor_id=self.actor,expected_version=1)
        self.assertEqual(self.db.rpc.call_count,1)

    def test_database_race_is_not_retried(self):
        error=RuntimeError('PRIVATE');error.code='PT409'
        self.db.rpc.return_value.execute.side_effect=[SimpleNamespace(data=self.value),error]
        with self.assertRaises(service.ControlConflict):service.change_mode(self.ticket,mode='human',actor_id=self.actor)
        self.assertEqual(self.db.rpc.call_count,2)

    def test_resume_requires_global_flag_and_open_window(self):
        for field in ['enabled','window_open']:
            value={**self.value,field:False}
            self.db.rpc.return_value.execute.return_value.data=value
            with self.assertRaises(ValueError):service.change_mode(self.ticket,mode='ai',actor_id=self.actor)
        self.assertEqual(self.db.rpc.call_count,2)


class CommercialAdapterTests(TestCase):
    def test_non_demo_enabled_adapter_reads_persistent_state(self):
        from app.services import automation_service as adapter
        with patch.object(adapter,'get_settings',return_value=SimpleNamespace(demo_mode=False,whatsapp_persistent_control_enabled=True)),\
             patch.object(adapter,'get_ai_settings',return_value={'assistant_name':'Dario'}),\
             patch.object(service,'read_control',return_value={'mode':'ai'}) as read:
            self.assertEqual(adapter.get_ticket_ai_control('ticket'),{'mode':'ai'})
            read.assert_called_once_with('ticket',assistant_name='Dario')

    def test_persistent_connect_uses_database_gate_instead_of_demo_setting(self):
        from app.services import automation_service as adapter
        with patch.object(adapter,'get_settings',return_value=SimpleNamespace(demo_mode=False,whatsapp_persistent_control_enabled=True)),\
             patch.object(adapter,'set_ticket_ai_mode',return_value={'mode':'ai'}) as change:
            adapter.connect_ticket_to_ai('ticket',actor_id='actor')
            self.assertEqual(change.call_args.kwargs['mode'],'ai')

    def test_persistent_messages_keep_ai_authorship_for_existing_template(self):
        from app.services import ticket_service as tickets
        db=MagicMock()
        rows=[{'id':'message','sender_id':None,'sender_kind':'ai','direction':'outbound','body':'Resposta','delivery_status':'read'}]
        chain=db.table.return_value
        chain.select.return_value.eq.return_value.order.return_value.execute.return_value.data=rows
        chain.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[]
        chain.select.return_value.in_.return_value.execute.return_value.data=[]
        with patch.object(tickets,'get_settings',return_value=SimpleNamespace(demo_mode=False,whatsapp_persistent_control_enabled=True)),\
             patch.object(tickets,'get_admin_client',return_value=db),\
             patch.object(tickets,'_profile_names',return_value={}),\
             patch.object(tickets,'_customer_rows',return_value={}),\
             patch.object(tickets,'list_attachments_for_messages',return_value={}):
            result=tickets.list_messages('ticket',{'id':'actor','role':'administrador'})
        self.assertEqual(result[0]['sender_kind'],'ai');self.assertEqual(result[0]['sender_name'],'Assistente de IA')
        self.assertEqual(result[0]['delivery_status'],'read')
