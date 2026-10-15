"""STAGING integrated portal. Dispatch transport defaults to disabled."""
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import get_settings
from app.core.ui import templates
from app.dependencies.auth import current_user
from app.services.auth_service import COOKIE_NAME, get_session_user
from app.services.access_service import allowed
from app.routers import (auth, users, staging_customers, staging_attendance, staging_crm,
    staging_dispatch_preview, staging_dispatch_lifecycle, staging_delivery_preflight, staging_transport_contract,
    dispatch_commands, whatsapp_conversations)
from tools.staging_guard import assert_staging
from fastapi import Depends, APIRouter

assert_staging()
settings = get_settings()
app = FastAPI(title='VENDRA STAGING H1-006H', docs_url=None, redoc_url=None, openapi_url=None)
app.mount('/static', StaticFiles(directory='app/static'), name='static')
templates.env.globals['allowed'] = lambda user, module: module in (
    'clientes','usuarios','atendimentos','oportunidades','disparos') and allowed(user, module)
templates.env.globals.update(vendra_integrated_portal=True,
                            vendra_whatsapp_portal=True,
                            vendra_dispatch_live=settings.dispatch_transport_enabled)


@app.middleware('http')
async def module_gate(request: Request, call_next):
    if request.url.path.startswith(('/clientes','/usuarios','/atendimentos','/oportunidades','/disparos','/conversas')):
        request.state.vendra_user = get_session_user(request.cookies.get(COOKIE_NAME))
    response = await call_next(request)
    if request.url.path.startswith(('/static','/disparos','/conversas')):
        response.headers.update({'Cache-Control':'no-store','Pragma':'no-cache',
            'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'})
    return response


@app.get('/')
def home(user: dict = Depends(current_user)):
    return RedirectResponse('/clientes', status_code=303)


@app.get('/health')
def health():
    return {'status':'ok','environment':'staging','stage':'H1-006H','supabase_mode':True,
        'external_sends_enabled':settings.dispatch_transport_enabled,'worker_enabled':False}


for router in (auth.router, staging_customers.router, staging_crm.router, staging_dispatch_preview.router,
    staging_dispatch_lifecycle.router, staging_delivery_preflight.router, staging_transport_contract.router,
    dispatch_commands.router, whatsapp_conversations.router, users.router):
    app.include_router(router)
internal = APIRouter()
internal.routes.extend(route for route in staging_attendance.router.routes if getattr(route,'path',None) != '/oportunidades')
app.include_router(internal)
