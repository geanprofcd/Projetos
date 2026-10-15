"""Smoke isolado sem dependencias VENDRA; execute via python tests/smoke_isolado.py.
NAO conecta bancos nem redes. Executa testes sobre service com stubs.
"""
import hashlib
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

root=Path(__file__).resolve().parents[1]
mod_path=root/'app/services/staging_dispatch_lifecycle_service.py'
modules=['app','app.db','app.db.supabase','app.services','app.services.staging_dispatch_preview_service']
for name in modules:
    module=types.ModuleType(name)
    module.__path__=[]
    sys.modules[name]=module

opp=str(uuid4());cust=str(uuid4());fun=str(uuid4());stage=str(uuid4());actor=str(uuid4());sim=str(uuid4())
dictionary={
'opportunities':{'id':opp,'customer_id':cust,'funnel_id':fun,'stage_id':stage,'title':'Teste H1', 'status':'open','archived_at':None},
'customers':{'id':cust,'name':'Maria','company_name':'Empresa','status':'active','phone_normalized':'5511999999999'},
'sales_funnels':{'id':fun,'name':'Funil'},
'funnel_stages':{'id':stage,'funnel_id':fun,'name':'Novo'}
}
preview=sys.modules['app.services.staging_dispatch_preview_service']
preview._get=lambda table,id: dictionary.get(table)
preview._phone_mask=lambda raw: (True,'•••• '+raw[-4:]) if len(raw)>=10 else (False,'Inválido')
preview._render=lambda text,values: text.replace('{{nome}}',values['name'])
class DummyExec:
  def __init__(self,data):self.data=data
  def execute(self):return self
class DummyDB:
  def __init__(self):self.calls=[]
  def rpc(self,method,payload):
    self.calls.append((method,payload))
    return DummyExec(sim if method=='vendra_staging_prepare_dispatch' else 2)
  def table(self,table):raise AssertionError('Tabelas de envio nao devem ser acessadas: '+table)
db=DummyDB()
sys.modules['app.db.supabase'].get_admin_client=lambda:db
spec=importlib.util.spec_from_file_location('app.services.staging_dispatch_lifecycle_service',mod_path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
# 1. Solicitar simulacao apenas por RPC de staging.
a=module.prepare_simulation(opportunity_id=opp,content='Ola {{nome}}',actor_id=actor)
assert a['message']=='Ola Maria' and a['sent'] is False and a['queued'] is False
assert db.calls[-1][0]=='vendra_staging_prepare_dispatch'
assert db.calls[-1][1]['p_fingerprint']==hashlib.sha256(b'Ola Maria').hexdigest()
# 2. Simular falha pelo unico RPC permitido.
assert module.change_state(simulation_id=sim,action='simulate_failure',lock_version=1,actor_id=actor)==2
assert db.calls[-1][0]=='vendra_staging_change_dispatch_simulation'
# 3. Bloqueio de envio externo.
try:module.change_state(simulation_id=sim,action='send_whatsapp',lock_version=1,actor_id=actor)
except ValueError:pass
else:raise AssertionError('acao de envio externo nao bloqueada')
# 4. Sem operacao com versao antiga.
try:module.change_state(simulation_id=sim,action='retry',lock_version=0,actor_id=actor)
except ValueError:pass
else:raise AssertionError('versao zero aceita')
# 5. Oportunidade encerrada nao aceita.
original=dictionary['opportunities'];dictionary['opportunities']={**original,'status':'won'}
try:module.prepare_simulation(opportunity_id=opp,content='Teste',actor_id=actor)
except ValueError:pass
else:raise AssertionError('oportunidade encerrada aceita')
dictionary['opportunities']=original
# 6. Validar UUID.
try:module.prepare_simulation(opportunity_id='invalido',content='Teste',actor_id=actor)
except ValueError:pass
else:raise AssertionError('UUID invalido aceito')
# 7. Nenhuma gravacao em filas reais; apenas RPCs nomeados.
assert set(name for name,_ in db.calls) <= {'vendra_staging_prepare_dispatch','vendra_staging_change_dispatch_simulation'}
print('Smoke isolado: 7 verificacoes OK (sem banco real, sem web).')
