"""Modelos de mensagem via Meta Cloud API; rotas restritas ao Atendimento."""
import json
import logging
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from app.core.ui import templates
from app.dependencies.auth import current_user
from app.services.access_service import require_access
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services.audit_service import record_audit
from app.services.ticket_service import get_ticket
from app.routers.tickets import _detail_context
from app.services.meta_template_service import TemplateError, configured, list_templates, send_template, submit_template

router=APIRouter(prefix='/atendimentos',tags=['modelos-whatsapp'])
log=logging.getLogger(__name__)


def _gate(request, user, ticket_id, csrf=None):
    require_access(user,'atendimentos')
    ticket=get_ticket(ticket_id,user)
    if not ticket or ticket.get('source')!='whatsapp':raise HTTPException(404,'Atendimento WhatsApp não encontrado.')
    if csrf is not None and not verify_csrf_token(request.cookies.get(COOKIE_NAME),csrf):
        raise HTTPException(403,'Solicitação inválida; recarregue a página.')


def _fail(request,user,ticket_id,message):
    return templates.TemplateResponse(request=request,name='tickets/detail.html',status_code=422,
        context=_detail_context(ticket_id,user,request=request,template_error=message,template_open=True))


def _items(value):
    try:
        parsed=json.loads(value)
        if not isinstance(parsed,list) or len(parsed)>5 or any(not isinstance(x,str) for x in parsed):raise ValueError()
        return [x.strip() for x in parsed]
    except (ValueError,TypeError):raise TemplateError('Variáveis inválidas; revise os campos.')


@router.get('/{ticket_id}/modelos.json')
def catalog(ticket_id:str,request:Request,user:dict=Depends(current_user)):
    _gate(request,user,ticket_id)
    if not configured():return JSONResponse({'configured':False,'templates':[],'message':'Configure META_ACCESS_TOKEN e os identificadores da conta WhatsApp em ambiente seguro.'})
    try: return JSONResponse({'configured':True,'templates':list_templates()})
    except TemplateError as exc: return JSONResponse({'configured':True,'templates':[],'message':str(exc)},status_code=502)


@router.post('/{ticket_id}/modelos/criar')
def create(ticket_id:str,request:Request,name:str=Form(...),category:str=Form(...),language:str=Form('pt_BR'),
           body:str=Form(...),examples_json:str=Form('[]'),csrf_token:str=Form(...),user:dict=Depends(current_user)):
    _gate(request,user,ticket_id,csrf_token)
    try: result=submit_template(name=name,category=category,language=language,body=body,examples=_items(examples_json))
    except TemplateError as exc:return _fail(request,user,ticket_id,str(exc))
    record_audit(actor_id=user['id'],entity_type='meta_template',entity_id=result.get('id') or name,
                 action='meta_template.submitted',payload={'name':name,'category':category,'status':result['status']})
    return RedirectResponse(f'/atendimentos/{ticket_id}?template_notice=submitted',303)


@router.post('/{ticket_id}/modelos/enviar')
def send(ticket_id:str,request:Request,template_name:str=Form(...),language:str=Form('pt_BR'),
         values_json:str=Form('[]'),csrf_token:str=Form(...),user:dict=Depends(current_user)):
    _gate(request,user,ticket_id,csrf_token)
    try: result=send_template(ticket_id=ticket_id,user=user,template_name=template_name,
                             language=language,values=_items(values_json))
    except TemplateError as exc:return _fail(request,user,ticket_id,str(exc))
    record_audit(actor_id=user['id'],entity_type='ticket',entity_id=ticket_id,
                 action='meta_template.sent',payload={'name':template_name,'wamid':result['wamid']})
    return RedirectResponse(f'/atendimentos/{ticket_id}?template_notice=sent',303)
