"""Teste opt-in no Supabase-STAGING: 8 insercoes concorrentes, apenas nas tabelas staging_transport_*.

Executar SOMENTE apos migration 01 e backup. Nao ha integracao com outbox, Meta, Make ou worker.
"""
from __future__ import annotations
import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from tools.staging_runtime import load


def main() -> int:
    load()  # Falha se APP_ENV/Supabase URL/segredos nao pertencerem ao STAGING.
    from app.db.supabase import get_admin_client
    from app.services.staging_delivery_preflight_service import readiness
    from app.services.staging_dispatch_preview_service import list_dispatch_candidates
    from app.services.staging_transport_contract_service import change_contract
    if not readiness()['real_queue_clean']:
        raise RuntimeError('Filas reais nao estao vazias. Teste cancelado.')
    db=get_admin_client()
    candidates=list_dispatch_candidates()
    if not candidates:
        raise RuntimeError('Nenhuma oportunidade de teste aberta encontrada.')
    profiles=(db.table('profiles').select('id,access_level')
              .eq('status','active').limit(100).execute().data or [])
    actors=[row for row in profiles if row.get('access_level') in
            ('comercial','gerencial','administrativo')]
    if not actors:
        raise RuntimeError('Nenhum perfil comercial ativo disponivel.')
    opportunity_id=str(candidates[0]['id']);actor_id=str(actors[0]['id'])
    print('STAGING confirmado. Teste usa uma oportunidade aberta e um perfil comercial ativo.')
    print('Sera criada UMA requisicao de contrato isolado e varios eventos de teste; nenhuma mensagem.')
    if input('Para autorizar apenas este teste, digite TESTAR-H1-005B8: ').strip()!='TESTAR-H1-005B8':
        print('Cancelado, sem criacao de registros.');return 2
    unique=uuid.uuid4().hex
    fingerprint=hashlib.sha256(('H1-005B8-CONCURRENCY-'+unique).encode()).hexdigest()
    payload={'p_opportunity_id':opportunity_id,'p_fingerprint':fingerprint,'p_actor_id':actor_id}
    def request(_):
        return db.rpc('vendra_staging_h1_005b8_prepare',payload).execute().data
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(request,range(8)))
    ids={str(result['id']) for result in results}
    created=sum(bool(x['created']) for x in results)
    if len(ids)!=1 or created!=1:
        raise RuntimeError('Concorrencia nao passou; ids ou indicador de criacao divergentes.')
    contract_id=next(iter(ids))
    print('Idempotencia REAL PostgreSQL: 8 chamadas / 1 contrato / 1 criacao — OK')
    # RBAC negativo: perfil inexistente deve ser barrado antes do INSERT.
    try:
        db.rpc('vendra_staging_h1_005b8_prepare',{**payload,'p_actor_id':str(uuid.uuid4())}).execute()
    except Exception:
        print('RPC com perfil inexistente foi bloqueada — OK')
    else:
        raise RuntimeError('RPC aceitou identidade inexistente; nao homologar.')
    events=(db.table('staging_transport_events').select('id')
             .eq('contract_id',contract_id).execute().data or [])
    if len(events)!=1:
        raise RuntimeError('Esperado 1 evento de preparo no banco.')
    version=1
    for i in range(3):
        lease=change_contract(contract_id=contract_id,action='lease',lock_version=version,actor_id=actor_id)
        version=int(lease['lock_version'])
        failed=change_contract(contract_id=contract_id,action='fail',lock_version=version,actor_id=actor_id)
        version=int(failed['lock_version'])
        if i<2:
            if failed['state']!='failed':raise RuntimeError('Falha simulada nao registrada.')
            retried=change_contract(contract_id=contract_id,action='retry',lock_version=version,actor_id=actor_id)
            version=int(retried['lock_version'])
        elif failed['state']!='dead_letter':
            raise RuntimeError('Limite de tentativas nao gerou dead_letter.')
    try:
        change_contract(contract_id=contract_id,action='retry',lock_version=1,actor_id=actor_id)
    except Exception:
        print('Lock/versionamento e estado terminal: escrita antiga rejeitada — OK')
    else:
        raise RuntimeError('Uma versao antiga nao foi rejeitada.')
    if not readiness()['real_queue_clean']:
        raise RuntimeError('ALERTA: contagem de fila real mudou. Investigar imediatamente.')
    print('Dead-letter na terceira tentativa simulada — OK')
    print('Filas reais vazias: dispatches=0 / whatsapp_outbox=0 / messages=0 — OK')
    print('H1-005B8: teste real de banco de dados passou; nenhuma mensagem enviada.')
    return 0

if __name__=='__main__':raise SystemExit(main())
