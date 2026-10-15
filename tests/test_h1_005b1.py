import ast
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from tools.preflight_staging import validate_config

class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.env={'APP_ENV':'staging','DEMO_MODE':'false','SUPABASE_URL':'https://abc123.supabase.co','VENDRA_STAGING_REF':'abc123','SUPABASE_ANON_KEY':'test_key','SUPABASE_SERVICE_ROLE_KEY':'test_secret','SECRET_KEY':'test_session'}
    def test_valid_staging(self):self.assertEqual(validate_config(self.env),[])
    def test_wrong_project(self):
        self.env['SUPABASE_URL']='https://production.supabase.co'
        self.assertTrue(validate_config(self.env))
    def test_wrong_url_path(self):
        self.env['SUPABASE_URL']+='/rest/v1/'
        self.assertTrue(validate_config(self.env))
    def test_demo_is_not_target(self):
        self.env['DEMO_MODE']='true'
        self.assertTrue(validate_config(self.env))
    def test_sources_parse(self):
        for p in root.rglob('*.py'):ast.parse(p.read_text(encoding='utf8'),filename=str(p))
    def test_no_staging_query_to_farms(self):
        code=(root/'app/services/customer_service.py').read_text()
        self.assertNotIn('table("farms")',code)
        for filename in ('ticket_service.py','metadata_service.py'):
            code=(root/'app/services'/filename).read_text()
            self.assertNotIn('table("farms")',code)
            self.assertNotIn('table("crops")',code)
            self.assertNotIn('table("categories")',code)
    def test_list_customers_real_mode_avoids_farms(self):
        import importlib.util
        import types
        from types import SimpleNamespace
        fake_admin=Mock()
        fake_admin.table.return_value.select.return_value.order.return_value.execute.return_value.data=[{'id':'1','name':'Cliente teste','status':'active'}]
        modnames=['app','app.core','app.core.config','app.db','app.db.supabase','app.services','app.services.demo_store']
        mods={n:types.ModuleType(n) for n in modnames}
        mods['app.core.config'].get_settings=lambda: SimpleNamespace(demo_mode=False)
        mods['app.db.supabase'].get_admin_client=lambda: fake_admin
        mods['app.services.demo_store'].DEMO_CUSTOMERS=[]
        mods['app.services.demo_store'].DEMO_FARMS=[]
        mods['app.services.demo_store'].new_id=lambda _: 'demo-id'
        with patch.dict(sys.modules,mods):
            spec=importlib.util.spec_from_file_location('customer_module_test',root/'app/services/customer_service.py')
            svc=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(svc)
            rows=svc.list_customers()
        self.assertEqual(rows[0]['name'],'Cliente teste')
        self.assertEqual(rows[0]['farm_count'],0)
        fake_admin.table.assert_called_once_with('customers')
    def test_template_parses(self):
        from jinja2 import Environment
        for p in (root/'app/templates/customers').glob('*.html'):
            Environment().parse(p.read_text(encoding='utf8'))
    def test_customer_template_complete(self):
        template=(root/'app/templates/customers/detail.html').read_text()
        self.assertIn('{% block content %}',template)
        self.assertIn('{% endblock %}',template)

if __name__=='__main__':unittest.main()
