from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings, installed_version
from app.routers import auth, customers, dashboard, dispatches, funnels, indicators, integrations, operations, opportunities, products, tickets
from app.services.admin_settings_service import get_whatsapp_settings, list_webhooks
from app.services.demo_store import persist_demo_state
from app.services.auth_service import COOKIE_NAME, get_session_user
from app.services.access_service import module_for_path, allowed


settings = get_settings()
app = FastAPI(title=settings.app_name)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.middleware("http")
async def development_cache_control(request, call_next):
    response = await call_next(request)
    if settings.app_env != "production" and request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.middleware("http")
async def persist_demo_data(request, call_next):
    """Persiste o estado operacional local após cada requisição no modo demo.

    Isso mantém clientes, atendimentos, mensagens, metadados de anexos,
    eventos de integração e outbox entre reinícios e atualizações.
    """
    response = await call_next(request)
    if settings.demo_mode:
        persist_demo_state()
    return response


@app.middleware("http")
async def enforce_module_access(request: Request, call_next):
    """Proíbe URLs diretas, POSTs e APIs mesmo sem menu lateral visível.

    Rotas externas /webhooks não passam por autorização de usuário de sessão.
    """
    module = module_for_path(request.url.path)
    if module:
        user = get_session_user(request.cookies.get(COOKIE_NAME))
        request.state.vendra_user = user
        if user and not allowed(user, module):
            return JSONResponse({"detail": "Sem permissão para esta área."}, status_code=403)
    return await call_next(request)


app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(customers.router)
app.include_router(products.router)
app.include_router(funnels.router)
app.include_router(indicators.router)
app.include_router(dispatches.router)
app.include_router(opportunities.router)
app.include_router(tickets.router)
app.include_router(integrations.router)
app.include_router(operations.router)
from app.routers import users
app.include_router(users.router)
from app.routers import meta_templates
app.include_router(meta_templates.router)


@app.get("/health")
def health():
    try:
        hooks = list_webhooks()
        bridge_configured = bool(settings.make_webhook_secret) or any(row.get("active") and row.get("kind") == "whatsapp_text" for row in hooks)
        whatsapp_enabled = bool(get_whatsapp_settings().get("enabled"))
    except Exception:
        bridge_configured = bool(settings.make_webhook_secret)
        whatsapp_enabled = False
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": installed_version(),
        "demo_mode": settings.demo_mode,
        "supabase_configured": settings.supabase_configured,
        "webhook_bridge_configured": bridge_configured,
        "whatsapp_channel_enabled": whatsapp_enabled,
    }
