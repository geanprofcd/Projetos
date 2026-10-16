import unittest
from unittest.mock import patch
from types import SimpleNamespace
from uuid import uuid4
import httpx
from datetime import datetime,timezone
from app.services.conversation_order_service import activity_key
from app.services.ticket_attention_service import summarize_ticket
from app.services import conversation_order_service as service

class ConversationOrderTests(unittest.TestCase):
    def test_rpc_get_accepts_optional_customer_filter(self):
        from supabase import create_client
        from supabase.lib.client_options import SyncClientOptions
        requests=[]
        def handle(request):
            requests.append(request)
            return httpx.Response(200,json=[])
        with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
            db=create_client('https://database.test','sb_secret_'+'x'*40,options=SyncClientOptions(httpx_client=transport,persist_session=False,auto_refresh_token=False))
            with patch.object(service,'get_settings',return_value=SimpleNamespace(demo_mode=False)),patch.object(service,'get_admin_client',return_value=db):
                self.assertEqual(service.list_ticket_rows(),[])
                customer=str(uuid4());self.assertEqual(service.list_ticket_rows(customer_ids=[customer]),[])
        self.assertEqual(requests[0].method,'GET')
        self.assertNotIn('p_customer_ids',requests[0].url.params)
        self.assertEqual(requests[1].url.params['p_customer_ids'],'{'+customer+'}')

    def test_inbound_priority_and_recency(self):
        rows=[{'id':'out','last_direction':'outbound','last_activity_at':'2026-10-16T12:03:00Z'},
              {'id':'in-old','last_direction':'inbound','last_activity_at':'2026-10-16T12:01:00Z'},
              {'id':'in-new','last_direction':'inbound','last_activity_at':'2026-10-16T12:02:00Z'}]
        self.assertEqual([r['id'] for r in sorted(rows,key=lambda r:activity_key(r,r),reverse=True)],['in-new','in-old','out'])

    def test_note_and_unsent_message_do_not_hide_inbound(self):
        msgs=[{'id':'1','direction':'inbound','created_at':'2026-10-16T12:00:00Z'},
              {'id':'2','direction':'outbound','is_internal':True,'created_at':'2026-10-16T12:01:00Z'},
              {'id':'3','direction':'outbound','delivery_status':'pending','created_at':'2026-10-16T12:02:00Z'}]
        result=summarize_ticket({'id':'t'},msgs,now=datetime(2026,10,16,13,tzinfo=timezone.utc))
        self.assertEqual(result['last_direction'],'inbound')
        self.assertEqual(result['last_activity_at'],'2026-10-16T12:00:00+00:00')

    def test_timestamp_tie_prioritizes_received(self):
        msgs=[{'id':'a','direction':'inbound','created_at':'2026-10-16T12:00:00Z'},
              {'id':'z','direction':'outbound','delivery_status':'sent','created_at':'2026-10-16T12:00:00Z'}]
        self.assertEqual(summarize_ticket({'id':'t'},msgs,now=datetime(2026,10,16,13,tzinfo=timezone.utc))['last_direction'],'inbound')
