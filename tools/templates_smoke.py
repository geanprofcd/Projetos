"""Smoke de contratos da UI e Graph simulado, sem rede/credenciais reais."""
from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import csrf_token_for_session,COOKIE_NAME
from app.services.local_credentials_service import demo_admin_credentials
from app.services import meta_template_service as svc
from app.services.demo_store import DEMO_WHATSAPP_OUTBOX


def run():
    assert svc.variable_count('Olá {{1}} e {{2}}')==2
    assert svc.preview('Olá {{1}}',['João'])=='Olá João'
    try: svc.variable_count('Olá {{2}}')
    except svc.TemplateError: pass
    else:raise AssertionError('Variáveis não sequenciais devem falhar.')
    session=TestClient(app)
    admin=demo_admin_credentials()
    assert session.post('/login',data={'email':admin['email'],'password':admin['password']},follow_redirects=False).status_code==303
    token=csrf_token_for_session(session.cookies[COOKIE_NAME])
    assert session.get('/atendimentos/1548').status_code==200
    assert 'templateOverlay' in session.get('/atendimentos/1548').text
    assert session.get('/atendimentos/1548/modelos.json').status_code==200
    response=session.post('/atendimentos/1548/modelos/enviar',data={'template_name':'nao_existe','csrf_token':token,'values_json':'[]'},follow_redirects=False)
    assert response.status_code==422
    response=session.post('/atendimentos/1548/modelos/enviar',data={'template_name':'nao_existe','csrf_token':'invalido','values_json':'[]'},follow_redirects=False)
    assert response.status_code==403
    # Só modelos aprovados podem seguir para o endpoint Meta.
    fake={'id':'id-1','name':'contato_teste','status':'PENDING','category':'UTILITY','language':'pt_BR','body':'Olá {{1}}!','variables':1}
    user={'id':'00000000-0000-0000-0000-000000000001','full_name':'Administrador Demo','role':'administrador'}
    with patch.object(svc,'configured',return_value=True), patch.object(svc,'list_templates',return_value=[fake]):
        try:svc.send_template(ticket_id='1548',user=user,template_name='contato_teste',language='pt_BR',values=['José'])
        except svc.TemplateError:pass
        else:raise AssertionError('Modelo PENDING não pode ser enviado')
    fake['status']='APPROVED'
    with patch.object(svc,'configured',return_value=True), patch.object(svc,'list_templates',return_value=[fake]),\
         patch.object(svc,'_graph',return_value={'messages':[{'id':'wamid.TEST_22'}]}),\
         patch.object(svc,'_phone_id',return_value='1234567890'):
        result=svc.send_template(ticket_id='1548',user=user,template_name='contato_teste',language='pt_BR',values=['José'])
    assert result['wamid']=='wamid.TEST_22'
    assert any(x.get('provider_message_id')=='wamid.TEST_22' for x in DEMO_WHATSAPP_OUTBOX)
    print('OK: validacao, sessao, CSRF, permissao Meta, envio simulado e registro WAMID')


if __name__=='__main__':run()
