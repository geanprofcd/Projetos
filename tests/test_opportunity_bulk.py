from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from app.services import opportunity_service as service


class Query:
    def __init__(self,db,name):self.db=db;self.name=name;self.filters=[];self.offset=0;self.size=1000;self.sort=None
    def select(self,*a):return self
    def is_(self,key,value):self.filters.append(lambda row:row.get(key) is None);return self
    def eq(self,key,value):self.filters.append(lambda row:row.get(key)==value);return self
    def gt(self,key,value):self.filters.append(lambda row:row.get(key)>value);return self
    def in_(self,key,values):self.filters.append(lambda row:row.get(key) in values);return self
    def order(self,key,*a,**kw):self.sort=key;return self
    def limit(self,count):self.size=count;return self
    def range(self,start,end):self.offset=start;self.size=end-start+1;return self
    def execute(self):
        self.db.calls.append(self.name)
        rows=[dict(row) for row in self.db.rows[self.name] if all(f(row) for f in self.filters)]
        if self.sort:rows.sort(key=lambda row:row.get(self.sort))
        return SimpleNamespace(data=rows[self.offset:self.offset+self.size])


class Database:
    def __init__(self,count):
        self.calls=[]
        opportunities=[dict(id=f'00000000-0000-0000-0000-{i:012d}',customer_id='customer',funnel_id='funnel',stage_id='stage',assigned_user_id='active',title=f'Card {i}',status='open',archived_at=None,updated_at='2026-10-19',calculated_value='123.45') for i in range(count)]
        self.rows={'opportunities':opportunities,'customers':[{'id':'customer','name':'Cliente atual'}],
            'tickets':[],'sales_funnels':[{'id':'funnel','name':'Comercial'}],
            'funnel_stages':[{'id':'stage','name':'Qualificação','color':'#3157d5'}],
            'opportunity_items':[{'id':row['id'],'opportunity_id':row['id']} for row in opportunities]}
    def table(self,name):return Query(self,name)


class OpportunityBulkTests(TestCase):
    def setUp(self):
        self.db=Database(1001)
        self.enterContext(patch.object(service,'get_settings',return_value=SimpleNamespace(demo_mode=False)))
        self.enterContext(patch.object(service,'get_admin_client',return_value=self.db))
        self.users=self.enterContext(patch.object(service,'list_internal_users',return_value=[{'id':'active','full_name':'Comercial'}]))
        self.enterContext(patch.object(service,'list_lost_reasons',return_value=[]))
    def test_over_one_page_without_truncation_or_per_card_queries(self):
        rows=service.list_opportunities(status='open',funnel_id='funnel')
        self.assertEqual(len(rows),1001)
        self.assertEqual(sum(row['item_count'] for row in rows),1001)
        self.assertLess(len(self.db.calls),25)
        self.assertEqual(self.db.calls.count('opportunities'),2)
        self.assertEqual(rows[0]['customer_name'],'Cliente atual')
        self.assertEqual(rows[0]['stage_name'],'Qualificação')
        self.assertEqual(rows[0]['assigned_name'],'Comercial')
        self.users.assert_called_once_with(active_only=True)
    def test_filters_exclude_archived_and_other_funnel_before_decoration(self):
        self.db.rows['opportunities'][0]['archived_at']='2026-10-19'
        self.db.rows['opportunities'][1]['funnel_id']='other'
        self.db.rows['opportunities'][2]['status']='lost'
        rows=service.list_opportunities(status='open',funnel_id='funnel')
        self.assertEqual(len(rows),998)
        self.assertTrue(all(row['status']=='open' and row['funnel_id']=='funnel' and row['archived_at'] is None for row in rows))
    def test_next_request_sees_renamed_customer_and_changed_assignee(self):
        first=service.list_opportunities(customer_id='customer')
        self.db.rows['customers'][0]['name']='Nome novo'
        self.users.return_value=[]
        second=service.list_opportunities(customer_id='customer')
        self.assertEqual(first[0]['customer_name'],'Cliente atual')
        self.assertEqual(second[0]['customer_name'],'Nome novo')
        self.assertEqual(second[0]['assigned_name'],'Sem responsável')
