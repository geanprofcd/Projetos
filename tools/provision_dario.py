"""Cria Dário Silas com perfil Comercial na INSTALAÇÃO LOCAL.

Execute com VENDRA parado. Senha solicitada interativamente (sem logs,
sem argumentos CLI, sem credenciais dentro do ZIP).
"""
from __future__ import annotations

import getpass
import hashlib
import secrets
import sys
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.core.config import get_settings

NAME='Dário Silas'
EMAIL='dario.silas@i9se.digital'
LEVEL='comercial'


def main() -> int:
    settings=get_settings()
    print('VENDRA — provisionamento de usuário Comercial')
    print(f'Usuário: {NAME} | {EMAIL} | {LEVEL}')
    if not settings.demo_mode and not settings.supabase_configured:
        print('Erro: configure a conexão real do Supabase. Nenhuma conta foi criada.')
        return 2
    if settings.demo_mode:
        from app.services.demo_store import DEMO_INTERNAL_USERS, DEMO_USER_PASSWORDS, persist_demo_state
        if any(x.get('email','').lower()==EMAIL for x in DEMO_INTERNAL_USERS):
            print('Conta já existente; não foram feitas alterações.')
            return 1
    else:
        from app.db.supabase import get_admin_client
        admin=get_admin_client()
        if admin.table('profiles').select('id').eq('email',EMAIL).limit(1).execute().data:
            print('Conta já existente; não foram feitas alterações.')
            return 1
    password=getpass.getpass('Senha inicial (mínimo 12 caracteres): ')
    confirm=getpass.getpass('Repita a senha: ')
    if len(password)<12 or len(password)>128 or password!=confirm:
        print('Senha inválida ou confirmação diferente. Nenhuma conta foi criada.')
        return 2
    if settings.demo_mode:
        salt=secrets.token_bytes(16)
        record={'salt':salt.hex(),'hash':hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000).hex()}
        user_id=str(uuid4())
        DEMO_INTERNAL_USERS.append({'id':user_id,'full_name':NAME,'email':EMAIL,
            'role':'responsavel','access_level':LEVEL,'can_manage_users':False,'status':'active'})
        DEMO_USER_PASSWORDS[user_id]=record
        persist_demo_state()
    else:
        from app.services.access_service import legacy_role
        response=admin.auth.admin.create_user({'email':EMAIL,'password':password,'email_confirm':True})
        user_id=str(response.user.id)
        try:
            admin.table('profiles').upsert({'id':user_id,'email':EMAIL,'full_name':NAME,'role':legacy_role(LEVEL),
                'access_level':LEVEL,'can_manage_users':False,'status':'active'},on_conflict='id').execute()
        except Exception:
            try:admin.auth.admin.delete_user(user_id)
            except Exception:pass
            raise
    print('Conta criada. Oriente o usuário a redefinir a senha inicial após entrar.')
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        print('Falha ao cadastrar usuário; verifique configurações e permissões do ambiente.')
        sys.exit(2)
