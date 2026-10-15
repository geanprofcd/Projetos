"""Contrato HTTP real no STAGING com fixtures descartaveis; nunca envia WhatsApp.

Requer perfil privado e ponte ativa com IA/envio desligados. Sem --executar,
somente confere pre-condicoes. A instancia HTTP de teste nao publica porta.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
from urllib.request import urlopen
from uuid import uuid4

from app.whatsapp_callbacks import create_app, load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--resposta-agente', type=Path, required=True)
    parser.add_argument('--relatorio', type=Path, required=True)
    parser.add_argument('--executar', action='store_true')
    args = parser.parse_args()
    config = load_config(args.config)
    if (config.environment != 'staging' or config.project_ref != 'ljufhqnadzltqbtdaulv'
            or config.ai_enabled):
        raise RuntimeError('Exige perfil STAGING esperado com IA desligada.')
    body = args.resposta_agente.read_text(encoding='utf-8-sig').strip()
    if not body or len(body) > 10000:
        raise RuntimeError('Resposta de teste fora do limite.')

    def health():
        with urlopen('http://127.0.0.1:8012/health', timeout=10) as response:
            data = json.load(response)
        if (data.get('environment') != 'staging' or data.get('ai_enabled') is not False
                or data.get('external_sends_enabled') is not False):
            raise RuntimeError('Ponte ativa precisa permanecer com IA/envio desligados.')

    health()
    from supabase import create_client
    db = create_client(config.supabase_url, config.backend_key)
    if db.table('integration_settings').select('key').eq('key', 'whatsapp_bridge').execute().data:
        raise RuntimeError('Configuracao global existente: preservar e conciliar antes do teste.')
    phone = '551100000000'
    if db.table('customers').select('id').in_('phone_normalized', [phone, '5511900000000']).execute().data:
        raise RuntimeError('Telefone sintetico ja pertence a registro existente.')
    if not args.executar:
        print('Pre-condicoes conferidas. Use --executar para fixtures e configuracao temporaria STAGING.')
        return

    from fastapi.testclient import TestClient
    run = 'CODEX-HTTP-' + uuid4().hex
    report = {'run': run, 'checks': [], 'cleanup': False, 'external_sends': False,
              'public_runtime_changed': False, 'passed': False}
    customer = ticket = inbound = None
    setting_created = False
    setting = {'ai_enabled': True, 'codex_test_run': run}

    def save():
        args.relatorio.parent.mkdir(parents=True, exist_ok=True)
        args.relatorio.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def check(name, ok):
        report['checks'].append({'name': name, 'ok': bool(ok)})
        save()
        print(name + ': ' + ('OK' if ok else 'FALHOU'), flush=True)
        if not ok:
            raise RuntimeError(name)

    def rpc(name, values):
        return db.rpc(name, values).execute().data

    actor = db.table('profiles').select('id').eq('access_level', 'administrativo').eq('status', 'active').limit(1).execute().data[0]['id']
    meta = {'phone_number_id': config.phone_number_id, 'business_account_id': config.business_account_id,
            'occurred_at': datetime.now(timezone.utc).isoformat()}
    headers = {'X-Webhook-Secret': config.webhook_secret}
    # Contrato IA habilitado somente nessa instancia local nao publicada.
    test_config = replace(config, allowed_phones=(phone,), ai_enabled=True)
    try:
        with TestClient(create_app(test_config, client=db)) as client:
            entry = dict(meta, phone=phone, name=run, message=run + ' entrada', external_message_id=run + '-in')
            response = client.post('/webhooks/make/whatsapp', json=entry, headers=headers)
            first = response.json()
            if response.status_code != 202 or not first.get('accepted'):
                raise RuntimeError('Entrada nao persistida.')
            customer, ticket, inbound = first['customer_id'], first['ticket_id'], first['message_id']
            check('entrada HTTP real inicia sem IA', not first['duplicate'] and not first['automation']['route_to_ai'])
            rpc('vendra_whatsapp_mode_v1', {'p_ticket_id': ticket, 'p_mode': 'ai', 'p_expected_version': 1, 'p_actor_id': actor})
            # Nunca upsert: preservar qualquer configuracao concorrente.
            db.table('integration_settings').insert({'key': 'whatsapp_bridge', 'settings': setting}).execute()
            setting_created = True
            health()
            control = client.get('/webhooks/make/ai/control/' + ticket, headers=headers)
            check('controle HTTP exige modo versao e janela atuais', control.status_code == 200 and control.json()['route_to_ai'] and control.json()['control_version'] == 2)
            reply = dict(meta, phone=phone, ticket_id=ticket, inbound_message_id=inbound,
                         message_base64=base64.b64encode(body.encode()).decode(), external_message_id=run + '-reply',
                         control_version=2, route_code='2', delivery_mode='inline_make')
            response = client.post('/webhooks/make/ai/reply', json=reply, headers=headers)
            prepared = response.json()
            check('resposta real do agente preparada via HTTP', response.status_code == 202 and prepared.get('authorized') is True)
            oid, mid = prepared['outbox_id'], prepared['message_id']
            token = prepared['outbox']['claim_token']
            expected = re.sub(r'\s*#[123]\s*$', '', body).strip()
            check('marcador tecnico removido e texto preservado', prepared['outbox']['body'] == expected and not re.search(r'#[123]\s*$', prepared['outbox']['body']))
            persisted = db.table('messages').select('body,sender_kind,delivery_status').eq('id', mid).single().execute().data
            check('autoria IA persistida com reserva sem envio', persisted['body'] == expected and persisted['sender_kind'] == 'ai' and persisted['delivery_status'] == 'claimed')
            duplicate = client.post('/webhooks/make/ai/reply', json=reply, headers=headers)
            check('duplicata HTTP nao reautoriza nem devolve token', duplicate.status_code == 202 and duplicate.json().get('duplicate') and duplicate.json()['authorized'] is False and 'outbox' not in duplicate.json())
            different = dict(reply, message_base64=base64.b64encode((body + '\nConflito').encode()).decode())
            check('resposta divergente HTTP recusada', client.post('/webhooks/make/ai/reply', json=different, headers=headers).status_code == 409)
            inbound_duplicate = client.post('/webhooks/make/whatsapp', json=entry, headers=headers)
            check('entrada duplicada nao reaciona agente com gates ligados', inbound_duplicate.status_code == 202 and inbound_duplicate.json()['duplicate'] and not inbound_duplicate.json()['automation']['route_to_ai'])
            wamid = 'wamid.' + run
            stamp = datetime.now(timezone.utc)
            for status, delay in [('delivered', 20), ('read', 10)]:
                payload = dict(meta, occurred_at=(stamp - timedelta(seconds=delay)).isoformat(),
                               provider_message_id=wamid, status=status, recipient_id=phone)
                response = client.post('/webhooks/make/whatsapp/provider-status', json=payload, headers=headers)
                check(status + ' HTTP pendente antes do vinculo', response.status_code == 202 and response.json().get('pending_match'))
            binding = dict(meta, provider_message_id=wamid, recipient_id=phone, claim_token=token, status='sent')
            url = '/webhooks/make/whatsapp/outbox/' + oid + '/status'
            denied = client.post(url, json=dict(binding, claim_token='x' * 36), headers=headers)
            check('token incorreto HTTP recusado', denied.status_code == 403)
            response = client.post(url, json=binding, headers=headers)
            check('vinculo HTTP reconcilia dois status ate read', response.status_code == 202 and response.json()['status'] == 'read' and response.json()['reconciled'] == 2)
            response = client.post(url, json=binding, headers=headers)
            check('vinculo HTTP repetido nao regride nem reprocessa', response.status_code == 202 and response.json()['status'] == 'read' and response.json()['reconciled'] == 0)
            persisted = db.table('messages').select('delivery_status,external_status_updated_at').eq('id', mid).single().execute().data
            check('mensagem mantem read e timestamp de status', persisted['delivery_status'] == 'read' and datetime.fromisoformat(persisted['external_status_updated_at']) == stamp - timedelta(seconds=10))
            rpc('vendra_whatsapp_mode_v1', {'p_ticket_id': ticket, 'p_mode': 'human', 'p_expected_version': 2, 'p_actor_id': actor})
            response = client.post('/webhooks/make/ai/reply', json=reply, headers=headers)
            check('handoff bloqueia resposta HTTP com versao antiga', response.status_code == 202 and response.json()['reason'] == 'stale_control_version')
            response = client.get('/webhooks/make/ai/control/' + ticket, headers=headers)
            check('controle HTTP confirma humano e versao nova', response.status_code == 200 and response.json()['mode'] == 'human' and response.json()['control_version'] == 3 and not response.json()['route_to_ai'])
            check('somente uma outbox foi criada', len(db.table('whatsapp_outbox').select('id').eq('ticket_id', ticket).execute().data) == 1)
            health()
            report['passed'] = True
    finally:
        if setting_created:
            rows = db.table('integration_settings').select('settings').eq('key', 'whatsapp_bridge').execute().data
            if not rows or rows[0]['settings'] != setting:
                raise RuntimeError('Configuracao concorrente divergente; preservar e conciliar.')
            db.table('integration_settings').delete().eq('key', 'whatsapp_bridge').eq('settings', json.dumps(setting)).execute()
        if ticket:
            own = db.table('tickets').select('customer_id').eq('id', ticket).single().execute().data
            if own['customer_id'] != customer:
                raise RuntimeError('Fixture divergente; preservar e conciliar.')
            events = db.table('integration_events').select('id').eq('provider', 'ai').eq('external_id', 'ai-reply:' + inbound).execute().data
            events += db.table('integration_events').select('id').or_('external_id.like.' + run + '%,external_id.like.provider-status:wamid.' + run + '%').execute().data
            for event in events:
                db.table('integration_events').delete().eq('id', event['id']).execute()
            db.table('audit_log').delete().eq('entity_id', ticket).eq('action', 'whatsapp_ai_mode').execute()
            db.table('whatsapp_outbox').delete().eq('ticket_id', ticket).execute()
            db.table('messages').delete().eq('ticket_id', ticket).execute()
            db.table('tickets').delete().eq('id', ticket).eq('customer_id', customer).execute()
            own = db.table('customers').select('name').eq('id', customer).single().execute().data
            if own['name'] != run:
                raise RuntimeError('Cliente fixture divergente; preservar.')
            db.table('customers').delete().eq('id', customer).eq('name', run).execute()
        report['cleanup'] = (not db.table('integration_settings').select('key').eq('key', 'whatsapp_bridge').execute().data
                             and not db.table('customers').select('id').eq('name', run).execute().data)
        save()
        check('configuracao restaurada e fixtures removidas', report['cleanup'])
        health()


if __name__ == '__main__':
    main()
