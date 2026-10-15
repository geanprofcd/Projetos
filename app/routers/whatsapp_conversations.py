from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from app.core.ui import templates
from app.dependencies.auth import current_user
from app.services.access_service import require_access, level_for
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services import whatsapp_portal_service as service

router = APIRouter(prefix='/conversas', tags=['whatsapp-conversations'])


def _render(request, user, ticket_id, *, error=None, status_code=200):
    try:
        detail = service.get_conversation(ticket_id)
    except ValueError:
        raise HTTPException(404, 'Conversa não encontrada.') from None
    except Exception:
        raise HTTPException(503, 'Conversa indisponível. Tente atualizar a página.') from None
    if not detail:
        raise HTTPException(404, 'Conversa não encontrada.')
    return templates.TemplateResponse(request=request, name='whatsapp/conversation.html', status_code=status_code,
        context={'user': user, 'active_page': 'conversations', **detail, 'error': error,
            'can_control': level_for(user) == 'administrativo',
            'csrf_token': csrf_token_for_session(request.cookies.get(COOKIE_NAME))})


@router.get('')
def listing(request: Request, user: dict = Depends(current_user)):
    require_access(user, 'atendimentos')
    try:
        rows = service.list_conversations()
    except Exception:
        raise HTTPException(503, 'Conversas indisponíveis. Tente atualizar a página.') from None
    return templates.TemplateResponse(request=request, name='whatsapp/list.html',
        context={'user': user, 'active_page': 'conversations', 'conversations': rows})


@router.get('/{ticket_id}')
def detail(ticket_id: str, request: Request, user: dict = Depends(current_user)):
    require_access(user, 'atendimentos')
    return _render(request, user, ticket_id)


@router.post('/{ticket_id}/modo')
def mode(ticket_id: str, request: Request, mode: str = Form(...), version: int = Form(...),
         csrf_token: str = Form(''), user: dict = Depends(current_user)):
    require_access(user, 'atendimentos')
    if level_for(user) != 'administrativo':
        raise HTTPException(403, 'Somente administradores podem alterar a automação.')
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME), csrf_token):
        raise HTTPException(403, 'Formulário inválido. Atualize a conversa.')
    try:
        service.change_mode(ticket_id=ticket_id, mode=mode, version=version, user=user)
    except service.ConversationConflict as exc:
        return _render(request, user, ticket_id, error=str(exc), status_code=409)
    except ValueError as exc:
        return _render(request, user, ticket_id, error=str(exc), status_code=422)
    except PermissionError:
        raise HTTPException(403, 'Sem permissão para alterar a automação.') from None
    except Exception:
        return _render(request, user, ticket_id,
            error='Não foi possível confirmar a alteração. Atualize a conversa antes de repetir.', status_code=503)
    return RedirectResponse('/conversas/'+ticket_id, status_code=303)
