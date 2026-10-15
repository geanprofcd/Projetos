"""UI de homologacao: atendimentos internos e leitura do CRM; SEM canais externos."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from app.core.ui import templates
from app.dependencies.auth import current_user
from app.services.access_service import require_access
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services.customer_service import list_customers
from app.services.staging_attendance_service import (
    list_internal_tickets,create_internal_ticket,get_internal_ticket,list_internal_notes,
    add_internal_note,list_crm_overview,PRIORITIES)

router=APIRouter(tags=['staging-atendimentos'])

def _authorize(user,module):return require_access(user,module)

def _token(request):return csrf_token_for_session(request.cookies.get(COOKIE_NAME))

def _csrf(request, supplied):
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME), supplied):
        raise HTTPException(status_code=403,detail='Token de segurança inválido. Atualize a página.')

def _ctx(request,user,**other):
    return {'user':user, 'csrf_token':_token(request),'active_page':'tickets',**other}

@router.get('/atendimentos')
def list_page(request:Request,user:dict=Depends(current_user)):
    _authorize(user,'atendimentos')
    return templates.TemplateResponse(request=request,name='staging/tickets_list.html',
        context=_ctx(request,user,tickets=list_internal_tickets()))

@router.get('/atendimentos/novo')
def new_page(request:Request,user:dict=Depends(current_user)):
    _authorize(user,'atendimentos')
    return templates.TemplateResponse(request=request,name='staging/ticket_new.html',
        context=_ctx(request,user,customers=list_customers(include_inactive=False),priorities=PRIORITIES,error=None))

@router.post('/atendimentos/novo')
def create(request:Request,title:str=Form(...),customer_id:str=Form(...),priority:str=Form('normal'),
           csrf_token:str=Form(''),user:dict=Depends(current_user)):
    _authorize(user,'atendimentos');_csrf(request,csrf_token)
    try:
        ticket=create_internal_ticket(actor_id=str(user.get('id') or ''),title=title,customer_id=customer_id,priority=priority)
    except ValueError as exc:
        return templates.TemplateResponse(request=request,name='staging/ticket_new.html',status_code=422,
             context=_ctx(request,user,customers=list_customers(include_inactive=False),priorities=PRIORITIES,error=str(exc),
                          selected={'title':title,'customer_id':customer_id,'priority':priority}))
    return RedirectResponse('/atendimentos/'+str(ticket['id']),status_code=303)

@router.get('/atendimentos/{ticket_id}')
def detail(request:Request,ticket_id:str,user:dict=Depends(current_user)):
    _authorize(user,'atendimentos')
    try:
        ticket=get_internal_ticket(ticket_id)
        if not ticket:raise HTTPException(404,'Atendimento interno não encontrado.')
        notes=list_internal_notes(ticket_id)
    except ValueError:raise HTTPException(404,'Atendimento interno não encontrado.') from None
    return templates.TemplateResponse(request=request,name='staging/ticket_detail.html',
        context=_ctx(request,user,ticket=ticket,notes=notes,error=None))

@router.post('/atendimentos/{ticket_id}/notas')
def note(request:Request,ticket_id:str,content:str=Form(...),csrf_token:str=Form(''),
         user:dict=Depends(current_user)):
    _authorize(user,'atendimentos');_csrf(request,csrf_token)
    try:add_internal_note(ticket_id=ticket_id,actor_id=str(user.get('id') or ''),content=content)
    except ValueError as exc:
        try:ticket=get_internal_ticket(ticket_id)
        except ValueError:ticket=None
        if not ticket:raise HTTPException(404,'Atendimento interno não encontrado.') from None
        return templates.TemplateResponse(request=request,name='staging/ticket_detail.html',status_code=422,
             context=_ctx(request,user,ticket=ticket,notes=list_internal_notes(ticket_id),error=str(exc)))
    return RedirectResponse('/atendimentos/'+ticket_id,status_code=303)

@router.get('/oportunidades')
def crm_read_only(request:Request,user:dict=Depends(current_user)):
    _authorize(user,'oportunidades')
    funnels,opportunities=list_crm_overview()
    return templates.TemplateResponse(request=request,name='staging/crm_read_only.html',
        context={'user':user,'active_page':'opportunities','funnels':funnels,'opportunities':opportunities})
