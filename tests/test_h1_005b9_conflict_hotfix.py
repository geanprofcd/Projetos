"""B9 conflict hotfix: offline contract checks, no DB traffic."""
from pathlib import Path
import ast
import unittest
ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT/'app/routers/staging_transport_contract.py'
HTML = ROOT/'app/templates/staging/transport_contract.html'
JS = ROOT/'app/static/js/staging-h1-005b9-flash.js'
class H1B9ConflictHotfix(unittest.TestCase):
    def test_01_python_syntax(self): ast.parse(ROUTER.read_text('utf-8'))
    def test_02_sqlstate_exact_mapping(self):
        s=ROUTER.read_text('utf-8')
        for code,name in [('40001','conflito'),('22023','estado'),('42501','permissao')]:
            self.assertIn("code == '%s'" % code,s)
            self.assertIn('?aviso='+name,s)
    def test_03_no_raw_error_exposure(self):
        s=ROUTER.read_text('utf-8')
        self.assertNotIn('detail=str(exc)',s)
        self.assertIn('return _offline_response(request,user,',s)
    def test_04_known_conflict_does_not_retry_post(self):
        s=ROUTER.read_text('utf-8')
        self.assertIn("?aviso=conflito',status_code=303",s)
    def test_05_unavailable_fail_closed(self):
        s=ROUTER.read_text('utf-8')
        self.assertIn("'items':[], 'candidates':[], 'status':None",s)
        self.assertIn('status_code=503',s)
    def test_06_warning_is_escaped_and_single_use(self):
        s=HTML.read_text('utf-8')
        self.assertIn('{{ warning }}',s)
        self.assertNotIn('{{ warning | safe }}',s)
        self.assertIn('data-vendra-b9-flash',s)
    def test_07_url_cleared_without_post(self):
        s=JS.read_text('utf-8')
        self.assertIn("url.searchParams.delete('aviso')",s)
        self.assertIn('history.replaceState',s)
        for name in ['fetch(', 'XMLHttpRequest', 'localStorage', 'sessionStorage']:
            self.assertNotIn(name,s)
    def test_08_real_queue_paths_untouched(self):
        s=ROUTER.read_text('utf-8')
        for term in ['send_whatsapp','claim_whatsapp_outbox','/webhooks/make','/webhooks/meta']:
            self.assertNotIn(term,s)
    def test_09_code_has_no_secret_or_raw_sql(self):
        s=ROUTER.read_text('utf-8')
        self.assertNotIn('service_role_key',s)
        self.assertNotIn('execute_sql',s)
    def test_10_prg_remains_for_success(self):
        s=ROUTER.read_text('utf-8')
        self.assertIn("?resultado=alterado',status_code=303",s)
if __name__=='__main__':unittest.main()
