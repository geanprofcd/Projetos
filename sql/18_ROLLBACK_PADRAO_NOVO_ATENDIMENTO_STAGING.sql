-- PREPARADO, NAO APLICADO. Exige autorizacao especifica somente STAGING.
-- Nao ativa IA, worker, lote ou envios. Nao cria tabelas/RLS.
BEGIN;
DO $guard$ BEGIN
 IF to_regclass('public.staging_transport_contracts') IS NULL THEN RAISE EXCEPTION 'Somente VENDRA-STAGING'; END IF;
END; $guard$;
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
    INSERT INTO public.tickets(title,customer_id,source,status,priority,automation_mode)
      VALUES(left(btrim(p_body),80),v_customer.id,'whatsapp','novo','normal','human')
      RETURNING * INTO v_ticket;
    v_created_ticket := true;
  END IF;
  INSERT INTO public.messages(ticket_id,sender_kind,body,channel,direction,is_internal,
      external_message_id,delivery_status,external_status_updated_at,created_at)
    VALUES(v_ticket.id,'customer',btrim(p_body),'whatsapp','inbound',false,
      p_external_message_id,'received',p_occurred_at,p_occurred_at)
    RETURNING * INTO v_message;
  UPDATE public.tickets SET updated_at=now(),
    whatsapp_active_at=greatest(whatsapp_active_at,p_occurred_at) WHERE id=v_ticket.id;
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

REVOKE ALL ON FUNCTION public.vendra_whatsapp_receive_v1(text,text,text,text,timestamptz) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_receive_v1(text,text,text,text,timestamptz) TO service_role;
COMMIT;

