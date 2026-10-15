"""Interface H1-005B8: nao ha qualquer acao de envio real nesta rota."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from app.core.ui import templates
from app.dependencies.auth import current_user
from app.services.access_service import require_access
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services import staging_dispatch_preview_service as preview
from app.services import staging_transport_contract_service as contracts

router = APIRouter(prefix='/disparos/contrato',tags=['staging-transport-contract'])

# Somente SQLSTATE de conflitos conhecidos; nao exibir mensagens internas do backend.
# PostgREST publica o codigo PostgreSQL como APIError.code.
def _sqlstate(exc: Exception) -> str:
    code = getattr(exc, 'code', None)
    if code is None:
        for arg in getattr(exc, 'args', ()):
            if isinstance(arg, dict):
                code = arg.get('code')
                if code is not None:
                    break
    return code if isinstance(code, str) else ''


def _offline_response(request: Request, user: dict, message: str):
    # Quando o banco falhar, NAO chamar _context outra vez (e bloquear botoes).
    return templates.TemplateResponse(request=request, name='staging/transport_contract.html',
        status_code=503, context={'user': user, 'active_page':'dispatches', 'problem':message,
                                  'items':[], 'candidates':[], 'status':None})


def _csrf(request: Request, token: str) -> None:
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME), token):
        raise HTTPException(403,detail='Formulario invalido. Atualize a pagina.')


def _context(request,user,**extra):
    return dict(user=user,active_page='dispatches',
                csrf_token=csrf_token_for_session(request.cookies.get(COOKIE_NAME)),
                status=contracts.require_clean_staging(),
                candidates=preview.list_dispatch_candidates(),
                items=contracts.list_contracts(),**extra)


@router.get('')
def page(request:Request, user:dict=Depends(current_user)):
    require_access(user,'disparos')
    try:
        ctx=_context(request,user)
        ctx['notice'] = request.query_params.get('resultado') in ('preparado','alterado')
        ctx['warning'] = {
            'conflito': 'Outra aba atualizou este contrato. Confira a versao atual antes de tentar novamente.',
            'estado': 'Acao nao permitida no estado atual ou prazo ainda valido. Confira o contrato.',
            'permissao': 'O usuario nao tem permissao para essa operacao de homologacao.',
        }.get(request.query_params.get('aviso',''))
        status=200
    except Exception:
        ctx={'user':user,'active_page':'dispatches','problem':'Banco ou integridade STAGING indisponivel. Acoes bloqueadas.',
             'items':[],'candidates':[],'status':None}
        status=503
    return templates.TemplateResponse(request=request,
        name='staging/transport_contract.html',status_code=status,context=ctx)


@router.post('/preparar')
def prepare(request:Request,opportunity_id:str=Form(...),content:str=Form(...),
            csrf_token:str=Form(''),user:dict=Depends(current_user)):
    require_access(user,'disparos');_csrf(request,csrf_token)
    try:
        contracts.prepare_contract(opportunity_id=opportunity_id,content=content,actor_id=user['id'])
    except ValueError as exc:
        ctx=_context(request,user,error=str(exc))
        return templates.TemplateResponse(request=request,
            name='staging/transport_contract.html',status_code=422,context=ctx)
    except Exception:
        ctx=_context(request,user,error='Falha ao preparar contrato. Verifique migration e logs seguros.')
        return templates.TemplateResponse(request=request,
            name='staging/transport_contract.html',status_code=503,context=ctx)
    # PRG: reabrir/atualizar pagina nao repete o POST.
    return RedirectResponse('/disparos/contrato?resultado=preparado',status_code=303)


@router.post('/{contract_id}/acao')
def action(request:Request,contract_id:str, action:str=Form(...),
           lock_version:int=Form(...),csrf_token:str=Form(''),
           user:dict=Depends(current_user)):
    require_access(user,'disparos');_csrf(request,csrf_token)
    try:
        contracts.change_contract(contract_id=contract_id,action=action,
                                  lock_version=lock_version,actor_id=user['id'])
    except ValueError as exc:
        ctx=_context(request,user,error=str(exc))
        return templates.TemplateResponse(request=request,
            name='staging/transport_contract.html',status_code=422,context=ctx)
    except Exception as exc:
        code = _sqlstate(exc)
        if code == 'PT409' or code == '40001':
            return RedirectResponse('/disparos/contrato?aviso=conflito',status_code=303)
        if code == '22023':
            return RedirectResponse('/disparos/contrato?aviso=estado',status_code=303)
        if code == '42501':
            return RedirectResponse('/disparos/contrato?aviso=permissao',status_code=303)
        return _offline_response(request,user,
            'Banco de homologacao temporariamente indisponivel. Operacoes bloqueadas; atualize mais tarde.')
    return RedirectResponse('/disparos/contrato?resultado=alterado',status_code=303)
