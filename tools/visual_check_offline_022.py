import sys,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from app.services.local_credentials_service import demo_admin_credentials
from fastapi.testclient import TestClient
from app.main import app
from playwright.sync_api import sync_playwright
client=TestClient(app)
creds=demo_admin_credentials()
client.post('/login',data={'email':creds['email'],'password':creds['password']})
html=client.get('/atendimentos/1548').text
html=re.sub(r'<link rel="stylesheet" href="/static/css/[^\"]+">','',html)
html=re.sub(r'<script src="/static/js/[^\"]+"></script>','',html)
css='\n'.join(p.read_text() for p in sorted((root/'app/static/css').glob('*.css')))
html=html.replace('</head>',f'<style>{css}</style></head>')
js=(root/'app/static/js/meta-templates-v0.0.22.js').read_text()
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    for w,h in [(1600,1000),(1366,900),(1024,768),(390,844)]:
        page=browser.new_page(viewport={'width':w,'height':h},device_scale_factor=1)
        page.set_content(html,wait_until='domcontentloaded')
        page.add_script_tag(content=js)
        page.locator('[data-open-template-modal]').click()
        rect=page.locator('.template-dialog').bounding_box()
        viewport=(rect['x']>=0 and rect['x']+rect['width']<=w+2 and rect['y']>=0 and rect['y']+rect['height']<=h+2)
        print(f'{w}x{h}: modal visible and within viewport:',viewport)
        assert viewport
        page.screenshot(path=str(root/'docs'/f'ui_template_{w}.png'),full_page=False)
        page.close()
    browser.close()
