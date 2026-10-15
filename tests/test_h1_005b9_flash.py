"""H1-005B9 hotfix: aviso de sucesso visivel 1 vez; nunca reenvia POST.
Este teste nao chama nenhum banco nem servico externo.
"""
from pathlib import Path
import unittest
from jinja2 import Environment
ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'app/templates/staging/transport_contract.html'
SCRIPT = ROOT / 'app/static/js/staging-h1-005b9-flash.js'
ROUTE = ROOT / 'app/routers/staging_transport_contract.py'
class FlashAfterPRG(unittest.TestCase):
    def test_01_flash_trigger_and_script_are_conditional(self):
        content=TEMPLATE.read_text(encoding='utf-8')
        self.assertIn('{% if notice %}<div role="status"',content)
        self.assertIn('data-vendra-b9-flash',content)
        self.assertIn('staging-h1-005b9-flash.js',content)
        self.assertIn('Nenhum envio realizado.',content)
    def test_02_remove_only_one_shot_query_flag(self):
        content=SCRIPT.read_text(encoding='utf-8')
        self.assertIn("url.searchParams.delete('resultado')",content)
        self.assertIn("result !== 'preparado' && result !== 'alterado'",content)
        self.assertIn('history.replaceState',content)
        self.assertNotIn('history.pushState',content)
    def test_03_no_persistence_or_new_outbound_requests(self):
        content=SCRIPT.read_text(encoding='utf-8').lower()
        for forbidden in ('fetch(', 'xmlhttprequest', 'localstorage', 'sessionstorage', 'document.cookie', 'send_whatsapp', 'window.location.assign'):
            self.assertNotIn(forbidden,content)
    def test_04_backend_prg_unmodified(self):
        content=ROUTE.read_text(encoding='utf-8')
        self.assertIn("RedirectResponse('/disparos/contrato?resultado=preparado',status_code=303)",content)
        self.assertIn("RedirectResponse('/disparos/contrato?resultado=alterado',status_code=303)",content)
if __name__=='__main__': unittest.main()
