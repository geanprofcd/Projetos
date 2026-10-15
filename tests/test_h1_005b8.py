"""H1-005B8: suite OFFLINE; asserta inexistencia de chamadas externas ou filas reais.

Concorrencia nesta suite e MOCKADA (thread-safe fake). Verificar SQL real
separadamente no STAGING para homologar concorrencia no PostgreSQL.
"""
from __future__ import annotations
import hashlib
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

os.environ.update({
    'APP_ENV':'staging', 'DEMO_MODE':'false',
    'VENDRA_STAGING_REF':'exampletest123',
    'SUPABASE_URL':'https://exampletest123.supabase.co',
    'SUPABASE_ANON_KEY':'sb_publishable_mock_for_unit_test_123456789',
    'SUPABASE_SERVICE_ROLE_KEY':'sb_secret_mock_for_unit_test_123456789',
    'SECRET_KEY':'session-secret-unit-test-very-long',
    'META_ACCESS_TOKEN':'','MAKE_WEBHOOK_SECRET':'','SMTP_HOST':'',
})
from app.services import staging_transport_contract_service as svc
from app.services import staging_delivery_preflight_service as preflight

ORIGINAL_REQUIRE = svc.require_clean_staging
OPP, ACTOR = str(uuid4()), str(uuid4())


class RpcCall:
    def __init__(self,fake,name,params):self.fake=fake;self.name=name;self.params=params
    def execute(self):
        return SimpleNamespace(data=self.fake._rpc(self.name,self.params))

class Query:
    def __init__(self,fake,table):self.fake=fake;self.table=table;self.n=40;self.target=None
    def select(self,*args,**kwargs):return self
    def order(self,*args,**kwargs):return self
    def limit(self,n):self.n=n;return self
    def eq(self,name,value):self.target=(name,value);return self
    def execute(self):
        if self.table=='staging_transport_contracts': rows=list(self.fake.data.values())
        elif self.table=='staging_transport_events': rows=self.fake.events[:]
        else:raise AssertionError('Leitura em tabela nao permitida: '+self.table)
        if self.target:rows=[r for r in rows if str(r.get(self.target[0]))==str(self.target[1])]
        return SimpleNamespace(data=rows[:self.n])
    def insert(self,*_):raise AssertionError('Insert direto proibido')

class FakeDb:
    def __init__(self):
        self.lock=threading.Lock();self.data={};self.events=[];self.calls=[]
    def table(self,name):
        if name not in ('staging_transport_contracts','staging_transport_events'):
            raise AssertionError('Tabela real nao permitida: '+name)
        return Query(self,name)
    def rpc(self,name,params):
        self.calls.append(name)
        if not name.startswith('vendra_staging_h1_005b8_'):
            raise AssertionError('RPC de envio real proibida: '+name)
        return RpcCall(self,name,params)
    def _rpc(self,name,p):
        with self.lock:
            if name.endswith('_prepare'):
                k=p['p_opportunity_id']+'-'+p['p_fingerprint']
                created=k not in self.data
                if created:
                    v={'id':str(uuid4()),'opportunity_id':p['p_opportunity_id'],
                       'fingerprint':p['p_fingerprint'],'state':'blocked',
                       'lock_version':1,'attempt_count':0,'created_at':'2026-10-13',
                       'last_failure_code':None,'lease_until':None}
                    self.data[k]=v
                    self.events.append({'contract_id':v['id'],'action':'prepare'})
                else:v=self.data[k]
                return {'id':v['id'],'created':created,'state':v['state']}
            if name.endswith('_transition'):
                v=next((r for r in self.data.values() if r['id']==p['p_contract_id']),None)
                if v is None:raise ValueError('Contrato inexistente')
                if v['lock_version']!=p['p_expected_version']:raise ValueError('Versao divergente')
                a=p['p_action']; s=v['state']; cnt=v['attempt_count']
                if a=='lease' and s=='blocked' and cnt<3: v['state']='leased';v['attempt_count']+=1
                elif a=='fail' and s=='leased':v['state']='dead_letter' if cnt==3 else 'failed'
                elif a=='retry' and s=='failed':v['state']='blocked'
                elif a=='validate_no_send' and s=='leased':v['state']='validated'
                elif a=='cancel' and s in ('blocked','failed'):v['state']='cancelled'
                else:raise ValueError('Transicao proibida')
                v['lock_version']+=1;self.events.append({'contract_id':v['id'],'action':a})
                return {'id':v['id'],'state':v['state'],'lock_version':v['lock_version']}
            raise AssertionError('RPC invalida')

class H1005B8(unittest.TestCase):
    def setUp(self):
        self.db=FakeDb()
        self.db_patch=patch.object(svc,'get_admin_client',return_value=self.db)
        self.db_patch.start()
        self.guard_patch=patch.object(svc,'require_clean_staging',return_value={'real_queue_clean':True})
        self.guard_patch.start()
        self.plan_patch=patch.object(preflight,'make_plan',return_value={'rendered_message':'Oi, Teste!',
            'phone_masked':'•••• 6094'})
        self.plan_patch.start()
    def tearDown(self):
        self.plan_patch.stop();self.guard_patch.stop();self.db_patch.stop()
    def prepare(self):return svc.prepare_contract(opportunity_id=OPP,content='Oi, {{nome}}!',actor_id=ACTOR)
    def test_01_initial_blocked_no_send(self):
        r=self.prepare();self.assertTrue(r['created']);self.assertEqual(r['state'],'blocked')
        self.assertFalse(r['sent']);self.assertFalse(r['queued'])
    def test_02_same_content_idempotent(self):
        a=self.prepare();b=self.prepare();self.assertEqual(a['id'],b['id']);self.assertFalse(b['created'])
        self.assertEqual(len(self.db.events),1)
    def test_03_change_content_diff_fingerprint(self):
        a=self.prepare()
        with patch.object(preflight,'make_plan',return_value={'rendered_message':'Outro texto','phone_masked':'•••• 6094'}):
            b=self.prepare()
        self.assertNotEqual(a['id'],b['id']);self.assertNotEqual(a['reference'],b['reference'])
    def test_04_20_concurrent_requests_simulated(self):
        with ThreadPoolExecutor(max_workers=12) as pool: results=list(pool.map(lambda _:self.prepare(),range(20)))
        self.assertEqual(len(set(r['id'] for r in results)),1)
        self.assertEqual(sum(bool(r['created']) for r in results),1)
    def test_05_lease_is_not_real_send(self):
        c=self.prepare()
        r=svc.change_contract(contract_id=c['id'],action='lease',lock_version=1,actor_id=ACTOR)
        self.assertEqual(r['state'],'leased');self.assertNotIn('claim_whatsapp_outbox',self.db.calls)
    def test_06_validation_is_not_delivery(self):
        c=self.prepare();svc.change_contract(contract_id=c['id'],action='lease',lock_version=1,actor_id=ACTOR)
        r=svc.change_contract(contract_id=c['id'],action='validate_no_send',lock_version=2,actor_id=ACTOR)
        self.assertEqual(r['state'],'validated')
    def test_07_stale_version_rejected(self):
        c=self.prepare();svc.change_contract(contract_id=c['id'],action='lease',lock_version=1,actor_id=ACTOR)
        with self.assertRaises(ValueError):svc.change_contract(contract_id=c['id'],action='fail',lock_version=1,actor_id=ACTOR)
    def test_08_fail_retry_and_dead_letter(self):
        c=self.prepare();version=1
        for i in range(3):
            a=svc.change_contract(contract_id=c['id'],action='lease',lock_version=version,actor_id=ACTOR);version=a['lock_version']
            a=svc.change_contract(contract_id=c['id'],action='fail',lock_version=version,actor_id=ACTOR);version=a['lock_version']
            if i<2:
                self.assertEqual(a['state'],'failed')
                a=svc.change_contract(contract_id=c['id'],action='retry',lock_version=version,actor_id=ACTOR);version=a['lock_version']
            else:self.assertEqual(a['state'],'dead_letter')
        self.assertEqual(len(self.db.events),9)
    def test_09_cancel(self):
        c=self.prepare();r=svc.change_contract(contract_id=c['id'],action='cancel',lock_version=1,actor_id=ACTOR)
        self.assertEqual(r['state'],'cancelled')
    def test_10_invalid_action(self):
        c=self.prepare()
        with self.assertRaises(ValueError):svc.change_contract(contract_id=c['id'],action='send',lock_version=1,actor_id=ACTOR)
    def test_11_invalid_uuid(self):
        with self.assertRaises(ValueError):svc.prepare_contract(opportunity_id='abc',content='abc',actor_id=ACTOR)
    def test_12_invalid_actor(self):
        with self.assertRaises(ValueError):svc.prepare_contract(opportunity_id=OPP,content='abc',actor_id='x')
    def test_13_bad_version(self):
        with self.assertRaises(ValueError):svc.change_contract(contract_id=str(uuid4()),action='lease',lock_version=0,actor_id=ACTOR)
    def test_14_real_queue_not_clean(self):
        with patch.object(svc,'require_clean_staging',side_effect=ValueError('filas reais')):
            with self.assertRaises(ValueError):self.prepare()
    def test_15_failed_preflight_prevents_rpc(self):
        with patch.object(preflight,'make_plan',side_effect=ValueError('oportunidade fechada')):
            with self.assertRaises(ValueError):self.prepare()
        self.assertFalse(self.db.calls)
    def test_16_staging_guard_rejects_prod(self):
        with patch.dict(os.environ,{'APP_ENV':'production'}), patch.object(svc,'require_clean_staging',side_effect=ORIGINAL_REQUIRE):
            with self.assertRaises(RuntimeError):svc.require_clean_staging()
    def test_17_no_phone_or_body_persisted(self):
        self.prepare();raw=repr(self.db.data)+repr(self.db.events)
        self.assertNotIn('6094',raw);self.assertNotIn('Oi, Teste!',raw)
    def test_18_allowed_rpc_and_table_only(self):
        self.prepare()
        with patch.object(svc.preview,'_get',return_value={'title':'Oportunidade teste'}):
            svc.list_contracts()
        self.assertEqual(set(self.db.calls),{'vendra_staging_h1_005b8_prepare'})
    def test_19_events_scoped(self):
        c=self.prepare();rows=svc.read_events(c['id']);self.assertEqual(len(rows),1)
    def test_20_hash_matches_h1_005b7(self):
        self.assertEqual(self.prepare()['reference'],hashlib.sha256((OPP+'\n'+'Oi, Teste!').encode()).hexdigest()[:16])
    def test_21_sql_never_changes_real_tables(self):
        sql=(Path(__file__).resolve().parents[1]/'sql'/'01_APLICAR_H1_005B8_SOMENTE_STAGING.sql').read_text()
        import re
        self.assertIsNone(re.search(r'\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|TRUNCATE|ALTER\s+TABLE|DROP\s+TABLE)\s+(?:public\.)?(?:dispatches|whatsapp_outbox|messages)\b',sql,re.I))
        self.assertIn('UNIQUE(opportunity_id,fingerprint)',sql)
        self.assertIn('FOR UPDATE',sql)
        self.assertIn('SECURITY INVOKER',sql)
        self.assertIn('CHECK(transport_enabled=false)',sql)
        self.assertIn('ENABLE ROW LEVEL SECURITY',sql)
    def test_22_runtime_points_new_isolated_module(self):
        text=(Path(__file__).resolve().parents[1]/'tools'/'staging_start.py').read_text()
        self.assertRegex(text,r'staging_h1_005b(?:8|9):app')
        self.assertNotIn('app.main:app',text)
    def test_23_cannot_transition_terminal(self):
        c=self.prepare();svc.change_contract(contract_id=c['id'],action='cancel',lock_version=1,actor_id=ACTOR)
        with self.assertRaises(ValueError):svc.change_contract(contract_id=c['id'],action='lease',lock_version=2,actor_id=ACTOR)

if __name__=='__main__':unittest.main()
