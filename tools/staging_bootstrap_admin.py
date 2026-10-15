"""Cria primeiro admin somente no VENDRA-STAGING; sem segredo na linha de comando."""
from __future__ import annotations
import getpass
import re
from tools.staging_runtime import load

def main():
    load()
    from app.db.supabase import get_admin_client
    admin=get_admin_client()
    try:
        existing=admin.table('profiles').select('id').limit(1).execute().data or []
    except Exception:
        print('Falha ao consultar perfis no STAGING. Nenhuma conta criada.');return 2
    if existing:
        print('STAGING ja tem perfil(s). Este comando e exclusivo para o primeiro administrador.');return 2
    name=' '.join(input('Nome do administrador de TESTE: ').split())
    email=input('Email do administrador de TESTE: ').strip().lower()
    passwd=getpass.getpass('Senha nova de TESTE (oculta, min. 12 caracteres): ')
    passwd2=getpass.getpass('Repita a senha de TESTE: ')
    if len(name)<2 or len(name)>120 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(passwd)<12 or passwd != passwd2:
        print('Dados invalidos ou senhas diferentes. Nenhuma conta criada.');return 2
    if input('Digite CRIAR ADMIN STAGING para autorizar: ').strip() != 'CRIAR ADMIN STAGING':
        print('Cancelado.');return 2
    uid=None
    try:
        response=admin.auth.admin.create_user({'email':email,'password':passwd,'email_confirm':True})
        if not response.user:raise RuntimeError('Sem usuario no retorno da autenticacao')
        uid=str(response.user.id)
        admin.table('profiles').insert({'id':uid,'full_name':name,'email':email,
            'role':'administrador','access_level':'administrativo','status':'active',
            'can_manage_users':True}).execute()
    except Exception:
        if uid:
            try:admin.auth.admin.delete_user(uid)
            except Exception:print('ATENCAO: pode existir usuario Auth sem perfil; verifique manualmente o STAGING.')
        print('Nao foi possivel concluir o provisionamento. Confira STAGING / Auth / perfis.');return 2
    print('Primeiro administrador de testes criado no Supabase-STAGING.')
    print('Agora inicie a aplicacao H1-005B2 na porta 8011.')
    return 0

if __name__=='__main__':raise SystemExit(main())
