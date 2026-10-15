"""Tela apenas de SIMULACAO de ciclo de vida. Nunca envia mensagens."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from app.core.ui import templates
from app.dependencies.auth import current_user
from app.services.access_service import require_access
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services import staging_dispatch_preview_service as preview
from app.services import staging_dispatch_lifecycle_service as lifecycle

router=APIRouter(prefix='/disparos/simulacoes',tags=['staging-dispatch-lifecycle'])


def _csrf(request,token):
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME),token):
        raise HTTPException(status_code=403,detail='Formulário inválido. Atualize a página.')


def _context(request,user,**extra):
    return {'user':user,'active_page':'dispatches',
            'csrf_token':csrf_token_for_session(request.cookies.get(COOKIE_NAME)),
            'candidates':preview.list_dispatch_candidates(),
            'simulations':lifecycle.list_simulations(),**extra}


def _state_error(exc):
    # Nunca renderiza o corpo de um erro do banco no HTML.
    code = getattr(exc, 'code', None)
    if not code:
        for part in getattr(exc, 'args', ()):
            if isinstance(part, dict):
                code = part.get('code')
                if code:
                    break
    if code in ('PT409', '40001'):
        return ('Outra aba atualizou esta simulação. Atualize a página antes de tentar novamente.', 409)
    if code == '22023':
        return ('Esta transição não é permitida. Atualize a página.', 422)
    if code == '42501':
        return ('Você não tem permissão para esta operação.', 403)
    return ('Banco de homologação temporariamente indisponível. Operações bloqueadas.', 503)


@router.get('')
def page(request:Request,user:dict=Depends(current_user)):
    require_access(user,'disparos')
    return templates.TemplateResponse(request=request,name='staging/dispatch_lifecycle.html',
                                      context=_context(request,user))


@router.post('/preparar')
def prepare(request:Request,opportunity_id:str=Form(...),content:str=Form(...),
            csrf_token:str=Form(''),user:dict=Depends(current_user)):
    require_access(user,'disparos');_csrf(request,csrf_token)
    try:
        result=lifecycle.prepare_simulation(opportunity_id=opportunity_id,
                                            content=content,actor_id=user['id'])
        error=None;code=200
    except ValueError as exc:
        result=None;error=str(exc);code=422
    except Exception:
        result=None;error='Não foi possível preparar a simulação. Verifique a migration no STAGING.';code=503
    return templates.TemplateResponse(request=request,name='staging/dispatch_lifecycle.html',
        status_code=code,context=_context(request,user,error=error,result=result,
                                         selected=opportunity_id,content=content[:1024]))


@router.post('/{simulation_id}/estado')
def state(request:Request,simulation_id:str,action:str=Form(...),
          lock_version:int=Form(...),csrf_token:str=Form(''),user:dict=Depends(current_user)):
    require_access(user,'disparos');_csrf(request,csrf_token)
    try:
        lifecycle.change_state(simulation_id=simulation_id,action=action,
                               lock_version=lock_version,actor_id=user['id'])
    except ValueError as exc:
        err=str(exc); status=422
    except Exception as exc:
        err, status=_state_error(exc)
    else:
        return RedirectResponse('/disparos/simulacoes',status_code=303)
    return templates.TemplateResponse(request=request,name='staging/dispatch_lifecycle.html',
        status_code=status,context=_context(request,user,error=err))
