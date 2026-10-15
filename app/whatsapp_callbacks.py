"""Ponte autenticada de entrada, controle e vinculo, sem worker ou envio direto.

Processo separado, configuracao explicita e SDK restrito ao backend. Nao importa
app.main, demo_store nem os routers do portal. Reutilizavel na hospedagem.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import hmac
import base64
import binascii
import re
from urllib.parse import urlsplit
from uuid import UUID

from dotenv import dotenv_values
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator


def canonical_phone(value: str) -> str:
    digits = re.sub(r'\D', '', value)
    if not re.fullmatch(r'55\d{10,11}', digits):
        raise ValueError('Telefone BR com DDI invalido.')
    if len(digits) == 13 and digits[4] == '9':
        digits = digits[:4] + digits[5:]
    return digits


@dataclass(frozen=True)
class BridgeConfig:
    environment: str
    project_ref: str
    supabase_url: str
    backend_key: str = field(repr=False)
    webhook_secret: str = field(repr=False)
    phone_number_id: str
    business_account_id: str
    allowed_phones: tuple[str, ...]
    ai_enabled: bool = False
    dispatch_enabled: bool = False

    def validate(self) -> None:
        if type(self.ai_enabled) is not bool:
            raise ValueError('Flag IA precisa ser booleana explicita.')
        if type(self.dispatch_enabled) is not bool:
            raise ValueError('Flag de disparos precisa ser booleana explicita.')
        if self.environment not in {'staging', 'production'}:
            raise ValueError('Ambiente explicito obrigatorio.')
        parsed = urlsplit(self.supabase_url)
        if (not re.fullmatch(r'[a-z0-9]{20}', self.project_ref)
                or parsed.scheme != 'https' or parsed.netloc != self.project_ref+'.supabase.co'
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
            raise ValueError('Projeto Supabase divergente da configuracao explicita.')
        if (len(self.backend_key) < 32 or not self.backend_key.startswith(('sb_secret_', 'eyJ'))
                or len(self.webhook_secret) < 32):
            raise ValueError('Credenciais backend/webhook ausentes ou invalidas.')
        if not self.phone_number_id.isdigit() or not self.business_account_id.isdigit():
            raise ValueError('Conta/remetente Meta obrigatorios.')
        if not self.allowed_phones:
            raise ValueError('Destinatarios explicitamente autorizados obrigatorios.')
        for phone in self.allowed_phones:
            canonical_phone(phone)


def load_config(path: Path) -> BridgeConfig:
    """Nao herda .env, variaveis globais, sessoes ou estado do principal."""
    if not path.is_file():
        raise ValueError('Arquivo exclusivo da ponte nao encontrado.')
    values = dotenv_values(path, interpolate=False)
    required = ('APP_ENV', 'VENDRA_BRIDGE_PROJECT_REF', 'SUPABASE_URL',
                'SUPABASE_SERVICE_ROLE_KEY', 'MAKE_WEBHOOK_SECRET',
                'META_PHONE_NUMBER_ID', 'META_WABA_ID', 'VENDRA_BRIDGE_ALLOWED_PHONES')
    if any(not values.get(key) for key in required):
        raise ValueError('Configuracao exclusiva da ponte incompleta.')
    ai_flag = values.get('VENDRA_BRIDGE_AI_ENABLED', 'false')
    if ai_flag not in {'true', 'false'}:
        raise ValueError('VENDRA_BRIDGE_AI_ENABLED exige true ou false explicito.')
    dispatch_flag = values.get('VENDRA_BRIDGE_DISPATCH_ENABLED', 'false')
    if dispatch_flag not in {'true', 'false'}:
        raise ValueError('VENDRA_BRIDGE_DISPATCH_ENABLED exige true ou false explicito.')
    config = BridgeConfig(
        environment=values['APP_ENV'], project_ref=values['VENDRA_BRIDGE_PROJECT_REF'],
        supabase_url=values['SUPABASE_URL'], backend_key=values['SUPABASE_SERVICE_ROLE_KEY'],
        webhook_secret=values['MAKE_WEBHOOK_SECRET'], phone_number_id=values['META_PHONE_NUMBER_ID'],
        business_account_id=values['META_WABA_ID'],
        allowed_phones=tuple(p.strip() for p in values['VENDRA_BRIDGE_ALLOWED_PHONES'].split(',') if p.strip()),
        ai_enabled=ai_flag == 'true', dispatch_enabled=dispatch_flag == 'true')
    config.validate()
    return config


class MetaSource(BaseModel):
    phone_number_id: str = Field(min_length=1, max_length=80)
    business_account_id: str = Field(min_length=1, max_length=80)
    occurred_at: datetime

    @field_validator('occurred_at')
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError('Timestamp precisa incluir fuso horario.')
        return value.astimezone(timezone.utc)


class Inbound(MetaSource):
    phone: str = Field(min_length=8, max_length=30)
    name: str | None = Field(default=None, max_length=180)
    message: str | None = Field(default=None, min_length=1, max_length=10000)
    message_base64: str | None = Field(default=None, max_length=56000)
    name_base64: str | None = Field(default=None, max_length=1000)
    external_message_id: str = Field(min_length=1, max_length=430)

    @model_validator(mode='after')
    def decode_make_text(self):
        # O Make usa base64 para que aspas, quebras e Unicode nao quebrem JSON raw.
        if (self.message is None) == (self.message_base64 is None):
            raise ValueError('Informe exatamente uma representacao da mensagem.')
        try:
            if self.message_base64 is not None:
                self.message = base64.b64decode(self.message_base64, validate=True).decode('utf-8')
            if self.name_base64 is not None:
                if self.name is not None: raise ValueError('Nome duplicado.')
                self.name = base64.b64decode(self.name_base64, validate=True).decode('utf-8')
        except (binascii.Error, UnicodeError):
            raise ValueError('Texto codificado invalido.') from None
        if not self.message.strip() or len(self.message) > 10000 or len(self.name or '') > 180:
            raise ValueError('Texto fora do limite.')
        return self


class ProviderStatus(MetaSource):
    provider_message_id: str = Field(min_length=1, max_length=430)
    status: str = Field(pattern='^(sent|delivered|read|failed)$')
    recipient_id: str = Field(min_length=8, max_length=30)
    error_message: str | None = Field(default=None, max_length=1000)


class AIReply(Inbound):
    ticket_id: UUID
    inbound_message_id: UUID
    control_version: int = Field(ge=1)
    route_code: str = Field(default='1', pattern='^[123]$')
    delivery_mode: str = Field(default='inline_make', pattern='^inline_make$')


class OutboxBinding(MetaSource):
    provider_message_id: str = Field(min_length=1, max_length=430)
    claim_token: SecretStr = Field(min_length=32, max_length=100)
    recipient_id: str = Field(min_length=8, max_length=30)
    status: str = Field(default='sent', pattern='^sent$')


class DispatchPrepare(MetaSource):
    phone: str = Field(min_length=8, max_length=30)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    name_base64: str | None = Field(default=None, max_length=1000)
    template_key: str = Field(pattern='^continuar_atendimento_vendra$')

    @model_validator(mode='after')
    def decode_name(self):
        if (self.name is None) == (self.name_base64 is None):
            raise ValueError('Informe exatamente uma representacao do nome.')
        if self.name_base64 is not None:
            try:
                self.name = base64.b64decode(self.name_base64, validate=True).decode('utf-8')
            except (binascii.Error, UnicodeError):
                raise ValueError('Nome codificado invalido.') from None
        if not self.name.strip() or len(self.name) > 160:
            raise ValueError('Nome fora do limite.')
        return self


class DispatchBinding(OutboxBinding):
    outbox_id: UUID


def create_app(config: BridgeConfig, *, client=None) -> FastAPI:
    config.validate()
    if client is None:
        from supabase import create_client
        client = create_client(config.supabase_url, config.backend_key)
    allowed = {canonical_phone(p) for p in config.allowed_phones}
    app = FastAPI(title='VENDRA - callbacks WhatsApp', docs_url=None,
                  redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def headers(request, call_next):
        # Limite aplicado antes de desserializar JSON (inclui corpos chunked).
        if request.method == 'POST':
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 65536:
                    from fastapi.responses import JSONResponse
                    return JSONResponse({'detail': 'Payload excede 64 KB.'}, status_code=413)
                chunks.append(chunk)
            request._body = b''.join(chunks)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def authenticate(secret: str | None) -> None:
        if not secret or not hmac.compare_digest(secret.encode('utf-8'), config.webhook_secret.encode('utf-8')):
            raise HTTPException(401, 'Webhook nao autorizado.')

    def authorize(secret: str | None, payload: MetaSource, phone: str) -> bool:
        authenticate(secret)
        if (payload.phone_number_id != config.phone_number_id
                or payload.business_account_id != config.business_account_id):
            raise HTTPException(403, 'Conta/remetente Meta divergentes.')
        try:
            return canonical_phone(phone) in allowed
        except ValueError:
            raise HTTPException(422, 'Telefone invalido.') from None

    def rpc(name: str, params: dict) -> dict:
        try:
            result = client.rpc(name, params).execute().data
        except Exception as exc:
            code = str(getattr(exc, 'code', ''))
            status = {'PT409': 409, '22023': 422, '42501': 403}.get(code, 503)
            raise HTTPException(status, 'Callback nao persistido; consultar o diagnostico do servidor.') from None
        if not isinstance(result, dict) or result.get('accepted') is not True:
            raise HTTPException(503, 'Banco nao confirmou o callback.')
        return result

    def lookup(table: str, columns: str, entity_id: UUID | str) -> dict:
        try:
            rows = client.table(table).select(columns).eq('id', str(entity_id)).limit(1).execute().data
        except Exception:
            raise HTTPException(503, 'Nao foi possivel validar o escopo da entidade.') from None
        if not rows:
            raise HTTPException(404, 'Entidade nao encontrada.')
        return rows[0]

    def check_entity_phone(phone: str | None, supplied_phone: str | None = None) -> None:
        try:
            actual = canonical_phone(phone or '')
            valid = actual in allowed and (supplied_phone is None or actual == canonical_phone(supplied_phone))
        except ValueError:
            valid = False
        if not valid:
            raise HTTPException(403, 'Entidade fora do escopo autorizado.')

    def ticket_scope(ticket_id: UUID, supplied_phone: str | None = None) -> None:
        ticket = lookup('tickets', 'customer_id,source', ticket_id)
        if ticket['source'] != 'whatsapp':
            raise HTTPException(403, 'Atendimento fora do canal autorizado.')
        customer = lookup('customers', 'phone_normalized', ticket['customer_id'])
        check_entity_phone(customer['phone_normalized'], supplied_phone)

    @app.get('/health')
    def health():
        return {'status': 'ok', 'environment': config.environment,
                'component': 'whatsapp_callbacks_v1', 'external_sends_enabled': False,
                'ai_enabled': config.ai_enabled, 'dispatch_enabled': config.dispatch_enabled,
                'persistence': 'supabase'}

    @app.post('/webhooks/make/whatsapp', status_code=202)
    def inbound(payload: Inbound, x_webhook_secret: str | None = Header(default=None)):
        if not authorize(x_webhook_secret, payload, payload.phone):
            return {'accepted': True, 'ignored': True, 'reason': 'outside_test_scope'}
        result = rpc('vendra_whatsapp_receive_v1', {
            'p_phone': payload.phone, 'p_name': payload.name, 'p_body': payload.message,
            'p_external_message_id': payload.external_message_id,
            'p_occurred_at': payload.occurred_at.isoformat()})
        result['automation'] = {'enabled': False, 'mode': 'human', 'connected': False,
            'route_to_ai': False, 'should_respond': False, 'control_version': 1,
            'make_instruction': 'STOP_AT_VENDRA', 'thread_id': 'VENDRA-'+str(result['ticket_id'])}
        if config.ai_enabled:
            control = rpc('vendra_whatsapp_control_v1', {'p_ticket_id': result['ticket_id']})
            route = control.get('route_to_ai') is True and result.get('duplicate') is False
            control.update(route_to_ai=route, should_respond=route,
                           make_instruction='CONTINUE_TO_AI' if route else 'STOP_AT_VENDRA')
            result['automation'] = control
        return result

    @app.post('/webhooks/make/whatsapp/provider-status', status_code=202)
    def provider_status(payload: ProviderStatus, x_webhook_secret: str | None = Header(default=None)):
        if not authorize(x_webhook_secret, payload, payload.recipient_id):
            return {'accepted': True, 'ignored': True, 'reason': 'outside_test_scope'}
        function = 'vendra_dispatch_provider_status_v1' if config.dispatch_enabled else 'vendra_whatsapp_status_v1'
        return rpc(function, {
            'p_provider_message_id': payload.provider_message_id, 'p_status': payload.status,
            'p_occurred_at': payload.occurred_at.isoformat(), 'p_recipient_id': payload.recipient_id,
            'p_error_message': payload.error_message})

    # Vincular aceite do provedor nao autoriza nenhum envio; disponivel com IA desligada.
    @app.post('/webhooks/make/whatsapp/outbox/{outbox_id}/status', status_code=202)
    def bind_status(outbox_id: UUID, payload: OutboxBinding,
                    x_webhook_secret: str | None = Header(default=None)):
        if not authorize(x_webhook_secret, payload, payload.recipient_id):
            raise HTTPException(403, 'Destinatario fora do escopo autorizado.')
        item = lookup('whatsapp_outbox', 'phone', outbox_id)
        check_entity_phone(item['phone'], payload.recipient_id)
        return rpc('vendra_whatsapp_bind_v1', {'p_outbox_id': str(outbox_id),
            'p_provider_message_id': payload.provider_message_id,
            'p_claim_token': payload.claim_token.get_secret_value()})

    if config.dispatch_enabled:
        def dispatch_scope(dispatch_id: UUID, phone: str) -> dict:
            item = lookup('dispatches', 'phone,ticket_id', dispatch_id)
            check_entity_phone(item['phone'], phone)
            ticket_scope(item['ticket_id'], phone)
            return item

        @app.post('/webhooks/make/disparos/{dispatch_id}/prepare', status_code=202)
        def dispatch_prepare(dispatch_id: UUID, payload: DispatchPrepare,
                             x_webhook_secret: str | None = Header(default=None)):
            if not authorize(x_webhook_secret, payload, payload.phone):
                raise HTTPException(403, 'Destinatario fora do escopo autorizado.')
            dispatch_scope(dispatch_id, payload.phone)
            result = rpc('vendra_dispatch_prepare_v1', {'p_dispatch_id': str(dispatch_id),
                'p_phone': payload.phone, 'p_name': payload.name, 'p_template_key': payload.template_key})
            if result.get('authorized') is True:
                outbox = result.get('outbox')
                if not isinstance(outbox, dict):
                    raise HTTPException(503, 'Banco nao confirmou a reserva do disparo.')
                check_entity_phone(outbox.get('phone'), payload.phone)
            return result

        @app.post('/webhooks/make/disparos/{dispatch_id}/status', status_code=202)
        def dispatch_bind(dispatch_id: UUID, payload: DispatchBinding,
                          x_webhook_secret: str | None = Header(default=None)):
            if not authorize(x_webhook_secret, payload, payload.recipient_id):
                raise HTTPException(403, 'Destinatario fora do escopo autorizado.')
            dispatch_scope(dispatch_id, payload.recipient_id)
            item = lookup('whatsapp_outbox', 'phone', payload.outbox_id)
            check_entity_phone(item['phone'], payload.recipient_id)
            return rpc('vendra_dispatch_bind_v1', {'p_dispatch_id': str(dispatch_id),
                'p_outbox_id': str(payload.outbox_id), 'p_provider_message_id': payload.provider_message_id,
                'p_claim_token': payload.claim_token.get_secret_value()})

    if config.ai_enabled:
        @app.get('/webhooks/make/ai/control/{ticket_id}')
        def ai_control(ticket_id: UUID, x_webhook_secret: str | None = Header(default=None)):
            authenticate(x_webhook_secret)
            ticket_scope(ticket_id)
            return rpc('vendra_whatsapp_control_v1', {'p_ticket_id': str(ticket_id)})

        @app.post('/webhooks/make/ai/reply', status_code=202)
        def ai_reply(payload: AIReply, x_webhook_secret: str | None = Header(default=None)):
            if not authorize(x_webhook_secret, payload, payload.phone):
                raise HTTPException(403, 'Destinatario fora do escopo autorizado.')
            ticket_scope(payload.ticket_id, payload.phone)
            # Marcador tecnico de roteamento nao deve ir para o cliente.
            body = re.sub(r'\s*#[123]\s*$', '', payload.message).strip()
            if not body:
                raise HTTPException(422, 'Resposta vazia apos remover marcador tecnico.')
            result = rpc('vendra_whatsapp_ai_prepare_v1', {
                'p_ticket_id': str(payload.ticket_id), 'p_inbound_message_id': str(payload.inbound_message_id),
                'p_body': body, 'p_expected_version': payload.control_version})
            if result.get('authorized') is True:
                outbox = result.get('outbox')
                if not isinstance(outbox, dict):
                    raise HTTPException(503, 'Banco nao confirmou a saida autorizada.')
                # Conferir novamente a reserva: o telefone pode mudar entre leitura e RPC.
                check_entity_phone(outbox.get('phone'), payload.phone)
            return result
    return app
