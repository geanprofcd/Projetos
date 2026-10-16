"""Gestão de convites: link compartilhável de uso único; SMTP opcional.

A modalidade demo apresenta link de teste ao administrador, SEM declarar email enviado.
Nunca armazenar senha em texto livre nem token de convite em banco.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from threading import RLock
from uuid import uuid4

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.access_service import LEVELS, LABELS, legacy_role, level_for
from app.services.auth_service import DEMO_USER_ID
from app.services.demo_store import DEMO_INTERNAL_USERS, DEMO_USER_INVITATIONS, DEMO_USER_PASSWORDS, now_iso

LOCK = RLock()

class UserError(ValueError):
    pass


def _email(email: str) -> str:
    value = email.strip().lower()
    if len(value) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise UserError('Informe um endereço de e-mail válido.')
    return value


def list_users() -> list[dict]:
    if get_settings().demo_mode:
        return sorted((dict(u, access_level=level_for(u)) for u in DEMO_INTERNAL_USERS), key=lambda u:u.get('full_name','').lower())
    return get_admin_client().table('profiles').select('id,full_name,email,role,access_level,can_manage_users,status').order('full_name').execute().data or []


def _smtp_send(email: str, name: str, url: str) -> None:
    settings = get_settings()
    if settings.app_env == "staging":
        raise UserError("Ambiente de homologação: envio de convites por e-mail desativado.")
    if not all((settings.smtp_host, settings.smtp_from, settings.public_app_url)):
        raise UserError('Configure SMTP_HOST, SMTP_FROM e PUBLIC_APP_URL para enviar convites reais.')
    if settings.is_production and not settings.public_app_url.startswith('https://'):
        raise UserError('PUBLIC_APP_URL deve usar HTTPS em produção.')
    msg = EmailMessage()
    msg['Subject'] = 'Convite para acessar o VENDRA'
    msg['From'] = settings.smtp_from
    msg['To'] = email
    msg.set_content(f'Olá, {name}!\n\nVocê foi convidado a acessar o VENDRA.\nCadastre sua senha neste endereço (válido por 48 horas):\n{url}\n\nSe não esperava este convite, ignore a mensagem.\n')
    try:
        if settings.smtp_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10, context=ssl.create_default_context()) as smtp:
                if settings.smtp_user:
                    smtp.login(settings.smtp_user, settings.smtp_password or '')
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                if settings.smtp_user:
                    smtp.login(settings.smtp_user, settings.smtp_password or '')
                smtp.send_message(msg)
    except (OSError, smtplib.SMTPException) as exc:
        raise UserError('Não foi possível enviar o convite. Verifique as configurações de e-mail.') from exc


def create_invite(*, actor: dict, name: str, email: str, access_level: str) -> dict:
    name = ' '.join(name.split())
    if not (2 <= len(name) <= 120):raise UserError('Informe o nome completo do usuário.')
    email = _email(email)
    if access_level not in LEVELS:raise UserError('Perfil inválido.')
    actor_level = level_for(actor)
    if actor_level != 'administrativo' and (not actor.get('can_manage_users') or LEVELS.index(access_level) > LEVELS.index(actor_level)):
        raise UserError('Você não pode conceder este nível de permissão.')
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
    row = {'id':str(uuid4()),'email':email,'full_name':name,'access_level':access_level,'invited_by':actor['id'],
           'token_hash':token_hash,'expires_at':expires,'status':'pending','created_at':now_iso(),'consumed_at':None}
    settings = get_settings()
    base_url = (settings.public_app_url or 'http://127.0.0.1:8010').rstrip('/')
    delivery = getattr(settings, 'invitation_delivery', 'link')
    if delivery not in ('link', 'smtp'):
        raise UserError('Forma de entrega de convite inválida.')
    if not settings.demo_mode and settings.is_production and not base_url.startswith('https://'):
        raise UserError('Configure PUBLIC_APP_URL com HTTPS antes de gerar convites.')
    url = f'{base_url}/convite/{token}'
    if settings.demo_mode:
        with LOCK:
            if any(u['email'].lower()==email and u.get('status')=='active' for u in DEMO_INTERNAL_USERS):
                raise UserError('Já existe um usuário ativo com esse e-mail.')
            for existing in DEMO_USER_INVITATIONS:
                if existing['email']==email and existing['status']=='pending': existing['status']='revoked'
            DEMO_USER_INVITATIONS.append(row)
        return {'status':'demo_preview','preview_url':url,'email':email}
    admin = get_admin_client()
    if admin.table('profiles').select('id').eq('email',email).limit(1).execute().data:
        raise UserError('Esse e-mail já está cadastrado.')
    # Revoga convites pendentes: um só link válido por endereço.
    admin.table('user_invitations').update({'status':'revoked'}).eq('email',email).in_('status',['pending','sent']).execute()
    admin.table('user_invitations').insert(row).execute()
    if delivery == 'link':
        # O token aparece somente ao operador; o banco guarda apenas seu hash.
        return {'status':'manual_link','invitation_url':url,'email':email}
    try:
        _smtp_send(email,name,url)
    except UserError:
        admin.table('user_invitations').update({'status':'failed'}).eq('id',row['id']).execute()
        raise
    admin.table('user_invitations').update({'status':'sent'}).eq('id',row['id']).execute()
    return {'status':'sent','email':email}


def find_invitation(token: str) -> dict | None:
    if not re.fullmatch(r'[A-Za-z0-9_-]{40,128}', token):return None
    sha = hashlib.sha256(token.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    if get_settings().demo_mode:
        row = next((x for x in DEMO_USER_INVITATIONS if hmac.compare_digest(x['token_hash'],sha)),None)
    else:
        items = get_admin_client().table('user_invitations').select('*').eq('token_hash',sha).limit(1).execute().data or []
        row = items[0] if items else None
    if not row or row.get('status') not in ('pending','sent') or datetime.fromisoformat(row['expires_at'].replace('Z','+00:00')) <= now:
        return None
    return row


def accept_invitation(token: str, password: str) -> dict:
    if len(password) < 12 or len(password) > 128:
        raise UserError('Use uma senha entre 12 e 128 caracteres.')
    row = find_invitation(token)
    if not row:raise UserError('Este convite expirou ou já foi utilizado.')
    with LOCK:
        row = find_invitation(token)
        if not row:raise UserError('Este convite não está mais disponível.')
        if get_settings().demo_mode:
            if any(u['email'].lower() == row['email'] for u in DEMO_INTERNAL_USERS):
                raise UserError('Usuário já existente.')
            uid = str(uuid4())
            salt = secrets.token_bytes(16)
            DEMO_USER_PASSWORDS[uid] = {'salt':salt.hex(),'hash':hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000).hex()}
            user = {'id':uid,'full_name':row['full_name'],'email':row['email'],'role':legacy_role(row['access_level']),
                    'access_level':row['access_level'],'can_manage_users':False,'status':'active'}
            DEMO_INTERNAL_USERS.append(user)
            row['status']='accepted';row['consumed_at']=now_iso()
            return user
        admin = get_admin_client()
        # Reserva condicional o convite ANTES de criar a conta, evitando reuso concorrente.
        claimed = (admin.table('user_invitations').update({'status':'processing'})
                   .eq('id',row['id']).in_('status',['pending','sent']).gt('expires_at',now_iso()).execute().data or [])
        if not claimed:raise UserError('Este convite já está sendo utilizado.')
        uid = None
        try:
            created = admin.auth.admin.create_user({'email':row['email'],'password':password,'email_confirm':True})
            uid = str(created.user.id)
            user = {'id':uid,'email':row['email'],'full_name':row['full_name'],'role':legacy_role(row['access_level']),
                    'access_level':row['access_level'],'can_manage_users':False,'status':'active'}
            admin.table('profiles').upsert(user, on_conflict='id').execute()
            admin.table('user_invitations').update({'status':'accepted','consumed_at':now_iso()}).eq('id',row['id']).execute()
            return user
        except Exception as exc:
            if uid:
                try:admin.auth.admin.delete_user(uid)
                except Exception:pass
            admin.table('user_invitations').update({'status':'failed'}).eq('id',row['id']).execute()
            raise UserError('Não foi possível concluir o cadastro. Solicite um novo convite.') from exc


def update_level(*, actor: dict, user_id: str, new_level: str, can_manage_users: bool = False) -> None:
    if level_for(actor) != 'administrativo':raise UserError('Somente administradores podem editar permissões.')
    if new_level not in LEVELS:raise UserError('Nível inválido.')
    if user_id == actor['id']:raise UserError('Não altere seu próprio perfil. Peça a outro administrador.')
    all_users = list_users()
    target = next((u for u in all_users if u['id']==user_id),None)
    if not target:raise UserError('Usuário não encontrado.')
    if level_for(target)=='administrativo' and new_level!='administrativo' and sum(level_for(u)=='administrativo' and u.get('status')=='active' for u in all_users) <= 1:
        raise UserError('Deve permanecer ao menos um administrador ativo.')
    fields = {'role':legacy_role(new_level),'access_level':new_level,'can_manage_users':bool(can_manage_users) and new_level != 'administrativo'}
    if get_settings().demo_mode:
        target2 = next(u for u in DEMO_INTERNAL_USERS if u['id']==user_id)
        target2.update(fields)
    else:
        get_admin_client().table('profiles').update(fields).eq('id',user_id).execute()


def create_user_direct(*, actor: dict, name: str, email: str, password: str, access_level: str) -> dict:
    """Cadastro sem convite, exclusivo do administrador autenticado.

    A senha chega somente no POST HTTPS, é armazenada por hash/Auth provider,
    nunca em arquivos de release, logs ou auditoria.
    """
    if level_for(actor) != 'administrativo':
        raise UserError('Somente administradores podem cadastrar contas diretamente.')
    name=' '.join(name.split())
    email=_email(email)
    if not 2<=len(name)<=120:raise UserError('Informe nome completo válido.')
    if access_level not in LEVELS:raise UserError('Nível de acesso inválido.')
    if not 12<=len(password)<=128:raise UserError('A senha deve ter entre 12 e 128 caracteres.')
    if get_settings().demo_mode:
        with LOCK:
            if any(u.get('email','').lower()==email for u in DEMO_INTERNAL_USERS):
                raise UserError('Já existe uma conta com esse e-mail.')
            uid=str(uuid4())
            salt=secrets.token_bytes(16)
            DEMO_USER_PASSWORDS[uid]={'salt':salt.hex(),
                'hash':hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000).hex()}
            result={'id':uid,'full_name':name,'email':email,'role':legacy_role(access_level),
                    'access_level':access_level,'can_manage_users':False,'status':'active'}
            DEMO_INTERNAL_USERS.append(result)
            return result
    admin=get_admin_client()
    if admin.table('profiles').select('id').eq('email',email).limit(1).execute().data:
        raise UserError('Já existe uma conta com esse e-mail.')
    uid=None
    try:
        created=admin.auth.admin.create_user({'email':email,'password':password,'email_confirm':True})
        uid=str(created.user.id)
        result={'id':uid,'full_name':name,'email':email,'role':legacy_role(access_level),
                'access_level':access_level,'can_manage_users':False,'status':'active'}
        admin.table('profiles').upsert(result,on_conflict='id').execute()
        return result
    except Exception as exc:
        if uid:
            try:admin.auth.admin.delete_user(uid)
            except Exception:pass
        raise UserError('Não foi possível criar a conta. Verifique as permissões da integração Supabase.') from exc
