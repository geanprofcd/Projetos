"""Rotas internas do CRM STAGING: sem Meta, Make ou Disparos."""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from app.core.ui import templates
from app.dependencies.auth import current_user
from app.services.access_service import require_access, level_for
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services import staging_crm_service as svc

router=APIRouter(tags=['staging-crm'])

def _ctx(request,user,**data):
    return {'user':user,'active_page':'opportunities',
            'csrf_token':csrf_token_for_session(request.cookies.get(COOKIE_NAME)),**data}

def _csrf(request, supplied):
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME),supplied):
        raise HTTPException(status_code=403, detail='Formulário inválido. Atualize a página.')

def _data(request, user, error=None):
    funnels,opps,tickets=svc.list_crm()
    return _ctx(request,user, funnels=funnels, opportunities=opps,tickets=tickets,
                error=error, can_manage_funnels=level_for(user)=='administrativo')

def _sqlstate(exc) -> str:
    # Somente o codigo do provedor: nunca expor SQL nem a excecao bruta ao usuario.
    value = getattr(exc, 'code', None)
    if not value:
        for item in getattr(exc, 'args', ()):
            if isinstance(item, dict):
                value = item.get('code')
                if value:
                    break
    return str(value or '')


def _problem(exc):
    # PT409 = conflito comercial sem retry PostgREST (40001 fica apenas como legado).
    code = _sqlstate(exc)
    if code in {'PT409', '40001'}:
        return 'Outra pessoa alterou esta oportunidade. Atualize a página e tente novamente.'
    if code == '23505':
        return 'Já existe um cadastro semelhante. Atualize a página.'
    if code == '42501':
        return 'Sem permissão para esta operação.'
    return 'Não foi possível concluir a operação. Confira os dados ou atualize a página.'

@router.get('/oportunidades')
def overview(request:Request,user:dict=Depends(current_user)):
    require_access(user,'oportunidades')
    return templates.TemplateResponse(request=request,name='staging/crm_edit.html',context=_data(request,user))

@router.post('/oportunidades/funis/novo')
def create_funnel(request:Request,name:str=Form(...),stages:str=Form(...),
                  csrf_token:str=Form(''),user:dict=Depends(current_user)):
    require_access(user,'oportunidades');_csrf(request,csrf_token)
    if level_for(user)!='administrativo':
        raise HTTPException(status_code=403,detail='Somente administradores podem criar funis.')
    try:svc.create_funnel(name=name, stages_text=stages, actor_id=user['id'])
    except ValueError as exc:err=str(exc)
    except Exception as exc:err=_problem(exc)
    else:return RedirectResponse('/oportunidades',status_code=303)
    return templates.TemplateResponse(request=request,name='staging/crm_edit.html',status_code=422,
            context=_data(request,user,error=err))

@router.post('/oportunidades/novo')
def create_opportunity(request:Request,ticket_id:str=Form(...),stage_id:str=Form(...),
                       title:str=Form(...),csrf_token:str=Form(''),user:dict=Depends(current_user)):
    require_access(user,'oportunidades');_csrf(request,csrf_token)
    try:svc.create_opportunity(ticket_id=ticket_id,stage_id=stage_id,title=title,actor_id=user['id'])
    except ValueError as exc:err=str(exc)
    except Exception as exc:err=_problem(exc)
    else:return RedirectResponse('/oportunidades',status_code=303)
    return templates.TemplateResponse(request=request,name='staging/crm_edit.html',status_code=422,
            context=_data(request,user,error=err))

@router.post('/oportunidades/{opportunity_id}/mover')
def move(request:Request,opportunity_id:str,stage_id:str=Form(...),lock_version:int=Form(...),
         csrf_token:str=Form(''),user:dict=Depends(current_user)):
    require_access(user,'oportunidades');_csrf(request,csrf_token)
    try:
        svc.move_opportunity(opportunity_id=opportunity_id,stage_id=stage_id,
                             lock_version=lock_version,actor_id=user['id'])
    except ValueError as exc:err=str(exc)
    except Exception as exc:err=_problem(exc)
    else:return RedirectResponse('/oportunidades',status_code=303)
    return templates.TemplateResponse(request=request,name='staging/crm_edit.html',status_code=409,
             context=_data(request,user,error=err))
