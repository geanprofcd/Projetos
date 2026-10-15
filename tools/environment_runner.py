#!/usr/bin/env python3
"""Execução de instâncias isoladas VENDRA (Windows ou Linux).

Principal: código/dados atuais em 127.0.0.1:8010.
Homologação: cópia independente em pasta irmã e 127.0.0.1:8011.
Não faz publish, não copia credenciais, não mistura dados, não liga integrações externas.
"""
from __future__ import annotations
import argparse
import os
import secrets
import shutil
import subprocess
import sys
import venv
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
STAGE=PROJECT.parent/(PROJECT.name+'_HOMOLOGACAO')
STAGING_PORT='8011'
EXTERNAL_KEYS = ('META_ACCESS_TOKEN','META_WABA_ID','META_PHONE_NUMBER_ID','MAKE_WEBHOOK_SECRET',
                 'SUPABASE_URL','SUPABASE_ANON_KEY','SUPABASE_SERVICE_ROLE_KEY',
                 'SMTP_HOST','SMTP_USER','SMTP_PASSWORD','SMTP_FROM')
COPY_FILES=('requirements.txt','version.json')
COPY_DIRS=('app',)  # não copiar ferramentas secretas, runtime, venv, dados, .env

def python_in_venv(folder:Path)->Path:
    return folder/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')

def stage_env():
    env=os.environ.copy()
    env.update({k:'' for k in EXTERNAL_KEYS})
    env.update(APP_ENV='staging',DEMO_MODE='true',COOKIE_SECURE='false',
               PUBLIC_APP_URL='http://127.0.0.1:8011',
               VENDRA_LOCAL_CONFIG=str(STAGE/'.vendra-data'/'admin_integrations.json'),
               VENDRA_DEMO_STATE_FILE=str(STAGE/'.vendra-data'/'demo_state.json'))
    return env

def prepare_staging():
    if STAGE.exists():
        if not (STAGE/'STAGING_ONLY.marker').is_file():
            raise SystemExit('A pasta de homologação existe sem marcador. Não vou sobrescrevê-la: '+str(STAGE))
        print('Homologação já preparada: '+str(STAGE))
        print('Para testar novas releases, atualize somente esta pasta e execute INICIAR_VENDRA_TESTE.cmd.')
        return
    print('Criando ambiente de homologação independente: '+str(STAGE))
    STAGE.mkdir(parents=True)
    (STAGE/'STAGING_ONLY.marker').write_text('Ambiente de teste isolado; não apontar domínio público.\n',encoding='utf-8')
    try:
        for d in COPY_DIRS:
            shutil.copytree(PROJECT/d,STAGE/d,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for f in COPY_FILES:shutil.copy2(PROJECT/f,STAGE/f)
        (STAGE/'.vendra-data').mkdir(exist_ok=True)
        # Não copia .env real ou credenciais do Windows. A senha demo padrão só vale no teste.
        (STAGE/'.env').write_text('\n'.join([
            'APP_NAME=VENDRA - HOMOLOGACAO','APP_ENV=staging','DEMO_MODE=true',
            'COOKIE_SECURE=false','PUBLIC_APP_URL=http://127.0.0.1:8011',
            'SECRET_KEY='+secrets.token_hex(32),
            'META_ACCESS_TOKEN=','META_WABA_ID=','META_PHONE_NUMBER_ID=',
            'MAKE_WEBHOOK_SECRET=','SUPABASE_URL=','SUPABASE_ANON_KEY=',
            'SUPABASE_SERVICE_ROLE_KEY=','SMTP_HOST=','SMTP_USER=','SMTP_PASSWORD=','SMTP_FROM=',
        ])+'\n',encoding='utf-8')
        py=python_in_venv(STAGE)
        venv.EnvBuilder(with_pip=True).create(STAGE/'.venv')
        print('Instalando dependências no Python independente de homologação...')
        subprocess.run([str(py),'-m','pip','install','-r','requirements.txt'],cwd=STAGE,check=True,env=stage_env())
    except Exception:
        print('PREPARO INCOMPLETO. Corrija o erro antes de iniciar os testes.')
        raise
    print('Ambiente pronto; produção não foi alterada: '+str(STAGE))

def start_main():
    py=python_in_venv(PROJECT)
    if not py.exists():raise SystemExit('Ambiente principal .venv não localizado. Execute: py -m venv .venv; .venv\\Scripts\\python.exe -m pip install -r requirements.txt')
    print('VENDRA principal — http://127.0.0.1:8010 — dados e integrações habituais')
    subprocess.run([str(py),'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8010'],cwd=PROJECT,check=True)

def start_staging():
    if not (STAGE/'STAGING_ONLY.marker').exists():
        raise SystemExit('Homologação não preparada: execute PREPARAR_VENDRA_TESTE.cmd primeiro.')
    py=python_in_venv(STAGE)
    if not py.exists():raise SystemExit('Faltou preparar dependências de homologação (.venv).')
    print('VENDRA HOMOLOGAÇÃO — http://127.0.0.1:8011 — demonstração isolada / sem integrações')
    subprocess.run([str(py),'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',STAGING_PORT],cwd=STAGE,env=stage_env(),check=True)

def main():
    parser=argparse.ArgumentParser(description='VENDRA - serviços independentes principal/teste')
    parser.add_argument('command',choices=['principal','preparar-teste','teste','diagnostico'])
    args=parser.parse_args()
    if args.command=='principal':start_main()
    elif args.command=='preparar-teste':prepare_staging()
    elif args.command=='teste':start_staging()
    else:
        print('Principal:',PROJECT,'| 127.0.0.1:8010')
        print('Homologação:',STAGE,'| 127.0.0.1:8011')
        print('Teste preparado:',(STAGE/'STAGING_ONLY.marker').exists())
        print('Ambientes independentes de código, dados, configuração e Python. TESTE não faz publicação.')
if __name__=='__main__':main()
