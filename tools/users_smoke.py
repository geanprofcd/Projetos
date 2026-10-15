"""Smoke demo isolado da base do usuário (não usa credenciais de e-mail real)."""
from __future__ import annotations
import os
import re
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

with tempfile.TemporaryDirectory(prefix='vendra-users-smoke-') as temp:
    os.environ['VENDRA_DEMO_STATE_FILE'] = str(Path(temp)/'demo_state.json')
    os.environ['VENDRA_LOCAL_CONFIG'] = str(Path(temp)/'local_credentials.json')
    os.environ['DEMO_MODE'] = 'true'
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.auth_service import csrf_token_for_session
    from app.services.demo_store import DEMO_INTERNAL_USERS
    from app.services.access_service import allowed, level_for

    client = TestClient(app)
    login = client.post('/login',data={'email':'admin@demo.local','password':'admin123'},follow_redirects=False)
    assert login.status_code == 303, f'login: {login.status_code}'
    token=csrf_token_for_session(client.cookies['vendra_session'])
    assert client.get('/usuarios').status_code == 200
    assert client.post('/usuarios/convidar',data={'full_name':'A Pessoa','email':'a@example.org','access_level':'comum','csrf_token':'invalid'}).status_code==403
    for role in ('comum','comercial','gerencial','administrativo'):
        email=f'{role}@example.org'
        page=client.post('/usuarios/convidar',data={'full_name':f'Perfil {role}','email':email,'access_level':role,'csrf_token':token})
        assert page.status_code==200,(role,page.status_code,page.text[:300])
        url=re.search(r'href="(http://127\.0\.0\.1:8010/convite/[^" ]+)"',page.text)
        assert url,role
        path='/convite/'+url.group(1).rsplit('/',1)[-1]
        assert client.get(path).status_code==200
        assert client.post(path,data={'password':'curta','confirm_password':'curta'}).status_code==422
        assert client.post(path,data={'password':'SenhaForte#2026Permissoes','confirm_password':'SenhaForte#2026Permissoes'},follow_redirects=False).status_code==303
        assert client.get(path).text.count('Convite indisponível')==1
        user=next(p for p in DEMO_INTERNAL_USERS if p.get('email')==email)
        assert level_for(user)==role
        browser=TestClient(app)
        assert browser.post('/login',data={'email':email,'password':'SenhaForte#2026Permissoes'},follow_redirects=False).status_code==303
        expected={'comum':(403,403,403,403), 'comercial':(200,403,403,403), 'gerencial':(200,200,403,403), 'administrativo':(200,200,200,200)}[role]
        observed=tuple(browser.get(path).status_code for path in ('/atendimentos','/indicadores','/configuracoes','/usuarios'))
        assert observed == expected, (role,observed,expected)
        if role=='comum':
            assert '/atendimentos' not in browser.get('/').text
        print(role,'=>',observed)
    new_user=next(p for p in DEMO_INTERNAL_USERS if p.get('email')=='comercial@example.org')
    user_id=new_user['id']
    assert client.post(f'/usuarios/{user_id}/permissoes',data={'access_level':'gerencial','csrf_token':token},follow_redirects=False).status_code==303
    assert new_user['access_level']=='gerencial'
    assert client.post(f'/usuarios/{user_id}/permissoes',data={'access_level':'comercial','can_manage_users':'true','csrf_token':token},follow_redirects=False).status_code==303
    assert allowed(new_user,'usuarios')
    browser=TestClient(app)
    assert browser.post('/login',data={'email':'comercial@example.org','password':'SenhaForte#2026Permissoes'},follow_redirects=False).status_code==303
    delegate_csrf=csrf_token_for_session(browser.cookies['vendra_session'])
    assert browser.get('/usuarios').status_code==200
    assert browser.post('/usuarios/convidar',data={'full_name':'Sem Elevacao','email':'elevacao@example.org','access_level':'administrativo','csrf_token':delegate_csrf}).status_code==422
    assert browser.post(f'/usuarios/{user_id}/permissoes',data={'access_level':'administrativo','csrf_token':delegate_csrf}).status_code==403
    with open('app/templates/tickets/detail.html',encoding='utf8') as f:
        src=f.read()
    for key in ('<dt>Propriedade</dt>', '<dt>Cultura</dt>', '<dt>Categoria</dt>'):
        assert key not in src
    assert client.get('/atendimentos/1548').status_code == 200
    print('CONVITE, SESSAO, QUATRO PERFIS, DELEGACAO, CSRF E UI: OK')
