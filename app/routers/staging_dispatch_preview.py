"""Disparos simulados no STAGING, sem WhatsApp, Make ou fila."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from app.core.ui import templates
from app.dependencies.auth import current_user
from app.services.access_service import require_access
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services import staging_dispatch_preview_service as svc

router = APIRouter(prefix='/disparos', tags=['staging-dispatch-preview'])

def _context(request: Request, user: dict, *, error=None, result=None, content='', selected=''):
    return {'user': user, 'active_page': 'dispatches', 'error': error,
            'result': result, 'content': content, 'selected': selected,
            'candidates': svc.list_dispatch_candidates(),
            'csrf_token': csrf_token_for_session(request.cookies.get(COOKIE_NAME))}

@router.get('')
def index(request: Request, user: dict = Depends(current_user)):
    require_access(user, 'disparos')
    return templates.TemplateResponse(request=request,
        name='staging/dispatch_preview.html', context=_context(request, user))

@router.post('/simular')
def simulate(request: Request,
             opportunity_id: str = Form(...),
             content: str = Form(...),
             csrf_token: str = Form(''),
             user: dict = Depends(current_user)):
    require_access(user, 'disparos')
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME), csrf_token):
        raise HTTPException(status_code=403, detail='Formulário inválido. Atualize a página.')
    try:
        preview = svc.simulate_dispatch(opportunity_id=opportunity_id,
                                        content=content, actor_id=user['id'])
        error = None
        status_code = 200
    except ValueError as exc:
        preview = None
        error = str(exc)
        status_code = 422
    except Exception:
        preview = None
        error = 'Não foi possível registrar a prévia. Verifique os dados e tente novamente.'
        status_code = 503
    return templates.TemplateResponse(request=request,name='staging/dispatch_preview.html',
        status_code=status_code,
        context=_context(request,user,error=error,result=preview,
                         content=content[:1024], selected=opportunity_id))
