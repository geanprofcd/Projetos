"""Ponte autenticada de entrada, controle e vinculo, sem worker ou envio direto.

Processo separado, configuracao explicita e SDK restrito ao backend. Nao importa
app.main, demo_store nem os routers do portal. Reutilizavel na hospedagem.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hmac
import base64
import binascii
import re
import logging
from urllib.parse import urlsplit
from uuid import UUID
from contextlib import asynccontextmanager

from dotenv import dotenv_values
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

logger = logging.getLogger(__name__)


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
    human_enabled: bool = False
    allow_all_phones: bool = False
    media_enabled: bool = False
    inbound_media_enabled: bool = False

    def validate(self) -> None:
        if type(self.inbound_media_enabled) is not bool:
            raise ValueError('Flag de recepcao de midia precisa ser booleana explicita.')
        if type(self.media_enabled) is not bool or (self.media_enabled and not self.human_enabled):
            raise ValueError('Midia exige flag booleana e canal humano habilitado.')
        if type(self.ai_enabled) is not bool:
            raise ValueError('Flag IA precisa ser booleana explicita.')
        if type(self.dispatch_enabled) is not bool:
            raise ValueError('Flag de disparos precisa ser booleana explicita.')
        if type(self.human_enabled) is not bool:
            raise ValueError('Flag de saida humana precisa ser booleana explicita.')
        if type(self.allow_all_phones) is not bool or (self.allow_all_phones and self.environment != 'production'):
            raise ValueError('Escopo geral exige producao e autorizacao explicita.')
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
        if not self.allowed_phones and not self.allow_all_phones:
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
    human_flag = values.get('VENDRA_BRIDGE_HUMAN_ENABLED', 'false')
    media_flag = values.get('VENDRA_BRIDGE_MEDIA_ENABLED', 'false')
    inbound_media_flag = values.get('VENDRA_BRIDGE_INBOUND_MEDIA_ENABLED', 'false')
    if inbound_media_flag not in {'true','false'}:
        raise ValueError('VENDRA_BRIDGE_INBOUND_MEDIA_ENABLED exige true ou false explicito.')
    if media_flag not in {'true','false'}:
        raise ValueError('VENDRA_BRIDGE_MEDIA_ENABLED exige true ou false explicito.')
    if human_flag not in {'true', 'false'}:
        raise ValueError('VENDRA_BRIDGE_HUMAN_ENABLED exige true ou false explicito.')
    config = BridgeConfig(
        environment=values['APP_ENV'], project_ref=values['VENDRA_BRIDGE_PROJECT_REF'],
        supabase_url=values['SUPABASE_URL'], backend_key=values['SUPABASE_SERVICE_ROLE_KEY'],
        webhook_secret=values['MAKE_WEBHOOK_SECRET'], phone_number_id=values['META_PHONE_NUMBER_ID'],
        business_account_id=values['META_WABA_ID'],
        allowed_phones=tuple(p.strip() for p in values['VENDRA_BRIDGE_ALLOWED_PHONES'].split(',') if p.strip()),
        ai_enabled=ai_flag == 'true', dispatch_enabled=dispatch_flag == 'true', human_enabled=human_flag == 'true', media_enabled=media_flag == 'true',
        inbound_media_enabled=inbound_media_flag == 'true')
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


class InboundMedia(MetaSource):
    phone: str = Field(min_length=8, max_length=30)
    name_base64: str = Field(default='', max_length=1000)
    caption_base64: str = Field(default='', max_length=56000)
    external_message_id: str = Field(min_length=1, max_length=430)
    media_id: str = Field(pattern=r'^\d{1,80}$')
    media_type: str = Field(pattern='^(image|document|audio|video)$')
    mime_type: str = Field(min_length=1, max_length=80)
    file_name_base64: str = Field(default='', max_length=1200)
    content_base64: SecretStr = Field(min_length=1, max_length=22369624)
    sha256: str = Field(min_length=40, max_length=64)

    @field_validator('mime_type')
    @classmethod
    def canonical_mime(cls, value):
        return value.split(';', 1)[0].strip().lower()

    @field_validator('occurred_at')
    @classmethod
    def valid_media_timestamp(cls, value):
        if value < datetime(2020,1,1,tzinfo=timezone.utc) or value > datetime.now(timezone.utc)+timedelta(seconds=60):
            raise ValueError('Timestamp de midia fora do intervalo permitido.')
        return value


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


class HumanPrepare(MetaSource):
    phone: str | None = Field(default=None,min_length=8, max_length=30)
    expected_ticket_id: UUID | None = None


class UncertainSend(MetaSource):
    recipient_id: str = Field(min_length=8,max_length=30)
    claim_token: SecretStr = Field(min_length=32,max_length=100)


def create_app(config: BridgeConfig, *, client=None) -> FastAPI:
    config.validate()
    transport = None
    if client is None:
        import httpx
        from supabase import create_client
        from supabase.lib.client_options import SyncClientOptions
        # HTTP/1.1 evita erros de protocolo reproduzidos com callbacks concorrentes.
        # Nao repetir escritas automaticamente quando o resultado for incerto.
        transport = httpx.Client(http2=False, timeout=30, follow_redirects=False)
        client = create_client(config.supabase_url, config.backend_key,
            options=SyncClientOptions(httpx_client=transport, auto_refresh_token=False, persist_session=False))
    allowed = {canonical_phone(p) for p in config.allowed_phones}

    @asynccontextmanager
    async def lifespan(_):
        try:
            yield
        finally:
            if transport is not None:
                transport.close()

    app = FastAPI(title='VENDRA - callbacks WhatsApp', docs_url=None,
                  redoc_url=None, openapi_url=None, lifespan=lifespan)

    def media_path(path):
        return path.rstrip('/').endswith('/webhooks/make/whatsapp/media')

    from fastapi.exceptions import RequestValidationError
    from fastapi.exception_handlers import request_validation_exception_handler
    from fastapi.responses import JSONResponse

    @app.exception_handler(RequestValidationError)
    async def safe_media_validation(request, exc):
        if media_path(request.url.path):
            # O JSON do erro padrão pode reproduzir o arquivo inteiro e dados pessoais.
            return JSONResponse({'detail': 'Payload de midia invalido.'}, status_code=422)
        return await request_validation_exception_handler(request, exc)

    @app.middleware('http')
    async def headers(request, call_next):
        # Limite aplicado antes de desserializar JSON (inclui corpos chunked).
        if request.method == 'POST':
            limit = 65536
            if media_path(request.url.path) and config.inbound_media_enabled:
                secret = request.headers.get('x-webhook-secret', '')
                if not hmac.compare_digest(secret.encode('utf8'), config.webhook_secret.encode('utf8')):
                    return JSONResponse({'detail': 'Webhook nao autorizado.'}, status_code=401,
                                        headers={'Cache-Control': 'no-store'})
                limit = 23 * 1024 * 1024
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    return JSONResponse({'detail': 'Payload excede o limite da rota.'}, status_code=413,
                                        headers={'Cache-Control': 'no-store'})
                chunks.append(chunk)
            request._body = b''.join(chunks)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def authenticate(secret: str | None) -> None:
        if not secret or not hmac.compare_digest(secret.encode('utf-8'), config.webhook_secret.encode('utf-8')):
            raise HTTPException(401, 'Webhook nao autorizado.')

    def authorize_source(secret: str | None, payload: MetaSource) -> None:
        authenticate(secret)
        if (payload.phone_number_id != config.phone_number_id
                or payload.business_account_id != config.business_account_id):
            raise HTTPException(403, 'Conta/remetente Meta divergentes.')

    def authorize(secret: str | None, payload: MetaSource, phone: str) -> bool:
        authorize_source(secret,payload)
        try:
            normalized = canonical_phone(phone)
            return config.allow_all_phones or normalized in allowed
        except ValueError:
            raise HTTPException(422, 'Telefone invalido.') from None

    def rpc(name: str, params: dict) -> dict:
        try:
            result = client.rpc(name, params).execute().data
        except Exception as exc:
            code = str(getattr(exc, 'code', ''))
            if code not in ('PT409', '22023', '42501'):
                logger.warning('Falha RPC de callback: %s', type(exc).__name__)
            status = {'PT409': 409, '22023': 422, '42501': 403}.get(code, 503)
            raise HTTPException(status, 'Callback nao persistido; consultar o diagnostico do servidor.') from None
        if not isinstance(result, dict) or result.get('accepted') is not True:
            raise HTTPException(503, 'Banco nao confirmou o callback.')
        return result

    def lookup(table: str, columns: str, entity_id: UUID | str) -> dict:
        try:
            rows = client.table(table).select(columns).eq('id', str(entity_id)).limit(1).execute().data
        except Exception as exc:
            logger.warning('Falha de consulta de escopo: %s', type(exc).__name__)
            raise HTTPException(503, 'Nao foi possivel validar o escopo da entidade.') from None
        if not rows:
            raise HTTPException(404, 'Entidade nao encontrada.')
        return rows[0]

    def check_entity_phone(phone: str | None, supplied_phone: str | None = None) -> None:
        try:
            actual = canonical_phone(phone or '')
            valid = (config.allow_all_phones or actual in allowed) and (supplied_phone is None or actual == canonical_phone(supplied_phone))
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
                'recipient_scope': 'production' if config.allow_all_phones else 'restricted',
                'ai_enabled': config.ai_enabled, 'dispatch_enabled': config.dispatch_enabled,
                'human_enabled': config.human_enabled,
                'media_enabled': config.media_enabled,
                'inbound_media_enabled': config.inbound_media_enabled,
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

    if config.inbound_media_enabled:
        @app.post('/webhooks/make/whatsapp/media', status_code=202)
        def inbound_media(payload: InboundMedia, x_webhook_secret: str | None = Header(default=None)):
            if not authorize(x_webhook_secret, payload, payload.phone):
                return {'accepted': True, 'ignored': True, 'reason': 'outside_test_scope'}
            from app.whatsapp_inbound_media import prepare_received_file, store_received_file, remove_unreferenced_file, MediaInvalid, MediaUnavailable
            try:
                def decode(value, limit):
                    decoded = base64.b64decode(value, validate=True).decode('utf8')
                    if len(decoded)>limit: raise ValueError()
                    return decoded
                name = decode(payload.name_base64, 180)
                caption = decode(payload.caption_base64, 9000)
                file_name = decode(payload.file_name_base64, 180)
                prepared = prepare_received_file(message_id=payload.external_message_id,
                    media_type=payload.media_type, mime_type=payload.mime_type, file_name=file_name,
                    content_base64=payload.content_base64.get_secret_value(), expected_sha256=payload.sha256)
            except (ValueError, binascii.Error, UnicodeError):
                raise HTTPException(422, 'Arquivo, checksum ou metadados de midia invalidos.') from None
            try:
                store_received_file(client, prepared)
            except MediaInvalid:
                raise HTTPException(409, 'Arquivo privado divergente; revisar evento.') from None
            except MediaUnavailable:
                raise HTTPException(503, 'Arquivo nao confirmado; repetir o mesmo evento.') from None
            body = 'Arquivo recebido: '+prepared.metadata['file_name']
            if caption.strip(): body += '\n'+caption.strip()
            try:
                result = rpc('vendra_whatsapp_media_receive_v1', {
                    'p_phone': payload.phone, 'p_name': name or None, 'p_body': body,
                    'p_external_message_id': payload.external_message_id,
                    'p_occurred_at': payload.occurred_at.isoformat(),
                    'p_media_id': payload.media_id, 'p_attachment': prepared.metadata})
            except HTTPException as exc:
                if exc.status_code in (403,409,422):
                    remove_unreferenced_file(client, prepared)
                raise
            if result.get('media_stored') is not True or not result.get('attachment_id'):
                raise HTTPException(503, 'Banco nao confirmou o vinculo da midia; repetir o mesmo evento.')
            # A configuração do atendimento é preservada. Só este evento binário não vai à IA.
            result['automation'] = {'route_to_ai': False, 'should_respond': False,
                'make_instruction': 'STOP_AT_VENDRA', 'reason': 'media_requires_human_review'}
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

    if config.human_enabled:
        @app.post('/webhooks/make/whatsapp/outbox/{outbox_id}/uncertain',status_code=202)
        def uncertain_send(outbox_id:UUID,payload:UncertainSend,x_webhook_secret:str|None=Header(default=None)):
            if not authorize(x_webhook_secret,payload,payload.recipient_id):
                raise HTTPException(403,'Destinatario fora do escopo autorizado.')
            item=lookup('whatsapp_outbox','phone',outbox_id)
            check_entity_phone(item['phone'],payload.recipient_id)
            return rpc('vendra_whatsapp_uncertain_v1',{'p_outbox_id':str(outbox_id),
                       'p_claim_token':payload.claim_token.get_secret_value()})

        @app.post('/webhooks/make/whatsapp/outbox/{outbox_id}/prepare-human', status_code=202)
        def human_prepare(outbox_id: UUID, payload: HumanPrepare,
                          x_webhook_secret: str | None = Header(default=None)):
            authorize_source(x_webhook_secret,payload)
            item = lookup('whatsapp_outbox', 'phone,ticket_id', outbox_id)
            actual_phone=payload.phone or item.get('phone')
            if not authorize(x_webhook_secret,payload,actual_phone):
                raise HTTPException(403,'Destinatario fora do escopo autorizado.')
            if payload.expected_ticket_id and str(payload.expected_ticket_id) != str(item.get('ticket_id')):
                raise HTTPException(403, 'Saida fora do atendimento autorizado.')
            check_entity_phone(item.get('phone'), payload.phone)
            ticket_scope(UUID(item['ticket_id']), actual_phone)
            name = 'vendra_whatsapp_human_or_media_prepare_v1' if config.media_enabled else 'vendra_whatsapp_human_prepare_v1'
            result = rpc(name, {'p_outbox_id': str(outbox_id)})
            if type(result.get('authorized')) is not bool:
                raise HTTPException(503, 'Banco nao confirmou a autorizacao humana.')
            if result.get('authorized') is True:
                outbox = result.get('outbox')
                policy = outbox.get('delivery_policy') if isinstance(outbox, dict) else None
                if (not isinstance(outbox, dict) or outbox.get('id') != str(outbox_id)
                        or not isinstance(outbox.get('body'), str) or not outbox['body'].strip()
                        or not isinstance(outbox.get('claim_token'), str) or not 32 <= len(outbox['claim_token']) <= 100
                        or not isinstance(policy, dict) or policy.get('authorized_to_send') is not True
                        or policy.get('template_required') is not False):
                    raise HTTPException(503, 'Banco nao confirmou a reserva humana.')
                check_entity_phone(outbox.get('phone'), payload.phone)
                kind = outbox.setdefault('message_type', 'text')
                if kind != 'text':
                    from app.services.whatsapp_media_service import media_type
                    media = outbox.get('media') or {}
                    attachment = lookup('attachments','message_id,file_name,mime_type,storage_path',media.get('id',''))
                    if (not config.media_enabled or attachment['message_id'] != result.get('message_id')
                            or media_type(attachment['mime_type']) != kind):
                        raise HTTPException(503,'Vinculo ou formato de midia divergente.')
                    try:
                        signed = client.storage.from_('ticket-attachments').create_signed_url(attachment['storage_path'],600)
                        url = signed.get('signedURL') or signed.get('signedUrl')
                        parsed = urlsplit(url or '')
                        if parsed.scheme!='https' or parsed.netloc!=config.project_ref+'.supabase.co':
                            raise ValueError('URL de armazenamento divergente')
                    except Exception:
                        raise HTTPException(503,'Nao foi possivel preparar acesso temporario ao arquivo.') from None
                    media['url']=url
            elif 'outbox' in result:
                raise HTTPException(503, 'Reserva humana suprimida com dados de envio divergentes.')
            return result

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
