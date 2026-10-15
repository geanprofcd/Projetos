"""Validate staging environment configuration without printing secrets or calling Supabase."""
import os
from urllib.parse import urlsplit

def validate_config(env:dict):
    errors=[]
    if env.get('APP_ENV','').lower() not in {'staging','homologation'}: errors.append('APP_ENV deve ser staging.')
    if env.get('DEMO_MODE','').strip().lower() not in {'false','0'}: errors.append('DEMO_MODE deve ser false APENAS na cópia isolada.')
    url=env.get('SUPABASE_URL','').strip(); host=urlsplit(url).hostname if url else None
    if not host or not host.endswith('.supabase.co') or urlsplit(url).path not in ('','/'):
        errors.append('SUPABASE_URL precisa ser a URL-base de STAGING, sem /rest/v1/.')
    ref=env.get('VENDRA_STAGING_REF','').strip()
    if not ref or host != f'{ref}.supabase.co': errors.append('Project Reference ID não corresponde à URL.')
    for field in ('SUPABASE_ANON_KEY','SUPABASE_SERVICE_ROLE_KEY','SECRET_KEY'):
        if not env.get(field,'').strip() or env.get(field,'').strip() in {'change-me','SEU-SEGREDO'}:
            errors.append(f'{field} não configurado.')
    return errors

if __name__=='__main__':
    # Environment values should be provided by a dedicated staging launcher; avoid reading production .env.
    failures=validate_config(os.environ)
    if failures:
        print('PREFLIGHT NÃO APROVADO:')
        for x in failures:print('- '+x)
        raise SystemExit(2)
    print('PREFLIGHT OK. Somente validação de configuração local; nenhum acesso ao banco executado.')
