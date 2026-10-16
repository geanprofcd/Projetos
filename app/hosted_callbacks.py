"""Compoe o portal e a ponte homologada, sem mudar suas rotas ou seu design."""
from contextlib import AsyncExitStack, asynccontextmanager
import os

from fastapi import FastAPI
from app.whatsapp_callbacks import BridgeConfig, create_app


def configuration_from_environment(settings, values=None):
    values = os.environ if values is None else values
    enabled = values.get('VENDRA_BRIDGE_ENABLED', 'false')
    if enabled not in ('true', 'false'):
        raise ValueError('VENDRA_BRIDGE_ENABLED exige true ou false.')
    if enabled == 'false':
        return None
    if (settings.app_env != 'production' or settings.demo_mode
            or settings.supabase_url.rstrip('/') != 'https://znkjibqcikuigfwfsbjb.supabase.co'):
        raise ValueError('Ponte hospedada exige o banco original de producao.')
    def flag(key):
        value = values.get(key, 'false')
        if value not in ('true', 'false'):
            raise ValueError('Flag de ponte invalida: '+key)
        return value == 'true'
    config = BridgeConfig(
        environment='production', project_ref='znkjibqcikuigfwfsbjb',
        supabase_url=settings.supabase_url, backend_key=settings.supabase_service_role_key,
        webhook_secret=values.get('VENDRA_BRIDGE_WEBHOOK_SECRET', ''),
        phone_number_id=values.get('META_PHONE_NUMBER_ID', ''),
        business_account_id=values.get('META_WABA_ID', ''),
        allowed_phones=tuple(p.strip() for p in values.get('VENDRA_BRIDGE_ALLOWED_PHONES', '').split(',') if p.strip()),
        ai_enabled=flag('VENDRA_BRIDGE_AI_ENABLED'),
        dispatch_enabled=flag('VENDRA_BRIDGE_DISPATCH_ENABLED'),
        human_enabled=flag('VENDRA_BRIDGE_HUMAN_ENABLED'),
        allow_all_phones=flag('VENDRA_BRIDGE_ALLOW_ALL_PHONES'))
    config.validate()
    return config


def mount_callbacks(portal, config, *, client=None):
    bridge = create_app(config, client=client)
    @asynccontextmanager
    async def lifespan(app):
        # FastAPI nao executa automaticamente o lifespan de subaplicacoes.
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(portal.router.lifespan_context(portal))
            await stack.enter_async_context(bridge.router.lifespan_context(bridge))
            from app.services.dispatch_list_service import start_worker
            stop,worker=start_worker()
            try:
                yield
            finally:
                stop.set()
                if worker is not None:
                    import asyncio
                    await asyncio.to_thread(worker.join,15)
    root = FastAPI(title='VENDRA', docs_url=None, redoc_url=None,
                   openapi_url=None, lifespan=lifespan)
    root.mount('/callbacks', bridge)
    root.mount('/', portal)
    return root


def create_hosted_app():
    from app.core.config import get_settings
    config = configuration_from_environment(get_settings())
    from app.main import app as portal
    return mount_callbacks(portal, config) if config is not None else portal
