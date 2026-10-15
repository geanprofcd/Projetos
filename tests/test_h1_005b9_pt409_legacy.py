"""Testes offline de regressao para RPCs historicas - sem credenciais reais."""
from pathlib import Path
import ast
import unittest
from types import SimpleNamespace

BASE=Path(__file__).resolve().parents[1]
CRM=BASE/'app/routers/staging_crm.py'
DISPATCH=BASE/'app/routers/staging_dispatch_lifecycle.py'
SQL=BASE/'sql/05_CORRIGIR_PT409_LEGADOS_SOMENTE_STAGING.sql'
CHECK=BASE/'sql/06_VALIDAR_PT409_LEGADOS_LEITURA.sql'

class LegacyPT409(unittest.TestCase):
    def test_01_syntax_crm(self): ast.parse(CRM.read_text('utf-8'))
    def test_02_syntax_simulations(self): ast.parse(DISPATCH.read_text('utf-8'))
    def test_03_sql_staging_guard(self):
        s=SQL.read_text('utf-8')
        for v in ('staging_transport_contracts','staging_dispatch_simulations','opportunity_stage_history','Filas reais nao estao vazias','BEGIN;','COMMIT;'):
            self.assertIn(v,s)
    def test_04_sql_only_two_rpcs(self):
        s=SQL.read_text('utf-8')
        for rpc in ('vendra_staging_move_opportunity','vendra_staging_change_dispatch_simulation'):
            self.assertIn(rpc,s)
        self.assertIn("v_old_code constant text",s)
        self.assertIn("v_new_code constant text",s)
    def test_05_sql_excludes_real_transport_and_os(self):
        s=SQL.read_text('utf-8')
        for bad in ('INSERT INTO public.dispatches','UPDATE public.whatsapp_outbox','DELETE FROM public.messages','pg_terminate_backend','DROP TABLE','CREATE TABLE','http_post'):
            self.assertNotIn(bad,s)
    def test_06_validation_has_both_rpcs(self):
        s=CHECK.read_text('utf-8')
        for label in ('crm_pt409','crm_40001_antigo','simulacoes_pt409','simulacoes_40001_antigo'):
            self.assertIn(label,s)
    def test_07_crm_pt409_mapped(self):
        from app.routers import staging_crm
        e=SimpleNamespace(code='PT409',args=())
        self.assertIn('alterou',staging_crm._problem(e))
    def test_08_crm_unknown_never_leaks(self):
        from app.routers import staging_crm
        e=SimpleNamespace(code='XX999',args=('SEGREDO-INTERNO',))
        self.assertNotIn('SEGREDO',staging_crm._problem(e))
    def test_09_dispatch_pt409_mapped(self):
        from app.routers import staging_dispatch_lifecycle as d
        msg,status=d._state_error(SimpleNamespace(code='PT409',args=()))
        self.assertEqual(status,409)
        self.assertIn('Outra aba',msg)
    def test_10_dispatch_other_errors_fail_closed(self):
        from app.routers import staging_dispatch_lifecycle as d
        msg,status=d._state_error(SimpleNamespace(code='XX999',args=('SEGREDO-INTERNO',)))
        self.assertEqual(status,503)
        self.assertNotIn('SEGREDO',msg)
    def test_11_dispatch_invalid_transition(self):
        from app.routers import staging_dispatch_lifecycle as d
        self.assertEqual(d._state_error(SimpleNamespace(code='22023',args=()))[1],422)
    def test_12_dispatch_permission_denied(self):
        from app.routers import staging_dispatch_lifecycle as d
        self.assertEqual(d._state_error(SimpleNamespace(code='42501',args=()))[1],403)
    def test_13_crm_existing_40001_compatible(self):
        from app.routers import staging_crm
        self.assertIn('alterou',staging_crm._problem(SimpleNamespace(code='40001',args=())))
    def test_14_no_new_external_transport(self):
        for file in (CRM,DISPATCH):
            s=file.read_text('utf-8').lower()
            self.assertNotIn('httpx.post',s)
            self.assertNotIn('requests.post',s)
            self.assertNotIn('make_webhook',s)

if __name__=='__main__': unittest.main()
