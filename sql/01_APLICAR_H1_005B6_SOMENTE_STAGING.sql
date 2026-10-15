-- VENDRA H1-005B6. EXECUTE APENAS NO PROJETO VENDRA-STAGING.
-- Nao usar em producao. NENHUMA integracao WhatsApp/Meta/Make e chamada.
-- Esta migration cria uma tabela separada de SIMULACOES, fora da fila real.
BEGIN;
DO $preflight$
BEGIN
  IF to_regclass('public.opportunities') IS NULL OR
     to_regclass('public.profiles') IS NULL OR
     to_regclass('public.audit_log') IS NULL THEN
    RAISE EXCEPTION 'H1-005B6 exige H1-005B4 e audit_log.';
  END IF;
  IF to_regclass('public.staging_dispatch_simulations') IS NOT NULL THEN
    RAISE EXCEPTION 'H1-005B6 ja existe: pare e valide antes de reaplicar.';
  END IF;
END;
$preflight$;

CREATE TABLE public.staging_dispatch_simulations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id uuid NOT NULL REFERENCES public.opportunities(id),
  fingerprint text NOT NULL CHECK (fingerprint ~ '^[a-f0-9]{64}$'),
  state text NOT NULL DEFAULT 'prepared'
       CHECK (state IN ('prepared','simulated','failed','cancelled')),
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  lock_version integer NOT NULL DEFAULT 1 CHECK (lock_version >= 1),
  last_failure_code text,
  created_by uuid REFERENCES public.profiles(id),
  updated_by uuid REFERENCES public.profiles(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT staging_dispatch_fingerprint_unique UNIQUE (opportunity_id, fingerprint),
  CONSTRAINT staging_dispatch_failure_coherence CHECK (
    (state = 'failed' AND last_failure_code = 'SIMULATED_FAILURE') OR
    (state <> 'failed' AND last_failure_code IS NULL)
  )
);
CREATE INDEX staging_dispatch_simulations_created_idx
  ON public.staging_dispatch_simulations(created_at DESC);
ALTER TABLE public.staging_dispatch_simulations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.staging_dispatch_simulations FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.staging_dispatch_simulations TO service_role;

-- Idempotente pelo par (oportunidade, SHA256 do texto renderizado).
CREATE FUNCTION public.vendra_staging_prepare_dispatch(
  p_opportunity_id uuid, p_fingerprint text, p_actor_id uuid
) RETURNS uuid LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $fn$
DECLARE v_id uuid; v_new boolean := false;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM public.profiles p WHERE p.id=p_actor_id AND p.status='active'
      AND p.access_level IN ('comercial','gerencial','administrativo')
  ) THEN
    RAISE EXCEPTION 'Sem permissao comercial' USING ERRCODE='42501';
  END IF;
  IF p_fingerprint IS NULL OR p_fingerprint !~ '^[a-f0-9]{64}$' THEN
    RAISE EXCEPTION 'Fingerprint invalido' USING ERRCODE='22023';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM public.opportunities o
    JOIN public.customers c ON c.id=o.customer_id
    WHERE o.id=p_opportunity_id AND o.status='open' AND o.archived_at IS NULL
      AND c.status='active'
  ) THEN
    RAISE EXCEPTION 'Oportunidade nao elegivel' USING ERRCODE='22023';
  END IF;
  INSERT INTO public.staging_dispatch_simulations
    (opportunity_id,fingerprint,created_by,updated_by)
  VALUES (p_opportunity_id,p_fingerprint,p_actor_id,p_actor_id)
  ON CONFLICT (opportunity_id,fingerprint) DO NOTHING
  RETURNING id INTO v_id;
  v_new := (v_id IS NOT NULL);
  IF NOT v_new THEN
    SELECT id INTO v_id FROM public.staging_dispatch_simulations
      WHERE opportunity_id=p_opportunity_id AND fingerprint=p_fingerprint;
  END IF;
  IF v_id IS NULL THEN RAISE EXCEPTION 'Simulacao nao localizada'; END IF;
  IF v_new THEN
    INSERT INTO public.audit_log(actor_id,entity_type,entity_id,action,payload)
    VALUES (p_actor_id,'staging_dispatch_simulation',v_id::text,'prepared',
            jsonb_build_object('stage','H1-005B6','external_send',false));
  END IF;
  RETURN v_id;
END;
$fn$;

-- Simula exclusivamente estado em tabela isolada. NAO ha HTTP, webhook, trigger ou fila real.
CREATE FUNCTION public.vendra_staging_change_dispatch_simulation(
  p_simulation_id uuid, p_action text, p_expected_version integer, p_actor_id uuid
) RETURNS integer LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $fn$
DECLARE v public.staging_dispatch_simulations%ROWTYPE; v_version integer;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM public.profiles p WHERE p.id=p_actor_id AND p.status='active'
      AND p.access_level IN ('comercial','gerencial','administrativo')
  ) THEN
    RAISE EXCEPTION 'Sem permissao comercial' USING ERRCODE='42501';
  END IF;
  SELECT * INTO v FROM public.staging_dispatch_simulations
    WHERE id=p_simulation_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Simulacao nao encontrada' USING ERRCODE='22023'; END IF;
  IF p_expected_version IS NULL OR v.lock_version <> p_expected_version THEN
    RAISE EXCEPTION 'Registro modificado; atualize a pagina' USING ERRCODE='40001';
  END IF;
  IF p_action='simulate_success' AND v.state='prepared' THEN
    UPDATE public.staging_dispatch_simulations
       SET state='simulated',attempt_count=attempt_count+1,last_failure_code=NULL,
           lock_version=lock_version+1,updated_by=p_actor_id,updated_at=now()
     WHERE id=p_simulation_id RETURNING lock_version INTO v_version;
  ELSIF p_action='simulate_failure' AND v.state='prepared' THEN
    UPDATE public.staging_dispatch_simulations
       SET state='failed',attempt_count=attempt_count+1,
           last_failure_code='SIMULATED_FAILURE',lock_version=lock_version+1,
           updated_by=p_actor_id,updated_at=now()
     WHERE id=p_simulation_id RETURNING lock_version INTO v_version;
  ELSIF p_action='retry' AND v.state='failed' THEN
    UPDATE public.staging_dispatch_simulations
       SET state='prepared',last_failure_code=NULL,lock_version=lock_version+1,
           updated_by=p_actor_id,updated_at=now()
     WHERE id=p_simulation_id RETURNING lock_version INTO v_version;
  ELSIF p_action='cancel' AND v.state IN ('prepared','failed') THEN
    UPDATE public.staging_dispatch_simulations
       SET state='cancelled',last_failure_code=NULL,lock_version=lock_version+1,
           updated_by=p_actor_id,updated_at=now()
     WHERE id=p_simulation_id RETURNING lock_version INTO v_version;
  ELSE
    RAISE EXCEPTION 'Transicao de estado nao permitida' USING ERRCODE='22023';
  END IF;
  INSERT INTO public.audit_log(actor_id,entity_type,entity_id,action,payload)
  VALUES (p_actor_id,'staging_dispatch_simulation',p_simulation_id::text,p_action,
    jsonb_build_object('stage','H1-005B6','from',v.state,
      'version',v_version,'external_send',false));
  RETURN v_version;
END;
$fn$;

REVOKE ALL ON FUNCTION public.vendra_staging_prepare_dispatch(uuid,text,uuid)
  FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.vendra_staging_change_dispatch_simulation(uuid,text,integer,uuid)
  FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_staging_prepare_dispatch(uuid,text,uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.vendra_staging_change_dispatch_simulation(uuid,text,integer,uuid) TO service_role;
COMMIT;
