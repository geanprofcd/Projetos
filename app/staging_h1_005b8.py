"""Aplicacao VENDRA H1-005B8 - somente testes. Nenhuma rota de integracao externa."""
from fastapi import FastAPI,Request,Depends,APIRouter
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import get_settings
from app.dependencies.auth import current_user
from app.services.auth_service import COOKIE_NAME,get_session_user
from app.services.access_service import allowed
from app.core.ui import templates
from app.routers import (auth,users,staging_customers,staging_attendance,staging_crm,
                         staging_dispatch_preview,staging_dispatch_lifecycle,staging_delivery_preflight,staging_transport_contract)
from tools.staging_guard import assert_staging

assert_staging()
settings=get_settings()
app=FastAPI(title='VENDRA STAGING H1-005B8',docs_url=None,redoc_url=None,openapi_url=None)
app.mount('/static',StaticFiles(directory='app/static'),name='static')
_original_allowed=allowed
templates.env.globals['allowed']=lambda u,m: m in (
    'clientes','usuarios','atendimentos','oportunidades','disparos') and _original_allowed(u,m)

@app.middleware('http')
async def module_gate(request:Request,call_next):
    path=request.url.path
    if path.startswith(('/clientes','/usuarios','/atendimentos','/oportunidades','/disparos')):
        request.state.vendra_user=get_session_user(request.cookies.get(COOKIE_NAME))
    response=await call_next(request)
    if path.startswith('/static'):response.headers['Cache-Control']='no-store'
    return response

@app.get('/')
def home(user:dict=Depends(current_user)):
    return RedirectResponse('/clientes',status_code=303)

@app.get('/health')
def health():
    return {'status':'ok','environment':'staging','stage':'H1-005B8',
            'supabase_mode':True,'external_sends_enabled':False,
            'simulation_only':True}

app.include_router(auth.router)
app.include_router(staging_customers.router)
app.include_router(staging_crm.router)
app.include_router(staging_dispatch_preview.router)
app.include_router(staging_dispatch_lifecycle.router)
app.include_router(staging_delivery_preflight.router)
app.include_router(staging_transport_contract.router)
_internal=APIRouter()
_internal.routes.extend(r for r in staging_attendance.router.routes
                        if getattr(r,'path',None)!='/oportunidades')
app.include_router(_internal)
app.include_router(users.router)
