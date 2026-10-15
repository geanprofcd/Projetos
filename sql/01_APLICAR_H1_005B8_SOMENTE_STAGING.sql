-- VENDRA H1-005B8 | MIGRATION EXCLUSIVA DE HOMOLOGACAO.
-- EXECUTAR MANUALMENTE APENAS NO PROJETO VENDRA-STAGING.
-- NENHUMA ALTERACAO em dispatches, whatsapp_outbox, messages; nenhum envio externo.
-- Primeiro confirmar que o projeto selecionado se chama exatamente VENDRA-STAGING.
BEGIN;
DO $check$
BEGIN
 IF to_regclass('public.staging_dispatch_simulations') IS NULL
    OR to_regclass('public.opportunities') IS NULL
    OR to_regclass('public.profiles') IS NULL THEN
   RAISE EXCEPTION 'H1-005B8 exige STAGING H1-005B6 instalado.';
 END IF;
 IF to_regclass('public.staging_transport_contracts') IS NOT NULL
    OR to_regclass('public.staging_transport_events') IS NOT NULL THEN
   RAISE EXCEPTION 'H1-005B8 ja instalada. Nao reaplicar; verificar o estado.';
 END IF;
 IF (SELECT count(*) FROM public.dispatches)>0 OR
    (SELECT count(*) FROM public.whatsapp_outbox)>0 OR
    (SELECT count(*) FROM public.messages)>0 THEN
   RAISE EXCEPTION 'Filas reais nao vazias no STAGING. Migration interrompida.';
 END IF;
END;
$check$;

CREATE TABLE public.staging_transport_contracts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 opportunity_id uuid NOT NULL REFERENCES public.opportunities(id),
 fingerprint text NOT NULL CHECK(fingerprint ~ '^[a-f0-9]{64}$'),
 state text NOT NULL DEFAULT 'blocked'
   CHECK(state IN ('blocked','leased','validated','failed','dead_letter','cancelled')),
 attempt_count integer NOT NULL DEFAULT 0 CHECK(attempt_count BETWEEN 0 AND 3),
 lock_version integer NOT NULL DEFAULT 1 CHECK(lock_version >= 1),
 lease_until timestamptz,
 last_failure_code text CHECK(last_failure_code IN ('SIMULATED_FAILURE','LEASE_EXPIRED')),
 transport_enabled boolean NOT NULL DEFAULT false CHECK(transport_enabled=false),
 created_by uuid REFERENCES public.profiles(id),
 updated_by uuid REFERENCES public.profiles(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT vendra_h1_005b8_unique UNIQUE(opportunity_id,fingerprint),
 CONSTRAINT vendra_h1_005b8_lease_consistency CHECK ((state='leased')=(lease_until IS NOT NULL)),
 CONSTRAINT vendra_h1_005b8_error_consistency CHECK (
   (state IN ('failed','dead_letter'))=(last_failure_code IS NOT NULL)),
 CONSTRAINT vendra_h1_005b8_terminal_consistency CHECK (
   state<>'dead_letter' OR attempt_count=3)
);
CREATE INDEX staging_transport_contracts_created_idx
 ON public.staging_transport_contracts(created_at DESC);
ALTER TABLE public.staging_transport_contracts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.staging_transport_contracts FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON public.staging_transport_contracts TO service_role;

CREATE TABLE public.staging_transport_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 contract_id uuid NOT NULL REFERENCES public.staging_transport_contracts(id),
 actor_id uuid REFERENCES public.profiles(id),
 action text NOT NULL CHECK(action IN ('prepare','lease','validate_no_send','fail','expire','retry','cancel')),
 old_state text,
 new_state text NOT NULL,
 version integer NOT NULL CHECK(version >= 1),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX staging_transport_events_contract_idx
 ON public.staging_transport_events(contract_id,created_at DESC);
ALTER TABLE public.staging_transport_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.staging_transport_events FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT ON public.staging_transport_events TO service_role;

-- INSERT CONFLICT protegido por constraint unica; apenas metadados sem PII.
CREATE FUNCTION public.vendra_staging_h1_005b8_prepare(
 p_opportunity_id uuid,p_fingerprint text,p_actor_id uuid
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
DECLARE v_id uuid; v_created boolean := false; v_state text;v_version integer;
BEGIN
 IF NOT EXISTS (SELECT 1 FROM public.profiles p WHERE p.id=p_actor_id
   AND p.status='active' AND p.access_level IN ('comercial','gerencial','administrativo')) THEN
   RAISE EXCEPTION 'Acesso comercial nao permitido' USING ERRCODE='42501';
 END IF;
 IF p_fingerprint IS NULL OR p_fingerprint !~ '^[a-f0-9]{64}$' THEN
   RAISE EXCEPTION 'Fingerprint invalido' USING ERRCODE='22023';
 END IF;
 IF (SELECT count(*) FROM public.dispatches)>0 OR
    (SELECT count(*) FROM public.whatsapp_outbox)>0 OR
    (SELECT count(*) FROM public.messages)>0 THEN
   RAISE EXCEPTION 'Filas reais nao vazias: bloquear homologacao' USING ERRCODE='22023';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM public.opportunities o
   JOIN public.customers c ON c.id=o.customer_id
   WHERE o.id=p_opportunity_id AND o.status='open' AND o.archived_at IS NULL
      AND c.status='active') THEN
   RAISE EXCEPTION 'Oportunidade nao elegivel' USING ERRCODE='22023';
 END IF;
 INSERT INTO public.staging_transport_contracts
   (opportunity_id,fingerprint,created_by,updated_by)
 VALUES (p_opportunity_id,p_fingerprint,p_actor_id,p_actor_id)
 ON CONFLICT(opportunity_id,fingerprint) DO NOTHING RETURNING id INTO v_id;
 v_created:=(v_id IS NOT NULL);
 IF NOT v_created THEN
   SELECT id INTO v_id FROM public.staging_transport_contracts
   WHERE opportunity_id=p_opportunity_id AND fingerprint=p_fingerprint;
 END IF;
 IF v_id IS NULL THEN RAISE EXCEPTION 'Contrato nao localizado'; END IF;
 IF v_created THEN
   INSERT INTO public.staging_transport_events(contract_id,actor_id,action,old_state,new_state,version)
    VALUES (v_id,p_actor_id,'prepare',NULL,'blocked',1);
 END IF;
 SELECT state,lock_version INTO v_state,v_version FROM public.staging_transport_contracts WHERE id=v_id;
 RETURN jsonb_build_object('id',v_id,'created',v_created,'state',v_state,
  'lock_version',v_version,'external_send',false);
END;
$fn$;

-- Maquina de estados somente SIMULADA. Mesmo 'lease' NUNCA entrega a um worker.
CREATE FUNCTION public.vendra_staging_h1_005b8_transition(
 p_contract_id uuid,p_action text,p_expected_version integer,p_actor_id uuid
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
DECLARE v public.staging_transport_contracts%ROWTYPE;
 v_next text;v_error text:=NULL;v_lease timestamptz:=NULL;v_attempt integer;
 v_next_version integer;
BEGIN
 IF NOT EXISTS (SELECT 1 FROM public.profiles p WHERE p.id=p_actor_id
   AND p.status='active' AND p.access_level IN ('comercial','gerencial','administrativo')) THEN
   RAISE EXCEPTION 'Acesso comercial nao permitido' USING ERRCODE='42501';
 END IF;
 IF (SELECT count(*) FROM public.dispatches)>0 OR
    (SELECT count(*) FROM public.whatsapp_outbox)>0 OR
    (SELECT count(*) FROM public.messages)>0 THEN
   RAISE EXCEPTION 'Filas reais nao vazias: bloquear homologacao' USING ERRCODE='22023';
 END IF;
 SELECT * INTO v FROM public.staging_transport_contracts WHERE id=p_contract_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Contrato nao encontrado' USING ERRCODE='22023'; END IF;
 IF p_expected_version IS NULL OR v.lock_version <> p_expected_version THEN
   RAISE EXCEPTION 'Versao divergente; atualize a pagina' USING ERRCODE='40001';
 END IF;
 v_attempt:=v.attempt_count;
 IF p_action='lease' AND v.state='blocked' AND v_attempt<3 THEN
   v_next:='leased';v_attempt:=v_attempt+1;v_lease:=now()+interval '2 minutes';
 ELSIF p_action='validate_no_send' AND v.state='leased' AND v.lease_until>now() THEN
   v_next:='validated';
 ELSIF p_action='fail' AND v.state='leased' AND v.lease_until>now() THEN
   v_next:=CASE WHEN v_attempt>=3 THEN 'dead_letter' ELSE 'failed' END;
   v_error:='SIMULATED_FAILURE';
 ELSIF p_action='expire' AND v.state='leased' AND v.lease_until<=now() THEN
   v_next:=CASE WHEN v_attempt>=3 THEN 'dead_letter' ELSE 'failed' END;
   v_error:='LEASE_EXPIRED';
 ELSIF p_action='retry' AND v.state='failed' AND v_attempt<3 THEN
   v_next:='blocked';
 ELSIF p_action='cancel' AND v.state IN ('blocked','failed') THEN
   v_next:='cancelled';
 ELSE
   RAISE EXCEPTION 'Transicao proibida ou lease ainda valido' USING ERRCODE='22023';
 END IF;
 UPDATE public.staging_transport_contracts
    SET state=v_next,attempt_count=v_attempt,lease_until=v_lease,
        last_failure_code=v_error,lock_version=lock_version+1,
        updated_by=p_actor_id,updated_at=now()
  WHERE id=p_contract_id RETURNING lock_version INTO v_next_version;
 INSERT INTO public.staging_transport_events
   (contract_id,actor_id,action,old_state,new_state,version)
 VALUES (p_contract_id,p_actor_id,p_action,v.state,v_next,v_next_version);
 RETURN jsonb_build_object('id',p_contract_id,'state',v_next,
  'lock_version',v_next_version,'attempt_count',v_attempt,'external_send',false);
END;
$fn$;

REVOKE ALL ON FUNCTION public.vendra_staging_h1_005b8_prepare(uuid,text,uuid)
 FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.vendra_staging_h1_005b8_transition(uuid,text,integer,uuid)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_staging_h1_005b8_prepare(uuid,text,uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.vendra_staging_h1_005b8_transition(uuid,text,integer,uuid) TO service_role;
COMMIT;
