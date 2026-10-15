"""Gestão de usuários e convite seguro por e-mail."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.core.ui import templates
from app.core.config import get_settings
from app.dependencies.auth import current_user
from app.services.access_service import LABELS, LEVELS, allowed, level_for
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services.audit_service import record_audit
from app.services.user_service import UserError, accept_invitation, create_invite, find_invitation, list_users, update_level, create_user_direct

router = APIRouter(tags=['usuarios'])


def _csrf(request: Request, supplied: str) -> None:
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME), supplied):
        raise HTTPException(status_code=403, detail='Solicitação inválida. Recarregue a página.')


def _context(request: Request, user: dict, **kwargs) -> dict:
    return {'user':user,'active_page':'users','people':list_users(), 'levels':LABELS,
            'can_edit_roles':level_for(user)=='administrativo',
            'csrf_token':csrf_token_for_session(request.cookies.get(COOKIE_NAME)), **kwargs}


@router.get('/usuarios')
def users_page(request: Request, user: dict = Depends(current_user)):
    if not allowed(user, 'usuarios'):raise HTTPException(403)
    return templates.TemplateResponse(request=request,name='users/index.html',context=_context(request,user))


@router.post('/usuarios/convidar')
def invite_user(request: Request, full_name: str = Form(...), email: str = Form(...),
                access_level: str = Form('comum'), csrf_token: str = Form(...), user: dict = Depends(current_user)):
    if not allowed(user,'usuarios'):raise HTTPException(403)
    _csrf(request,csrf_token)
    try:
        result = create_invite(actor=user,name=full_name,email=email,access_level=access_level)
    except UserError as exc:
        return templates.TemplateResponse(request=request,name='users/index.html',status_code=422,
                                          context=_context(request,user,error=str(exc)))
    record_audit(actor_id=user['id'], entity_type='user_invitation', entity_id=result['email'],
                 action='user.invited', payload={'access_level':access_level,'mode':result['status']})
    return templates.TemplateResponse(request=request,name='users/index.html',
                                      context=_context(request,user,success=('Convite enviado ao e-mail informado.' if result['status']=='sent' else 'Convite de demonstração criado. Nenhum e-mail foi enviado.'),
                                                       demo_preview=result.get('preview_url')))


@router.post('/usuarios/criar-direto')
def register_user_direct(request: Request, full_name: str = Form(...), email: str = Form(...),
                         password: str = Form(...), access_level: str = Form('comum'),
                         csrf_token: str = Form(...), user: dict = Depends(current_user)):
    _csrf(request,csrf_token)
    if level_for(user)!='administrativo':raise HTTPException(403,'Somente administrador pode criar conta com senha.')
    if get_settings().is_production and (not request.url.scheme=='https' and not get_settings().public_app_url):
        raise HTTPException(403,'Cadastro de senha requer HTTPS.')
    try:
        result=create_user_direct(actor=user,name=full_name,email=email,password=password,access_level=access_level)
    except UserError as exc:
        return templates.TemplateResponse(request=request,name='users/index.html',status_code=422,
             context=_context(request,user,error=str(exc)))
    record_audit(actor_id=user['id'],entity_type='user',entity_id=result['id'],action='user.created_direct',
                 payload={'access_level':access_level})
    return RedirectResponse('/usuarios?created=1',status_code=303)


@router.post('/usuarios/{user_id}/permissoes')
def permissions_change(user_id: str, request: Request, access_level: str = Form(...),
                       can_manage_users: bool = Form(False), csrf_token: str = Form(...), user: dict = Depends(current_user)):
    _csrf(request,csrf_token)
    if level_for(user)!='administrativo':raise HTTPException(403,'Somente administradores alteram permissões.')
    try:
        update_level(actor=user,user_id=user_id,new_level=access_level,can_manage_users=can_manage_users)
    except UserError as exc:
        return templates.TemplateResponse(request=request,name='users/index.html',status_code=422,
                                          context=_context(request,user,error=str(exc)))
    record_audit(actor_id=user['id'], entity_type='user', entity_id=user_id, action='user.permissions.changed',
                 payload={'access_level':access_level,'can_manage_users':bool(can_manage_users)})
    return RedirectResponse('/usuarios?updated=1',status_code=303)


@router.get('/convite/{token}')
def accept_page(token: str, request: Request):
    row = find_invitation(token)
    return templates.TemplateResponse(request=request,name='users/accept.html',
                                      context={'invitation':row,'token':token,'error':None})


@router.post('/convite/{token}')
def accept_user(token: str, request: Request, password: str = Form(...), confirm_password: str = Form(...)):
    row = find_invitation(token)
    if not row:raise HTTPException(410,'Convite inválido, expirado ou utilizado.')
    if password != confirm_password:
        return templates.TemplateResponse(request=request,name='users/accept.html',status_code=422,
                                          context={'invitation':row,'token':token,'error':'As senhas não coincidem.'})
    try:
        accept_invitation(token,password)
    except UserError as exc:
        return templates.TemplateResponse(request=request,name='users/accept.html',status_code=422,
                                          context={'invitation':find_invitation(token),'token':token,'error':str(exc)})
    return RedirectResponse('/login?invite=accepted',status_code=303)
