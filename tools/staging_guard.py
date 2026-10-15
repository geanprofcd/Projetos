"""Gate para a instancia VENDRA H1-005B2. Nao consultar producao por engano."""
from __future__ import annotations
import os
from urllib.parse import urlsplit


def check_staging(env=None):
    env = os.environ if env is None else env
    problems = []
    if env.get('APP_ENV','').strip().lower() != 'staging':
        problems.append('APP_ENV deve ser staging')
    if env.get('DEMO_MODE','').strip().lower() not in ('false', '0'):
        problems.append('DEMO_MODE deve ser false somente na copia de testes')
    ref = env.get('VENDRA_STAGING_REF', '').strip()
    url = env.get('SUPABASE_URL','').strip()
    parsed = urlsplit(url)
    if not ref or not ref.isalnum() or len(ref) < 8:
        problems.append('VENDRA_STAGING_REF nao configurado')
    if parsed.scheme != 'https' or parsed.hostname != (ref + '.supabase.co') or parsed.path not in ('','/') or parsed.query or parsed.fragment:
        problems.append('SUPABASE_URL deve ser a URL raiz do projeto STAGING indicado pelo Reference ID')
    for field in ('SUPABASE_ANON_KEY','SUPABASE_SERVICE_ROLE_KEY','SECRET_KEY'):
        val = env.get(field, '').strip()
        if len(val) < 24 or 'SUA_' in val or 'SEU_' in val or 'change-me' in val:
            problems.append(field + ' nao configurado adequadamente')
    pub=env.get('SUPABASE_ANON_KEY','').strip()
    sec=env.get('SUPABASE_SERVICE_ROLE_KEY','').strip()
    if pub and not pub.startswith(('sb_publishable_','eyJ')):
        problems.append('SUPABASE_ANON_KEY deve ser chave publishable/anon do STAGING')
    if sec and not sec.startswith(('sb_secret_','eyJ')):
        problems.append('SUPABASE_SERVICE_ROLE_KEY deve ser secret/service_role do STAGING')
    if sec and sec == pub:
        problems.append('A chave backend deve ser diferente da publica')
    if env.get('META_ACCESS_TOKEN') or env.get('MAKE_WEBHOOK_SECRET') or env.get('SMTP_HOST'):
        problems.append('Meta, Make e SMTP devem permanecer sem configuracao nesta etapa')
    return problems


def assert_staging(env=None):
    problems = check_staging(env)
    if problems:
        raise RuntimeError('CONFIGURACAO STAGING BLOQUEADA: ' + '; '.join(problems))
