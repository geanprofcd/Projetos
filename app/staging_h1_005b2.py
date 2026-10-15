"""App independente da H1-005B2 para homologar Auth + Clientes em Supabase STAGING.

Exclui intencionalmente rotas de Disparos, Meta, Make, webhooks, IA e trabalhos assíncronos.
"""
from __future__ import annotations
import os
from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import get_settings
from app.dependencies.auth import current_user
from app.services.auth_service import COOKIE_NAME, get_session_user
from app.services.access_service import allowed, module_for_path
from app.core.ui import templates
from app.routers import auth, users
from app.routers import staging_customers
from tools.staging_guard import assert_staging

# Falhar fechado antes de carregar as rotas se o ambiente estiver errado.
assert_staging()
settings=get_settings()
app=FastAPI(title='VENDRA - STAGING H1-005B2',docs_url=None,redoc_url=None,openapi_url=None)
app.mount('/static',StaticFiles(directory='app/static'),name='static')

_orig_allowed = allowed
templates.env.globals['allowed'] = lambda u, m: m in ('clientes','usuarios') and _orig_allowed(u,m)

@app.middleware('http')
async def module_gate(request:Request, call_next):
    path=request.url.path
    # A propria inclusao seletiva de routers evita rotas de envio e operacoes ainda nao migradas.
    if path.startswith('/clientes') or path.startswith('/usuarios'):
        u=get_session_user(request.cookies.get(COOKIE_NAME))
        request.state.vendra_user=u
    response=await call_next(request)
    if path.startswith('/static'):
        response.headers['Cache-Control']='no-store'
    return response

@app.get('/')
def home(user:dict=Depends(current_user)):
    return RedirectResponse('/clientes',status_code=303)

@app.get('/health')
def health():
    return {'status':'ok','environment':'staging','stage':'H1-005B2','supabase_mode':True,
            'external_sends_enabled':False}

app.include_router(auth.router)
app.include_router(staging_customers.router)
app.include_router(users.router)
