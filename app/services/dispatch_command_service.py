"""Persistent portal command; transport requires explicit server configuration."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from uuid import UUID

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.access_service import level_for
from app.whatsapp_callbacks import canonical_phone


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _new_lead_destination():
    # Keep demo storage and configuration out of module import side effects.
    from app.services.dispatch_service import _new_lead_destination as resolve
    return resolve()


def channel_ready() -> bool:
    settings = get_settings()
    return bool(settings.dispatch_transport_enabled and not settings.demo_mode)


def _transport():
    settings = get_settings()
    if not channel_ready():
        raise ValueError('O envio deste canal está desativado.')
    url = str(settings.dispatch_transport_url or '')
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ValueError('O destino de envio não está configurado corretamente.') from None
    if (parsed.scheme != 'https' or parsed.hostname not in {'hook.us2.make.com', 'hook.eu1.make.com', 'hook.eu2.make.com', 'hook.us1.make.com'}
        or parsed.username or parsed.password or port not in (None, 443)
        or parsed.query or parsed.fragment or not re.fullmatch(r'/[A-Za-z0-9_-]{24,}', parsed.path)):
        raise ValueError('O destino de envio não está configurado corretamente.')
    secret = str(settings.dispatch_transport_secret or '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', secret):
        raise ValueError('A autenticação do canal não está configurada.')
    allowed = {canonical_phone(p.strip()) for p in settings.dispatch_allowed_phones.split(',') if p.strip()}
    if settings.app_env == 'staging' and not allowed:
        raise ValueError('Configure o destinatário autorizado para homologação.')
    return url, secret, allowed


def request_dispatch(*, user: dict, name: str, phone: str, request_id: str) -> dict:
    if user.get('status') != 'active' or level_for(user) not in {'administrativo', 'comercial', 'gerencial'}:
        raise ValueError('Seu perfil não permite solicitar este envio.')
    try:
        actor = str(UUID(str(user.get('id'))))
        nonce = str(UUID(str(request_id)))
    except (TypeError, ValueError, AttributeError):
        raise ValueError('Formulário inválido. Atualize a página.') from None
    name = str(name or '').strip()
    digits = re.sub(r'\D', '', str(phone or ''))
    if not 1 <= len(name) <= 160 or not re.fullmatch(r'55[1-9][0-9][0-9]{8,9}', digits):
        raise ValueError('Informe nome e telefone brasileiro com DDI e DDD.')
    phone = canonical_phone(digits)
    if len(phone) != 12:
        raise ValueError('Telefone brasileiro inválido.')
    url, secret, allowed = _transport()
    if allowed and phone not in allowed:
        raise ValueError('Este telefone não está autorizado para o teste.')
    _, stage_id = _new_lead_destination()
    db = get_admin_client()
    row = db.rpc('vendra_dispatch_request_v1', {
        'p_actor_id': actor, 'p_name': name, 'p_phone': phone,
        'p_stage_id': stage_id, 'p_request_id': nonce,
    }).execute().data
    if (not isinstance(row, dict) or not row.get('id') or row.get('phone') != phone
        or row.get('name') != name or row.get('template_key') != 'continuar_atendimento_vendra'):
        raise RuntimeError('O banco não confirmou o pedido de envio.')
    if row.get('status') != 'pending':
        return {**row, 'transport_confirmed': row.get('status') in {'submitted', 'sent', 'delivered', 'read'}}
    # An uncertain HTTP result never causes a new command or an automatic retry.
    payload = {'dispatch_id': row['id'], 'phone': phone, 'name': name,
               'template_key': row['template_key'], 'dispatch_secret': secret}
    request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode('utf8'),
        headers={'Content-Type': 'application/json', 'User-Agent': 'VENDRA-Dispatch/1'}, method='POST')
    code = None
    try:
        opener = urllib.request.build_opener(_NoRedirect())
        with opener.open(request, timeout=12) as response:
            code = response.status
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    # Never regress provider status if Make finished while the portal waited.
    db.table('dispatches').update({'make_status_code': code,
        'last_error': None if code is not None and 200 <= code < 300 else 'Confirmação do transporte pendente; confira o mesmo pedido.'}
    ).eq('id', row['id']).eq('status', 'pending').execute()
    return {**row, 'transport_confirmed': code is not None and 200 <= code < 300}


def list_dispatches(limit: int = 30) -> list[dict]:
    rows = (get_admin_client().table('dispatches')
        .select('id,name,phone,status,created_at,last_error')
        .order('created_at', desc=True).limit(min(max(limit, 1), 100)).execute().data or [])
    return [{**row, 'phone': '•••• '+str(row.get('phone') or '')[-4:]} for row in rows]
