from __future__ import annotations

from uuid import uuid4
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from app.core.ui import templates
from app.dependencies.auth import current_user
from app.services.access_service import require_access
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services import dispatch_command_service as service

router = APIRouter(prefix='/disparos/envio', tags=['dispatch-command'])


def _render(request, user, *, error=None, status_code=200, form=None):
    try:
        rows = service.list_dispatches()
    except Exception:
        rows = []
        error = 'Histórico indisponível. Atualize a página antes de enviar.'
        status_code = 503
    return templates.TemplateResponse(request=request, name='dispatches/command.html', status_code=status_code,
        context={'user': user, 'active_page': 'dispatches', 'rows': rows, 'error': error,
            'enabled': service.channel_ready() and status_code != 503,
            'csrf_token': csrf_token_for_session(request.cookies.get(COOKIE_NAME)),
            'request_id': (form or {}).get('request_id') or str(uuid4()), 'form': form or {}})


@router.get('')
def page(request: Request, user: dict = Depends(current_user)):
    require_access(user, 'disparos')
    return _render(request, user)


@router.post('')
def submit(request: Request, name: str = Form(...), phone: str = Form(...),
           request_id: str = Form(...), csrf_token: str = Form(''), user: dict = Depends(current_user)):
    require_access(user, 'disparos')
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME), csrf_token):
        raise HTTPException(403, detail='Formulário inválido. Atualize a página.')
    form = {'name': name, 'phone': phone, 'request_id': request_id}
    try:
        result = service.request_dispatch(user=user, name=name, phone=phone, request_id=request_id)
    except ValueError as exc:
        return _render(request, user, error=str(exc), status_code=422, form=form)
    except Exception:
        return _render(request, user, error='Não foi possível confirmar o pedido. Confira o histórico antes de repetir.',
                       status_code=503, form=form)
    outcome = 'recebido' if result.get('transport_confirmed') else 'pendente'
    return RedirectResponse('/disparos/envio?resultado='+outcome, status_code=303)
