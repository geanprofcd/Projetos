-- VENDRA H1-005B4 | EXCLUSIVAMENTE VENDRA-STAGING | Banco com H1-001..H1-004.
-- CONFIRA O NOME DO PROJETO NO CABECALHO DO SUPABASE ANTES DE EXECUTAR.
-- Nao aplicar no projeto principal. Não cria dados nem envia mensagens.
-- Funcoes SECURITY INVOKER: so service_role pode executar via backend autenticado.
BEGIN;
DO $preflight$
DECLARE obj text;
BEGIN
  FOREACH obj IN ARRAY ARRAY['profiles','customers','tickets','sales_funnels','funnel_stages',
    'opportunities','opportunity_stage_history','audit_log'] LOOP
    IF to_regclass(format('public.%I',obj)) IS NULL THEN
      RAISE EXCEPTION 'H1-005B4 exige a tabela public.%',obj;
    END IF;
  END LOOP;
  IF (SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public') <> 21 THEN
    RAISE EXCEPTION 'Esperado exatamente 21 tabelas publicas antes de H1-005B4';
  END IF;
  IF (SELECT count(*) FROM auth.users) <> 1 THEN
    RAISE EXCEPTION 'STAGING esperado com somente 1 usuario bootstrap; conferir ambiente';
  END IF;
END;
$preflight$;

CREATE OR REPLACE FUNCTION public.vendra_staging_create_funnel(
    p_name text, p_stage_names text[], p_actor_id uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $fn$
DECLARE
  v_id uuid;
  v_stage text;
  v_pos integer := 0;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.profiles
                 WHERE id=p_actor_id AND status='active' AND access_level='administrativo') THEN
    RAISE EXCEPTION 'Sem permissao para criar funis' USING ERRCODE='42501';
  END IF;
  IF p_name IS NULL OR length(btrim(p_name)) NOT BETWEEN 1 AND 120 THEN
    RAISE EXCEPTION 'Nome de funil invalido' USING ERRCODE='22023';
  END IF;
  IF COALESCE(array_length(p_stage_names,1),0) NOT BETWEEN 2 AND 12 THEN
    RAISE EXCEPTION 'Informe entre 2 e 12 etapas' USING ERRCODE='22023';
  END IF;
  IF EXISTS (SELECT 1 FROM unnest(p_stage_names) AS x(stage)
             WHERE x.stage IS NULL OR length(btrim(x.stage)) NOT BETWEEN 1 AND 120) THEN
    RAISE EXCEPTION 'Etapa vazia ou muito longa' USING ERRCODE='22023';
  END IF;
  IF (SELECT count(DISTINCT lower(btrim(x.stage))) FROM unnest(p_stage_names) AS x(stage))
      <> array_length(p_stage_names,1) THEN
    RAISE EXCEPTION 'Etapas duplicadas' USING ERRCODE='22023';
  END IF;
  INSERT INTO public.sales_funnels(name, is_active, is_default)
  VALUES (btrim(p_name), true, false) RETURNING id INTO v_id;
  FOREACH v_stage IN ARRAY p_stage_names LOOP
    v_pos:=v_pos+1;
    INSERT INTO public.funnel_stages(funnel_id,name,position)
    VALUES(v_id,btrim(v_stage),v_pos);
  END LOOP;
  INSERT INTO public.audit_log(actor_id,entity_type,entity_id,action,payload)
  VALUES(p_actor_id,'sales_funnel',v_id::text,'created',
         jsonb_build_object('stages',v_pos));
  RETURN v_id;
END;
$fn$;

CREATE OR REPLACE FUNCTION public.vendra_staging_create_opportunity(
    p_ticket_id uuid, p_stage_id uuid, p_title text, p_actor_id uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $fn$
DECLARE
  v_ticket public.tickets%ROWTYPE;
  v_stage public.funnel_stages%ROWTYPE;
  v_id uuid;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.profiles WHERE id=p_actor_id AND status='active'
              AND access_level IN ('comercial','gerencial','administrativo')) THEN
    RAISE EXCEPTION 'Sem permissao comercial' USING ERRCODE='42501';
  END IF;
  IF p_title IS NULL OR length(btrim(p_title)) NOT BETWEEN 1 AND 180 THEN
    RAISE EXCEPTION 'Titulo invalido' USING ERRCODE='22023';
  END IF;
  SELECT * INTO v_ticket FROM public.tickets WHERE id=p_ticket_id FOR UPDATE;
  IF NOT FOUND OR v_ticket.source <> 'interno'
       OR v_ticket.status IN ('finalizado','cancelado') THEN
    RAISE EXCEPTION 'Atendimento interno inexistente ou encerrado' USING ERRCODE='22023';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM public.customers WHERE id=v_ticket.customer_id AND status='active') THEN
    RAISE EXCEPTION 'Cliente inativo ou inexistente' USING ERRCODE='22023';
  END IF;
  SELECT * INTO v_stage FROM public.funnel_stages WHERE id=p_stage_id AND is_active;
  IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM public.sales_funnels
                              WHERE id=v_stage.funnel_id AND is_active) THEN
    RAISE EXCEPTION 'Etapa ou funil inativos' USING ERRCODE='22023';
  END IF;
  -- O bloqueio do ticket serializa chamadas concorrentes para o mesmo atendimento.
  SELECT id INTO v_id FROM public.opportunities
     WHERE ticket_id=p_ticket_id AND status='open' AND archived_at IS NULL LIMIT 1;
  IF v_id IS NOT NULL THEN RETURN v_id; END IF;
  INSERT INTO public.opportunities(customer_id,ticket_id,title,funnel_id,stage_id,assigned_user_id)
  VALUES(v_ticket.customer_id,p_ticket_id,btrim(p_title),v_stage.funnel_id,p_stage_id,p_actor_id)
  RETURNING id INTO v_id;
  INSERT INTO public.opportunity_stage_history(opportunity_id,from_stage_id,to_stage_id,moved_by,source)
  VALUES(v_id,NULL,p_stage_id,p_actor_id,'staging_initial');
  INSERT INTO public.audit_log(actor_id,entity_type,entity_id,action,payload)
  VALUES(p_actor_id,'opportunity',v_id::text,'created',jsonb_build_object('ticket_id',p_ticket_id));
  RETURN v_id;
END;
$fn$;

CREATE OR REPLACE FUNCTION public.vendra_staging_move_opportunity(
    p_opportunity_id uuid, p_to_stage_id uuid,
    p_expected_lock_version integer, p_actor_id uuid
) RETURNS integer
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $fn$
DECLARE
  v_opp public.opportunities%ROWTYPE;
  v_stage public.funnel_stages%ROWTYPE;
  v_version integer;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.profiles WHERE id=p_actor_id AND status='active'
              AND access_level IN ('comercial','gerencial','administrativo')) THEN
    RAISE EXCEPTION 'Sem permissao comercial' USING ERRCODE='42501';
  END IF;
  SELECT * INTO v_opp FROM public.opportunities WHERE id=p_opportunity_id FOR UPDATE;
  IF NOT FOUND OR v_opp.status <> 'open' OR v_opp.archived_at IS NOT NULL THEN
    RAISE EXCEPTION 'Oportunidade nao esta aberta' USING ERRCODE='22023';
  END IF;
  IF p_expected_lock_version IS NULL OR v_opp.lock_version <> p_expected_lock_version THEN
    RAISE EXCEPTION 'Etapa alterada por outro usuario; atualize a tela' USING ERRCODE='40001';
  END IF;
  SELECT * INTO v_stage FROM public.funnel_stages WHERE id=p_to_stage_id
    AND funnel_id=v_opp.funnel_id AND is_active;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Etapa invalida para este funil' USING ERRCODE='22023';
  END IF;
  IF v_opp.stage_id=p_to_stage_id THEN RETURN v_opp.lock_version; END IF;
  UPDATE public.opportunities SET stage_id=p_to_stage_id,
      lock_version=lock_version+1, updated_at=now()
    WHERE id=p_opportunity_id RETURNING lock_version INTO v_version;
  INSERT INTO public.opportunity_stage_history(opportunity_id,from_stage_id,to_stage_id,moved_by,source)
  VALUES(v_opp.id,v_opp.stage_id,p_to_stage_id,p_actor_id,'staging_manual');
  INSERT INTO public.audit_log(actor_id,entity_type,entity_id,action,payload)
  VALUES(p_actor_id,'opportunity',v_opp.id::text,'stage_changed',
    jsonb_build_object('from',v_opp.stage_id,'to',p_to_stage_id,'version',v_version));
  RETURN v_version;
END;
$fn$;

REVOKE ALL ON FUNCTION public.vendra_staging_create_funnel(text,text[],uuid) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.vendra_staging_create_opportunity(uuid,uuid,text,uuid) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.vendra_staging_move_opportunity(uuid,uuid,integer,uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_staging_create_funnel(text,text[],uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.vendra_staging_create_opportunity(uuid,uuid,text,uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.vendra_staging_move_opportunity(uuid,uuid,integer,uuid) TO service_role;
COMMIT;
