-- Regras comerciais solicitadas em 16/10/2026. Sem dados STAGING, envios ou novas tabelas.
CREATE OR REPLACE FUNCTION public.vendra_commercial_stage_v1(p_ticket_id uuid,p_target text,p_source text)
RETURNS jsonb LANGUAGE plpgsql SET search_path TO '' AS $fn$
DECLARE t public.tickets%ROWTYPE; o public.opportunities%ROWTYPE;
  dest public.funnel_stages%ROWTYPE; current_position integer; f uuid;
BEGIN
 IF p_target NOT IN ('qualification','proposal') THEN RAISE EXCEPTION 'Destino comercial invalido'; END IF;
 SELECT * INTO t FROM public.tickets WHERE id=p_ticket_id;
 IF NOT FOUND OR t.status IN ('finalizado','cancelado') THEN RETURN jsonb_build_object('applied',false); END IF;
 SELECT * INTO o FROM public.opportunities WHERE ticket_id=t.id AND status='open' AND archived_at IS NULL FOR UPDATE;
 IF o.id IS NULL AND EXISTS(SELECT 1 FROM public.opportunities WHERE ticket_id=t.id) THEN
  RETURN jsonb_build_object('applied',false,'reason','closed_or_archived');
 END IF;
 IF o.id IS NOT NULL THEN f:=o.funnel_id;
 ELSE SELECT id INTO f FROM public.sales_funnels WHERE lower(btrim(name))='funil comercial' AND is_active=true;
 END IF;
 IF NOT EXISTS(SELECT 1 FROM public.sales_funnels WHERE id=f AND is_active=true) THEN RETURN jsonb_build_object('applied',false); END IF;
 SELECT * INTO dest FROM public.funnel_stages WHERE funnel_id=f AND is_active=true
   AND lower(btrim(name))=CASE WHEN p_target='qualification' THEN 'qualificação' ELSE 'proposta' END LIMIT 1;
 IF dest.id IS NULL THEN RETURN jsonb_build_object('applied',false,'reason','stage_not_configured'); END IF;
 IF o.id IS NULL THEN
  INSERT INTO public.opportunities(customer_id,ticket_id,title,funnel_id,stage_id,assigned_user_id,status)
   VALUES(t.customer_id,t.id,left(t.title,180),f,dest.id,t.assigned_user_id,'open') RETURNING * INTO o;
  INSERT INTO public.opportunity_stage_history(opportunity_id,from_stage_id,to_stage_id,source)
   VALUES(o.id,NULL,dest.id,'system');
 ELSE
  SELECT position INTO current_position FROM public.funnel_stages WHERE id=o.stage_id;
  IF current_position>=dest.position THEN RETURN jsonb_build_object('applied',false,'reason','no_regression'); END IF;
  UPDATE public.opportunities SET stage_id=dest.id,lock_version=lock_version+1,updated_at=now(),
   kanban_position=coalesce((SELECT max(kanban_position)+1000 FROM public.opportunities WHERE stage_id=dest.id AND status='open'),1000)
   WHERE id=o.id;
  INSERT INTO public.opportunity_stage_history(opportunity_id,from_stage_id,to_stage_id,source)
   VALUES(o.id,o.stage_id,dest.id,'system');
 END IF;
 INSERT INTO public.audit_log(entity_type,entity_id,action,payload)
  VALUES('opportunity',o.id::text,'commercial_auto_stage',jsonb_build_object('stage_id',dest.id,'source',p_source));
 RETURN jsonb_build_object('applied',true,'stage_id',dest.id,'opportunity_id',o.id);
END; $fn$;
REVOKE ALL ON FUNCTION public.vendra_commercial_stage_v1(uuid,text,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_commercial_stage_v1(uuid,text,text) TO service_role;

CREATE OR REPLACE FUNCTION public.vendra_whatsapp_receive_v1(p_phone text, p_name text, p_body text, p_external_message_id text, p_occurred_at timestamp with time zone)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE
  v_phone text := regexp_replace(coalesce(p_phone,''),'[^0-9]','','g');
  v_aliases text[];
  v_hash text;
  v_event public.integration_events%ROWTYPE;
  v_customer public.customers%ROWTYPE;
  v_ticket public.tickets%ROWTYPE;
  v_message public.messages%ROWTYPE;
  v_count integer;
  v_created_ticket boolean := false;
  v_default_mode text;
  v_ai_config jsonb;
  v_first_reply boolean;
BEGIN
  IF v_phone !~ '^55[0-9]{10,11}$'
     OR p_body IS NULL OR length(btrim(p_body)) NOT BETWEEN 1 AND 10000
     OR p_external_message_id IS NULL OR length(btrim(p_external_message_id)) NOT BETWEEN 1 AND 430
     OR p_occurred_at IS NULL OR NOT isfinite(p_occurred_at)
     OR p_occurred_at > now() + interval '60 seconds'
     OR p_occurred_at < timestamptz '2020-01-01 00:00:00+00' THEN
    RAISE EXCEPTION 'Entrada WhatsApp invalida' USING ERRCODE='22023';
  END IF;
  -- Canonicaliza a forma mobile BR que a Meta pode retornar sem o nono digito.
  IF length(v_phone)=13 AND substr(v_phone,5,1)='9' THEN
    v_phone := substr(v_phone,1,4)||substr(v_phone,6);
  END IF;
  v_aliases := ARRAY[v_phone,substr(v_phone,1,4)||'9'||substr(v_phone,5)];
  v_hash := encode(sha256(convert_to(jsonb_build_array(v_phone,btrim(p_body),extract(epoch FROM p_occurred_at))::text,'UTF8')),'hex');
  -- Mesma ordem de locks em todas as entradas: evento, depois identidade do telefone.
  PERFORM pg_advisory_xact_lock(hashtextextended('whatsapp:event:'||p_external_message_id,0));
  SELECT * INTO v_event FROM public.integration_events
    WHERE provider='whatsapp' AND external_id=p_external_message_id FOR UPDATE;
  IF FOUND THEN
    IF v_event.event_type <> 'message.inbound' OR v_event.payload_hash IS DISTINCT FROM v_hash THEN
      RAISE EXCEPTION 'WAMID reutilizado com outro payload' USING ERRCODE='PT409';
    END IF;
    IF v_event.status='processed' THEN
      SELECT * INTO v_message FROM public.messages WHERE external_message_id=p_external_message_id;
      IF NOT FOUND THEN RAISE EXCEPTION 'Evento sem mensagem persistida' USING ERRCODE='55000'; END IF;
      SELECT * INTO v_ticket FROM public.tickets WHERE id=v_message.ticket_id;
      RETURN jsonb_build_object('accepted',true,'duplicate',true,'customer_id',v_ticket.customer_id,
        'ticket_id',v_ticket.id,'message_id',v_message.id,'external_message_id',p_external_message_id);
    END IF;
    RAISE EXCEPTION 'Evento legado exige reconciliacao' USING ERRCODE='55000';
  END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended('whatsapp:phone:'||v_phone,0));
  SELECT count(*) INTO v_count FROM public.customers WHERE phone_normalized=ANY(v_aliases);
  IF v_count>1 THEN RAISE EXCEPTION 'Identidade de telefone ambigua' USING ERRCODE='PT409'; END IF;
  SELECT * INTO v_customer FROM public.customers WHERE phone_normalized=ANY(v_aliases) FOR UPDATE;
  IF NOT FOUND THEN
    INSERT INTO public.customers(name,phone,phone_normalized,status)
      VALUES(left(coalesce(nullif(btrim(p_name),''),'WhatsApp '||v_phone),180),v_phone,v_phone,'active')
      RETURNING * INTO v_customer;
  ELSIF v_customer.status <> 'active' THEN
    RAISE EXCEPTION 'Cliente inativo' USING ERRCODE='22023';
  END IF;
  SELECT * INTO v_ticket FROM public.tickets
    WHERE customer_id=v_customer.id AND source='whatsapp' AND status NOT IN ('finalizado','cancelado')
    ORDER BY updated_at DESC,id LIMIT 1 FOR UPDATE;
  IF NOT FOUND THEN
    -- Configuracao global vale somente para novos atendimentos.
    SELECT settings INTO v_ai_config FROM public.integration_settings WHERE key='ai_automation';
    v_default_mode := CASE WHEN coalesce(v_ai_config->>'enabled','false')='true'
      AND coalesce(v_ai_config->>'default_mode','ai')='ai' THEN 'ai' ELSE 'human' END;
    INSERT INTO public.tickets(title,customer_id,source,status,priority,automation_mode)
      VALUES(left(btrim(p_body),80),v_customer.id,'whatsapp','novo','normal',v_default_mode)
      RETURNING * INTO v_ticket;
    v_created_ticket := true;
  END IF;
  v_first_reply := NOT EXISTS(SELECT 1 FROM public.messages WHERE ticket_id=v_ticket.id AND direction='inbound' AND is_internal=false);
  IF v_first_reply AND v_ticket.ai_paused_by IS NULL THEN
    SELECT settings INTO v_ai_config FROM public.integration_settings WHERE key='ai_automation';
    IF coalesce(v_ai_config->>'enabled','false')='true' AND v_ticket.automation_mode<>'ai' THEN
      UPDATE public.tickets SET automation_mode='ai',automation_version=automation_version+1,
        ai_resumed_at=now(),ai_resumed_by='first_lead_reply' WHERE id=v_ticket.id;
    END IF;
  END IF;
  INSERT INTO public.messages(ticket_id,sender_kind,body,channel,direction,is_internal,
      external_message_id,delivery_status,external_status_updated_at,created_at)
    VALUES(v_ticket.id,'customer',btrim(p_body),'whatsapp','inbound',false,
      p_external_message_id,'received',p_occurred_at,p_occurred_at)
    RETURNING * INTO v_message;
  UPDATE public.tickets SET updated_at=now(),
    whatsapp_active_at=greatest(whatsapp_active_at,p_occurred_at) WHERE id=v_ticket.id;
  IF v_first_reply THEN
    PERFORM public.vendra_commercial_stage_v1(v_ticket.id,'qualification','first_lead_reply');
  END IF;
  INSERT INTO public.integration_events(provider,external_id,event_type,status,payload_hash,payload,
      entity_type,entity_id,processed_at)
    VALUES('whatsapp',p_external_message_id,'message.inbound','processed',v_hash,
      jsonb_build_object('phone',v_phone,'occurred_at',p_occurred_at,'message_id',v_message.id),
      'ticket',v_ticket.id::text,now());
  RETURN jsonb_build_object('accepted',true,'duplicate',false,'customer_id',v_customer.id,
    'ticket_id',v_ticket.id,'message_id',v_message.id,'external_message_id',p_external_message_id,
    'created_ticket',v_created_ticket);
END;
$function$;
CREATE OR REPLACE FUNCTION public.vendra_whatsapp_bind_v1(p_outbox_id uuid, p_provider_message_id text, p_claim_token text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE o public.whatsapp_outbox%ROWTYPE; ev record; reconciled integer:=0; status_result jsonb;
BEGIN
 IF p_provider_message_id IS NULL OR length(btrim(p_provider_message_id)) NOT BETWEEN 1 AND 430
    OR p_claim_token IS NULL OR length(p_claim_token)<32 THEN RAISE EXCEPTION 'Vinculo invalido' USING ERRCODE='22023'; END IF;
 -- Mesma ordem de locks usada pela RPC de status: WAMID, depois outbox.
 PERFORM pg_advisory_xact_lock(hashtextextended('whatsapp:status:'||p_provider_message_id,0));
 SELECT * INTO o FROM public.whatsapp_outbox WHERE id=p_outbox_id FOR UPDATE;
 IF NOT FOUND OR o.claimed_by IS DISTINCT FROM p_claim_token THEN
  RAISE EXCEPTION 'Reserva divergente' USING ERRCODE='42501';
 END IF;
 IF o.provider_message_id IS NOT NULL AND o.provider_message_id<>p_provider_message_id THEN
  RAISE EXCEPTION 'Saida ja vinculada a outro WAMID' USING ERRCODE='PT409';
 END IF;
 IF EXISTS(SELECT 1 FROM public.whatsapp_outbox WHERE provider_message_id=p_provider_message_id AND id<>o.id) THEN
  RAISE EXCEPTION 'WAMID ja pertence a outra saida' USING ERRCODE='PT409';
 END IF;
 IF o.status NOT IN ('claimed','sent','delivered','read','failed') THEN
  RAISE EXCEPTION 'Saida nao reservada para envio' USING ERRCODE='22023';
 END IF;
 UPDATE public.whatsapp_outbox SET provider_message_id=p_provider_message_id,updated_at=now() WHERE id=o.id;
 FOR ev IN SELECT payload FROM public.integration_events WHERE provider='whatsapp' AND event_type='message.status'
  AND status='received' AND payload->>'provider_message_id'=p_provider_message_id
  ORDER BY (payload->>'occurred_at')::timestamptz,created_at,id LOOP
  status_result := public.vendra_whatsapp_status_v1(p_provider_message_id,ev.payload->>'status',
   (ev.payload->>'occurred_at')::timestamptz,ev.payload->>'recipient_id',ev.payload->>'error_message');
  reconciled := reconciled+1;
 END LOOP;
 -- Confirmacao Make, somente depois de reconciliar timestamps reais pendentes.
 -- sent aqui e confirmacao do conector; delivered/read exigem eventos Meta.
 PERFORM public.vendra_whatsapp_status_v1(p_provider_message_id,'sent',now(),o.phone,NULL);
 SELECT * INTO o FROM public.whatsapp_outbox WHERE id=p_outbox_id;
 RETURN jsonb_build_object('accepted',true,'id',o.id,'status',o.status,'reconciled',reconciled,
  'provider_message_id',o.provider_message_id);
END; $function$;
CREATE OR REPLACE FUNCTION public.vendra_whatsapp_status_v1(p_provider_message_id text, p_status text, p_occurred_at timestamp with time zone, p_recipient_id text, p_error_message text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE
  v_key text;
  v_event public.integration_events%ROWTYPE;
  v_item public.whatsapp_outbox%ROWTYPE;
  v_phone text := regexp_replace(coalesce(p_recipient_id,''),'[^0-9]','','g');
  v_bound_phone text;
  v_count integer;
  v_ignore boolean := false;
  v_rank integer;
  v_current_rank integer;
BEGIN
  IF p_provider_message_id IS NULL OR length(btrim(p_provider_message_id)) NOT BETWEEN 1 AND 430
     OR p_status IS NULL OR p_status NOT IN ('sent','delivered','read','failed')
     OR v_phone !~ '^55[0-9]{10,11}$' OR p_occurred_at IS NULL OR NOT isfinite(p_occurred_at)
     OR p_occurred_at > now()+interval '60 seconds'
     OR p_occurred_at < timestamptz '2020-01-01 00:00:00+00' THEN
    RAISE EXCEPTION 'Status WhatsApp invalido' USING ERRCODE='22023';
  END IF;
  IF length(v_phone)=13 AND substr(v_phone,5,1)='9' THEN
    v_phone := substr(v_phone,1,4)||substr(v_phone,6);
  END IF;
  v_key := 'provider-status:'||p_provider_message_id||':'||p_status;
  PERFORM pg_advisory_xact_lock(hashtextextended('whatsapp:status:'||p_provider_message_id,0));
  SELECT * INTO v_event FROM public.integration_events
    WHERE provider='whatsapp' AND external_id=v_key FOR UPDATE;
  IF FOUND AND (v_event.payload->>'recipient_id') IS DISTINCT FROM v_phone THEN
    RAISE EXCEPTION 'Status pertence a outro destinatario' USING ERRCODE='PT409';
  END IF;
  IF FOUND AND v_event.status IN ('processed','ignored') THEN
    RETURN jsonb_build_object('accepted',true,'duplicate',true,'updated',false,'pending_match',false);
  END IF;
  SELECT count(*) INTO v_count FROM public.whatsapp_outbox WHERE provider_message_id=p_provider_message_id;
  IF v_count>1 THEN RAISE EXCEPTION 'WAMID associado a varias saidas' USING ERRCODE='PT409'; END IF;
  SELECT * INTO v_item FROM public.whatsapp_outbox WHERE provider_message_id=p_provider_message_id FOR UPDATE;
  IF NOT FOUND THEN
    INSERT INTO public.integration_events(provider,external_id,event_type,status,payload)
      VALUES('whatsapp',v_key,'message.status','received',jsonb_build_object(
        'provider_message_id',p_provider_message_id,'status',p_status,'occurred_at',p_occurred_at,
        'recipient_id',v_phone,'error_message',left(p_error_message,1000)))
      ON CONFLICT(provider,external_id) DO NOTHING;
    RETURN jsonb_build_object('accepted',true,'updated',false,'pending_match',true,'status',p_status);
  END IF;
  v_bound_phone := regexp_replace(v_item.phone,'[^0-9]','','g');
  IF length(v_bound_phone)=13 AND substr(v_bound_phone,5,1)='9' THEN
    v_bound_phone := substr(v_bound_phone,1,4)||substr(v_bound_phone,6);
  END IF;
  IF v_bound_phone IS DISTINCT FROM v_phone THEN
    RAISE EXCEPTION 'Destinatario diverge da saida' USING ERRCODE='PT409';
  END IF;
  v_rank := CASE p_status WHEN 'sent' THEN 2 WHEN 'delivered' THEN 3 WHEN 'read' THEN 4 ELSE -1 END;
  v_current_rank := CASE v_item.status WHEN 'pending' THEN 0 WHEN 'claimed' THEN 1
    WHEN 'sent' THEN 2 WHEN 'delivered' THEN 3 WHEN 'read' THEN 4 ELSE -1 END;
  v_ignore := v_item.status IN ('read','cancelled') OR
    (p_status='failed' AND v_item.status IN ('failed','delivered','read')) OR
    (p_status<>'failed' AND v_rank<=v_current_rank);
  IF NOT v_ignore THEN
    UPDATE public.whatsapp_outbox SET status=p_status,last_error=CASE WHEN p_status='failed'
      THEN left(p_error_message,1000) ELSE NULL END,updated_at=now() WHERE id=v_item.id;
    UPDATE public.messages SET delivery_status=p_status,external_status_updated_at=p_occurred_at
      WHERE id=v_item.message_id AND ticket_id=v_item.ticket_id;
  END IF;
  IF NOT v_ignore AND p_status IN ('delivered','read') AND v_item.status NOT IN ('delivered','read') AND EXISTS(
    SELECT 1 FROM public.messages WHERE id=v_item.message_id AND direction='outbound' AND is_internal=false
      AND body ~* 'https?://(www\.)?calendly\.com/') THEN
    PERFORM public.vendra_commercial_stage_v1(v_item.ticket_id,'proposal','calendly_delivered');
  END IF;
  INSERT INTO public.integration_events(provider,external_id,event_type,status,payload,entity_type,entity_id,processed_at)
    VALUES('whatsapp',v_key,'message.status',CASE WHEN v_ignore THEN 'ignored' ELSE 'processed' END,
      jsonb_build_object('provider_message_id',p_provider_message_id,'status',p_status,
        'occurred_at',p_occurred_at,'recipient_id',v_phone,'error_message',left(p_error_message,1000)),
      'whatsapp_outbox',v_item.id::text,now())
    ON CONFLICT(provider,external_id) DO UPDATE SET status=excluded.status,
      entity_type=excluded.entity_type,entity_id=excluded.entity_id,processed_at=excluded.processed_at;
  RETURN jsonb_build_object('accepted',true,'updated',NOT v_ignore,'ignored',v_ignore,
    'pending_match',false,'id',v_item.id,'status',CASE WHEN v_ignore THEN v_item.status ELSE p_status END);
END;
$function$;
CREATE OR REPLACE FUNCTION public.vendra_ticket_activity_list_v1(p_customer_ids uuid[] DEFAULT NULL,p_limit integer DEFAULT 100)
RETURNS SETOF public.tickets LANGUAGE sql STABLE SET search_path TO '' AS $fn$
 SELECT t.* FROM public.tickets t
 LEFT JOIN LATERAL (
  SELECT created_at,direction FROM public.messages WHERE ticket_id=t.id AND is_internal=false
   AND direction IN ('inbound','outbound') AND coalesce(delivery_status,'') NOT IN ('failed','cancelled','pending')
  ORDER BY created_at DESC,(direction='inbound') DESC,id DESC LIMIT 1
 ) latest ON true
 WHERE p_customer_ids IS NULL OR t.customer_id=ANY(p_customer_ids)
 ORDER BY coalesce(latest.direction='inbound',false) DESC,
   coalesce(latest.created_at,t.updated_at,t.created_at) DESC,t.id DESC
 LIMIT greatest(1,least(coalesce(p_limit,100),5000));
$fn$;
REVOKE ALL ON FUNCTION public.vendra_ticket_activity_list_v1(uuid[],integer) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_ticket_activity_list_v1(uuid[],integer) TO service_role;

