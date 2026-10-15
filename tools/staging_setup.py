"""Cria .env.h1_005b2 apenas na pasta copiada de testes; segredos nunca sao impressos."""
import getpass
import os
from pathlib import Path
from urllib.parse import urlsplit
from secrets import token_urlsafe
from tools.staging_guard import check_staging

TARGET = Path('.env.h1_005b2')

def main():
    if TARGET.exists():
        print('A configuracao de STAGING ja existe. Nenhum arquivo foi alterado.')
        print('Se precisar corrigir, edite .env.h1_005b2 localmente sem compartilhar as chaves.')
        return 1
    print('Configurar SOMENTE a copia de testes do VENDRA, na porta 8011.')
    url=input('Project URL de VENDRA-STAGING (sem /rest/v1/): ').strip().rstrip('/')
    ref=input('Reference ID de VENDRA-STAGING: ').strip()
    anon=getpass.getpass('Chave publica anon/publishable SOMENTE do STAGING (oculta): ').strip()
    secret=getpass.getpass('Chave backend secret/service_role SOMENTE do STAGING (oculta): ').strip()
    confirm=input('Digite VENDRA-STAGING para confirmar o destino: ').strip()
    if confirm != 'VENDRA-STAGING':
        print('Confirmacao incorreta. Nenhuma configuracao salva.')
        return 2
    config = {
      'APP_NAME':'VENDRA', 'APP_ENV':'staging','DEMO_MODE':'false','APP_PORT':'8011',
      'PUBLIC_APP_URL':'http://127.0.0.1:8011',
      'SUPABASE_URL':url,'VENDRA_STAGING_REF':ref,
      'SUPABASE_ANON_KEY':anon,'SUPABASE_SERVICE_ROLE_KEY':secret,
      'SECRET_KEY':token_urlsafe(48), 'COOKIE_SECURE':'false', 'SESSION_HOURS':'8',
      'MAKE_WEBHOOK_SECRET':'', 'META_ACCESS_TOKEN':'', 'SMTP_HOST':''
    }
    errors=check_staging(config)
    if errors:
        for error in errors: print('ERRO:',error)
        print('Nenhum arquivo foi gravado. Revise os dados.')
        return 2
    # Encode values, sem interpolacao maliciosa por newline/quotes.
    if any('\n' in value or '\r' in value or '#' in value for value in config.values()):
        print('Valor com caractere proibido. Configuracao cancelada.');return 2
    with TARGET.open('x',encoding='utf8') as f:
        f.write('# Exclusivo da copia de testes. NUNCA incluir em ZIP/release.\n')
        for k,v in config.items():f.write(f'{k}={v}\n')
    try:os.chmod(TARGET,0o600)
    except OSError:pass
    print('Configuracao criada. Chaves nao foram exibidas.')
    return 0

if __name__=='__main__':raise SystemExit(main())
