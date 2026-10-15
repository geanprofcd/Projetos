"""H1-005B7: pagina apenas de preflight de delivery; proibido enviar ou enfileirar."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from app.core.ui import templates
from fastapi.responses import JSONResponse, RedirectResponse
from app.dependencies.auth import current_user
from app.services.access_service import require_access
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services import staging_dispatch_preview_service as preview
from app.services import staging_delivery_preflight_service as svc

router = APIRouter(prefix='/disparos/prontidao', tags=['staging-delivery-preflight'])


def _context(request, user, **extra):
    try:
        result = svc.readiness()
        problem = None
    except Exception:
        result = None
        problem = 'Nao foi possivel verificar o STAGING. Plano bloqueado; confira banco e configuracao.'
    if result is None:
        candidates = []
    else:
        try:
            candidates = preview.list_dispatch_candidates()
        except Exception:
            candidates = []
            problem = 'Nao foi possivel consultar as oportunidades; plano bloqueado.'
    return {
        'user':user,'active_page':'dispatches',
        'csrf_token':csrf_token_for_session(request.cookies.get(COOKIE_NAME)),
        'status':result,'candidates':candidates,'problem':problem,**extra,
    }


@router.get('')
def page(request:Request,user:dict=Depends(current_user)):
    require_access(user,'disparos')
    ctx = _context(request,user)
    ctx['result_notice'] = request.query_params.get('resultado') == 'validado'
    ctx['error_notice'] = request.query_params.get('resultado') == 'recusado'
    return templates.TemplateResponse(request=request,
        name='staging/delivery_preflight.html',status_code=503 if ctx['problem'] else 200,context=ctx)


@router.post('/plano')
def plan(request:Request,opportunity_id:str=Form(...),content:str=Form(...),
         csrf_token:str=Form(''),user:dict=Depends(current_user)):
    require_access(user,'disparos')
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME),csrf_token):
        raise HTTPException(status_code=403,detail='Formulario invalido. Atualize a pagina.')

    # H1-005B9: o navegador submete via fetch para manter a resposta somente em memoria.
    # Sem JS, o servidor usa PRG com indicador generico (nunca leva PII para a URL).
    as_json = 'application/json' in request.headers.get('accept','').lower()
    try:
        readiness = svc.readiness()
        if not readiness['real_queue_clean']:
            raise RuntimeError('Preflight indisponivel. Filas de envio nao estao vazias.')
        result = svc.make_plan(opportunity_id=opportunity_id,content=content,actor_id=user['id'])
    except ValueError as exc:
        if as_json:
            return JSONResponse({'ok':False,'error':str(exc)},status_code=422,
                                headers={'Cache-Control':'no-store'})
        return RedirectResponse('/disparos/prontidao?resultado=recusado',status_code=303)
    except Exception:
        if as_json:
            return JSONResponse({'ok':False,'error':'Preflight bloqueado. Confira o STAGING.'},
                                status_code=503,headers={'Cache-Control':'no-store'})
        return RedirectResponse('/disparos/prontidao?resultado=recusado',status_code=303)

    if as_json:
        # JSON transitório: nunca gravar plano, mensagem, telefone ou chave em banco/session/url.
        public_fields = ('opportunity_title','customer_name','phone_masked',
                         'rendered_message','idempotency_reference',
                         'destination','delivery_state')
        return JSONResponse({'ok':True,'plan':{k:result[k] for k in public_fields}},
                            headers={'Cache-Control':'no-store','Pragma':'no-cache'})
    return RedirectResponse('/disparos/prontidao?resultado=validado',status_code=303)
