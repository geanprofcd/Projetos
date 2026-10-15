"""Meta Cloud API: templates de texto. Não imita aprovação e não usa Make fixo.

A origem de verdade do status do modelo é a WABA. Tokens permanecem no ambiente.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from app.core.config import get_settings
from app.services.admin_settings_service import get_whatsapp_settings
from app.services.customer_service import get_customer, normalize_phone
from app.services.demo_store import DEMO_MESSAGES, DEMO_TICKETS, DEMO_WHATSAPP_OUTBOX, new_id
from app.services.ticket_service import add_message, get_ticket
from app.db.supabase import get_admin_client
from app.services.automation_service import set_ticket_ai_mode

NAME_RE = re.compile(r'^[a-z][a-z0-9_]{2,127}$')
VARIABLE_RE = re.compile(r'\{\{(\d+)\}\}')

class TemplateError(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def configured() -> bool:
    s = get_settings()
    w = get_whatsapp_settings()
    return all((s.meta_access_token, s.meta_waba_id or w.get('business_account_id'),
                s.meta_phone_number_id or w.get('phone_number_id')))


def _graph_id(value: str) -> str:
    if not re.fullmatch(r'\d{5,30}', str(value or '')):
        raise TemplateError('Identificador da conta Meta não configurado corretamente.')
    return str(value)


def _graph(method: str, endpoint: str, payload: dict | None = None, *, params: dict | None = None) -> dict:
    settings = get_settings()
    if settings.app_env == "staging":
        raise TemplateError("Ambiente de homologação: requisições à Meta bloqueadas.")
    if not settings.meta_access_token:
        raise TemplateError('META_ACCESS_TOKEN não configurado. Cadastre um token de sistema com permissões apropriadas.')
    version = settings.meta_graph_version
    if not re.fullmatch(r'v\d{1,2}\.\d{1,2}', version):
        raise TemplateError('META_GRAPH_VERSION inválida.')
    url = f'https://graph.facebook.com/{version}/{endpoint}'
    if params: url += '?' + urllib.parse.urlencode(params)
    headers = {'Authorization': f'Bearer {settings.meta_access_token}', 'Accept':'application/json'}
    if payload is not None: headers['Content-Type'] = 'application/json'
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read(300000).decode())
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read(6000)).get('error', {})
            detail = str(err.get('message') or 'Solicitação recusada pela Meta.')[:250]
        except (ValueError, UnicodeError):
            detail = 'Solicitação recusada pela Meta.'
        raise TemplateError(f'Meta: {detail}') from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise TemplateError('Meta indisponível. Nenhuma confirmação de envio foi recebida; verifique antes de tentar novamente.') from exc


def _waba() -> str:
    s=get_settings()
    return _graph_id(s.meta_waba_id or get_whatsapp_settings().get('business_account_id'))


def _phone_id() -> str:
    s=get_settings()
    return _graph_id(s.meta_phone_number_id or get_whatsapp_settings().get('phone_number_id'))


def text_body(item: dict) -> str:
    return next((str(c.get('text') or '') for c in (item.get('components') or []) if str(c.get('type')).upper()=='BODY'), '')


def variable_count(body: str) -> int:
    ids = {int(x) for x in VARIABLE_RE.findall(body)}
    if not ids: return 0
    if ids != set(range(1, max(ids)+1)) or max(ids)>5:
        raise TemplateError('Use variáveis sequenciais {{1}} até {{5}}, sem pular números.')
    return max(ids)


def preview(body: str, values: list[str]) -> str:
    for idx, value in enumerate(values,1):
        body = body.replace('{{'+str(idx)+'}}', value)
    return body


def list_templates() -> list[dict]:
    if not configured(): return []
    data = _graph('GET', f'{_waba()}/message_templates', params={'fields':'id,name,status,category,language,components,rejected_reason','limit':'100'})
    rows = []
    for item in data.get('data', []):
        body = text_body(item)
        # O primeiro incremento só envia modelos de texto sem cabeçalho/botões.
        if any(str(c.get('type') or '').upper() not in {'BODY','FOOTER'} for c in item.get('components') or []):
            continue
        if not body: continue
        try: count = variable_count(body)
        except TemplateError: continue
        rows.append({'id':str(item.get('id') or ''),'name':str(item.get('name') or ''),
                    'status':str(item.get('status') or '').upper(), 'category':str(item.get('category') or ''),
                    'language':str(item.get('language') or ''),'body':body,'variables':count})
    return sorted(rows,key=lambda x:(x['status']!='APPROVED',x['name']))


def submit_template(*, name: str, category: str, body: str, examples: list[str], language: str = 'pt_BR') -> dict:
    name=name.strip().lower()
    body=body.strip()
    if not NAME_RE.fullmatch(name): raise TemplateError('Identificador: de 3 a 128 caracteres, letras minúsculas, números e _.')
    if category not in {'MARKETING','UTILITY'}:raise TemplateError('Selecione Marketing ou Utilidade.')
    if language not in {'pt_BR','en_US','es_ES'}:raise TemplateError('Idioma inválido.')
    if not (10 <= len(body) <= 1024):raise TemplateError('O conteúdo deve ter entre 10 e 1024 caracteres.')
    count=variable_count(body)
    if len(examples)!=count or any(not v.strip() or len(v)>100 for v in examples):
        raise TemplateError(f'Informe {count} exemplo(s) para validar as variáveis do modelo.')
    if not configured():raise TemplateError('Conecte uma WABA e configure o token Meta antes de enviar para aprovação.')
    component={'type':'BODY','text':body}
    if count: component['example']={'body_text':[examples]}
    result=_graph('POST',f'{_waba()}/message_templates',{'name':name,'language':language,'category':category,'components':[component]})
    return {'id':str(result.get('id') or ''),'name':name,'status':str(result.get('status') or 'PENDING').upper()}


def _sync_message(ticket_id: str, user: dict, body: str, wamid: str) -> None:
    """Integra a saída direta ao histórico/outbox, para que Statuses Meta encontre o WAMID.

    A produção deve adicionar fila transacional para retry em futura etapa; o envio
    não é repetido automaticamente na falha de persistência posterior à Meta.
    """
    msg=add_message(ticket_id,user,body)
    now=_now()
    ticket=get_ticket(ticket_id,user)
    customer=get_customer(str(ticket['customer_id']))
    phone=normalize_phone(customer.get('phone') if customer else None)
    fields={'channel':'whatsapp','external_message_id':wamid,'delivery_status':'sent','external_status_updated_at':now}
    if get_settings().demo_mode:
        target=next(x for x in DEMO_MESSAGES[ticket_id] if str(x['id'])==str(msg['id']))
        target.update(fields)
        DEMO_WHATSAPP_OUTBOX.append({'id':new_id('outbox'),'message_id':msg['id'],'ticket_id':ticket_id,
            'customer_id':ticket['customer_id'],'phone':phone,'body':body,'status':'sent',
            'provider_message_id':wamid,'attempt_count':1,'last_error':None,'created_at':now,'updated_at':now})
    else:
        admin=get_admin_client()
        admin.table('messages').update(fields).eq('id',msg['id']).execute()
        admin.table('whatsapp_outbox').insert({'message_id':msg['id'],'ticket_id':ticket_id,
             'customer_id':ticket['customer_id'],'phone':phone,'body':body,'status':'sent','provider_message_id':wamid}).execute()
        admin.table('tickets').update({'whatsapp_active_at':now}).eq('id',ticket_id).execute()


def send_template(*, ticket_id: str, user: dict, template_name: str, language: str, values: list[str]) -> dict:
    if not configured(): raise TemplateError('Integração Meta não configurada; nenhum WhatsApp foi enviado.')
    ticket=get_ticket(ticket_id,user)
    if not ticket or ticket.get('source')!='whatsapp':raise TemplateError('Atendimento WhatsApp não encontrado.')
    matching=[t for t in list_templates() if t['name']==template_name and t['language']==language]
    if not matching:raise TemplateError('Modelo não localizado na conta Meta. Atualize a lista.')
    item=matching[0]
    if item['status']!='APPROVED':raise TemplateError('O modelo ainda não está aprovado pela Meta.')
    if item['variables']!=len(values) or any(not str(v).strip() or len(str(v))>200 for v in values):
        raise TemplateError('Preencha todas as variáveis do modelo.')
    customer=get_customer(str(ticket.get('customer_id')))
    phone=normalize_phone(customer.get('phone') if customer else None)
    if not phone:raise TemplateError('Cliente sem número WhatsApp válido.')
    templ={'name':template_name,'language':{'code':language}}
    if values:templ['components']=[{'type':'body','parameters':[{'type':'text','text':v} for v in values]}]
    payload={'messaging_product':'whatsapp','to':phone,'type':'template','template':templ}
    result=_graph('POST', f'{_phone_id()}/messages', payload)
    wamid=str((result.get('messages') or [{}])[0].get('id') or '')
    if not wamid.startswith('wamid.'):
        raise TemplateError('A Meta não retornou identificador válido; consulte os logs antes de reenviar.')
    text=preview(item['body'],values)
    # Nunca reenviar automaticamente se a persistência falhar após o aceite da Meta.
    try:
        _sync_message(ticket_id,user,text,wamid)
        set_ticket_ai_mode(ticket_id,mode='human',actor_id=str(user.get('id') or ''),source='human_template')
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception('Envio Meta confirmado %s; falha de persistência local',wamid)
        raise TemplateError(f'Meta aceitou o envio ({wamid}), mas o registro local falhou. NÃO reenvie antes de conciliar.') from exc
    return {'wamid':wamid,'template':template_name}
