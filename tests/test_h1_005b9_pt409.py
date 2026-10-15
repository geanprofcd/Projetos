"""Regressao sem rede: fix PT409 e conservacao do contrato isolado."""
from pathlib import Path
import ast
import unittest
BASE=Path(__file__).resolve().parents[1]
ROUTER=BASE/'app/routers/staging_transport_contract.py'
SQL=BASE/'sql/03_CORRIGIR_PT409_STAGING.sql'

class H1B9PT409(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.router=ROUTER.read_text('utf-8')
        cls.sql=SQL.read_text('utf-8')
    def test_01_router_syntax(self): ast.parse(self.router)
    def test_02_conflict_status_new(self):
        self.assertIn("code == 'PT409'",self.router)
        self.assertIn('?aviso=conflito',self.router)
    def test_03_old_mapping_compatible(self):self.assertIn("code == '40001'",self.router)
    def test_04_fail_closed_retained(self):self.assertIn('return _offline_response(request,user,',self.router)
    def test_05_sql_target_only_staging(self):
        self.assertIn('staging_transport_contracts',self.sql)
        self.assertIn('vendra_staging_h1_005b8_transition',self.sql)
    def test_06_sql_guard_before_change(self):
        self.assertIn('to_regprocedure',self.sql)
        self.assertIn('EXECUTE v_new',self.sql)
        self.assertIn('Fila real nao vazia',self.sql)
    def test_07_sql_only_modify_functiondef(self):
        for forbidden in ('INSERT INTO public.dispatches','UPDATE public.dispatches','DELETE FROM public.dispatches',
                          'pg_terminate_backend', 'CREATE TABLE', 'DROP TABLE'):
            self.assertNotIn(forbidden,self.sql)
    def test_08_no_sender_or_token(self):
        self.assertNotIn('send_whatsapp',self.router)
        self.assertNotIn('make_webhook',self.router)
        self.assertNotIn('service_role_key',self.router)

if __name__=='__main__':unittest.main()
