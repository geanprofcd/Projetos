-- PREPARADO, NAO APLICADO. Promocao seletiva de 12 RPCs homologadas.
-- Destino: VENDRA original znkjibqcikuigfwfsbjb. Sem dados/configuracao/worker/envio.
-- Fonte: definicoes vivas do STAGING em 16/10/2026; SECURITY INVOKER/search_path vazio.
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND (p.proname LIKE 'vendra_whatsapp_%' OR p.proname LIKE 'vendra_dispatch_%')) THEN RAISE EXCEPTION 'Funcoes ja existem; reconciliar antes de promover'; END IF;
END $$;
CREATE OR REPLACE FUNCTION public.vendra_dispatch_bind_v1(p_dispatch_id uuid, p_outbox_id uuid, p_provider_message_id text, p_claim_token text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE d public.dispatches%ROWTYPE; o public.whatsapp_outbox%ROWTYPE; result jsonb;
BEGIN
 SELECT * INTO d FROM public.dispatches WHERE id=p_dispatch_id;
 SELECT * INTO o FROM public.whatsapp_outbox WHERE id=p_outbox_id;
 IF d.id IS NULL OR o.id IS NULL OR d.message_id<>o.message_id OR d.ticket_id<>o.ticket_id OR d.customer_id<>o.customer_id THEN
  RAISE EXCEPTION 'Reserva nao pertence ao disparo' USING ERRCODE='42501';
 END IF;
 result:=public.vendra_whatsapp_bind_v1(p_outbox_id,p_provider_message_id,p_claim_token);
 UPDATE public.messages SET external_message_id=p_provider_message_id WHERE id=d.message_id
  AND (external_message_id IS NULL OR external_message_id=p_provider_message_id);
 IF NOT FOUND THEN RAISE EXCEPTION 'Mensagem ja tem outro WAMID' USING ERRCODE='PT409'; END IF;
 UPDATE public.dispatches SET provider_message_id=p_provider_message_id,status=result->>'status',updated_at=now()
  WHERE id=d.id AND (provider_message_id IS NULL OR provider_message_id=p_provider_message_id);
 IF NOT FOUND THEN RAISE EXCEPTION 'Disparo ja tem outro WAMID' USING ERRCODE='PT409'; END IF;
 RETURN result||jsonb_build_object('dispatch_id',d.id);
END; $function$;
REVOKE ALL ON FUNCTION public.vendra_dispatch_bind_v1(p_dispatch_id uuid, p_outbox_id uuid, p_provider_message_id text, p_claim_token text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_dispatch_bind_v1(p_dispatch_id uuid, p_outbox_id uuid, p_provider_message_id text, p_claim_token text) TO service_role;

CREATE OR REPLACE FUNCTION public.vendra_dispatch_prepare_v1(p_dispatch_id uuid, p_phone text, p_name text, p_template_key text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE d public.dispatches%ROWTYPE; t public.tickets%ROWTYPE; c public.customers%ROWTYPE;
 m public.messages%ROWTYPE; o public.whatsapp_outbox%ROWTYPE; token text; v_body text;
 supplied text; recorded text; customer_phone text;
BEGIN
 SELECT * INTO d FROM public.dispatches WHERE id=p_dispatch_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Disparo inexistente' USING ERRCODE='22023'; END IF;
 supplied:=regexp_replace(coalesce(p_phone,''),'[^0-9]','','g');
 recorded:=regexp_replace(d.phone,'[^0-9]','','g');
 IF length(supplied)=13 AND substring(supplied,5,1)='9' THEN supplied:=left(supplied,4)||substring(supplied,6); END IF;
 IF length(recorded)=13 AND substring(recorded,5,1)='9' THEN recorded:=left(recorded,4)||substring(recorded,6); END IF;
 IF supplied !~ '^55[1-9][0-9][0-9]{8}$' OR supplied IS DISTINCT FROM recorded OR
    p_name IS DISTINCT FROM d.name OR p_template_key IS DISTINCT FROM 'continuar_atendimento_vendra' OR
    d.template_key IS DISTINCT FROM p_template_key OR length(d.name) NOT BETWEEN 1 AND 160 THEN
  RAISE EXCEPTION 'Payload diverge do disparo' USING ERRCODE='PT409';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM public.profiles WHERE id=d.requested_by AND status='active'
               AND access_level IN ('administrativo','comercial','gerencial')) THEN
  RAISE EXCEPTION 'Solicitante sem permissao de disparo' USING ERRCODE='42501';
 END IF;
 SELECT * INTO t FROM public.tickets WHERE id=d.ticket_id;
 SELECT * INTO c FROM public.customers WHERE id=d.customer_id;
 customer_phone:=regexp_replace(coalesce(c.phone_normalized,''),'[^0-9]','','g');
 IF length(customer_phone)=13 AND substring(customer_phone,5,1)='9' THEN customer_phone:=left(customer_phone,4)||substring(customer_phone,6); END IF;
 IF t.id IS NULL OR c.id IS NULL OR t.customer_id<>c.id OR t.source<>'whatsapp' OR
    t.status IN ('cancelado','finalizado') OR c.status<>'active' OR customer_phone<>supplied THEN
  RAISE EXCEPTION 'Atendimento/cliente fora do escopo' USING ERRCODE='42501';
 END IF;
 IF d.opportunity_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM public.opportunities
    WHERE id=d.opportunity_id AND customer_id=c.id AND ticket_id=t.id AND status='open' AND archived_at IS NULL) THEN
  RAISE EXCEPTION 'Oportunidade indisponivel' USING ERRCODE='42501';
 END IF;
 IF NOT coalesce((SELECT settings->'enabled'='true'::jsonb FROM public.integration_settings WHERE key='dispatch_bridge'),false) THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,'reason','dispatch_disabled');
 END IF;
 -- Nunca reautorizar reserva ou repetir implicitamente falha/cancelamento.
 SELECT * INTO o FROM public.whatsapp_outbox WHERE message_id=d.message_id;
 IF FOUND OR d.status<>'pending' OR d.provider_message_id IS NOT NULL THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,'duplicate',true,'reason','dispatch_already_reserved');
 END IF;
 SELECT * INTO m FROM public.messages WHERE id=d.message_id FOR UPDATE;
 IF NOT FOUND OR m.ticket_id<>t.id OR m.direction<>'outbound' OR m.channel<>'whatsapp'
    OR m.is_internal OR m.delivery_status IS DISTINCT FROM 'pending' OR m.external_message_id IS NOT NULL THEN
  RAISE EXCEPTION 'Mensagem indisponivel para reserva' USING ERRCODE='42501';
 END IF;
 v_body:='Oi, '||d.name||E'! Tudo bem?\n\nAqui é o Dario. Posso confirmar uma informação rapidinho?';
 token:=gen_random_uuid()::text;
 UPDATE public.messages SET body=v_body,delivery_status='claimed' WHERE id=m.id;
 INSERT INTO public.whatsapp_outbox(ticket_id,message_id,customer_id,phone,body,status,attempt_count,claimed_at,claimed_by)
  VALUES(t.id,m.id,c.id,d.phone,v_body,'claimed',1,now(),token) RETURNING * INTO o;
 UPDATE public.dispatches SET status='submitted',updated_at=now() WHERE id=d.id;
 RETURN jsonb_build_object('accepted',true,'authorized',true,'suppressed',false,'duplicate',false,
  'dispatch_id',d.id,'outbox_id',o.id,'message_id',m.id,'template_key',d.template_key,'name',d.name,
  'outbox',jsonb_build_object('id',o.id,'phone',o.phone,'claim_token',token,
   'delivery_policy',jsonb_build_object('authorized_to_send',true,'template_required',true)));
END; $function$;
REVOKE ALL ON FUNCTION public.vendra_dispatch_prepare_v1(p_dispatch_id uuid, p_phone text, p_name text, p_template_key text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_dispatch_prepare_v1(p_dispatch_id uuid, p_phone text, p_name text, p_template_key text) TO service_role;

CREATE OR REPLACE FUNCTION public.vendra_dispatch_provider_status_v1(p_provider_message_id text, p_status text, p_occurred_at timestamp with time zone, p_recipient_id text, p_error_message text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE result jsonb; o public.whatsapp_outbox%ROWTYPE;
BEGIN
 result:=public.vendra_whatsapp_status_v1(p_provider_message_id,p_status,p_occurred_at,p_recipient_id,p_error_message);
 SELECT * INTO o FROM public.whatsapp_outbox WHERE provider_message_id=p_provider_message_id;
 IF FOUND THEN
  UPDATE public.dispatches SET status=o.status,provider_message_id=o.provider_message_id,updated_at=now()
   WHERE message_id=o.message_id AND ticket_id=o.ticket_id AND customer_id=o.customer_id
     AND (provider_message_id IS NULL OR provider_message_id=o.provider_message_id);
 END IF;
 RETURN result;
END; $function$;
REVOKE ALL ON FUNCTION public.vendra_dispatch_provider_status_v1(p_provider_message_id text, p_status text, p_occurred_at timestamp with time zone, p_recipient_id text, p_error_message text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_dispatch_provider_status_v1(p_provider_message_id text, p_status text, p_occurred_at timestamp with time zone, p_recipient_id text, p_error_message text) TO service_role;

CREATE OR REPLACE FUNCTION public.vendra_dispatch_request_v1(p_actor_id uuid, p_name text, p_phone text, p_stage_id uuid, p_request_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE
 actor public.profiles%ROWTYPE;
 c public.customers%ROWTYPE;
 t public.tickets%ROWTYPE;
 o public.opportunities%ROWTYPE;
 d public.dispatches%ROWTYPE;
 stage public.funnel_stages%ROWTYPE;
 phone text := regexp_replace(coalesce(p_phone,''),'[^0-9]','','g');
 aliases text[];
 message_id uuid;
 existing_count integer;
 request_key text;
BEGIN
 SELECT * INTO actor FROM public.profiles WHERE id=p_actor_id;
 IF actor.id IS NULL OR actor.status<>'active' OR
    actor.access_level NOT IN ('administrativo','comercial','gerencial') THEN
  RAISE EXCEPTION 'Perfil sem permissao de disparo' USING ERRCODE='42501';
 END IF;
 IF p_request_id IS NULL OR p_stage_id IS NULL OR
    length(btrim(coalesce(p_name,''))) NOT BETWEEN 1 AND 160 OR
    phone !~ '^55[1-9][0-9][0-9]{8,9}$' THEN
  RAISE EXCEPTION 'Pedido invalido' USING ERRCODE='22023';
 END IF;
 IF length(phone)=13 AND substring(phone,5,1)='9' THEN
  phone:=left(phone,4)||substring(phone,6);
 END IF;
 IF length(phone)<>12 THEN RAISE EXCEPTION 'Telefone invalido' USING ERRCODE='22023'; END IF;
 aliases:=ARRAY[phone,left(phone,4)||'9'||substring(phone,5)];
 request_key:='vendra-dispatch-'||p_request_id::text;
 -- Repeticao do formulario nunca cria outro conjunto de registros.
 PERFORM pg_advisory_xact_lock(hashtextextended('dispatch:request:'||request_key,0));
 SELECT * INTO d FROM public.dispatches WHERE idempotency_key=request_key;
 IF FOUND THEN
  IF d.requested_by IS DISTINCT FROM p_actor_id OR d.phone<>phone OR d.name<>btrim(p_name) THEN
   RAISE EXCEPTION 'Chave pertence a outro pedido' USING ERRCODE='PT409';
  END IF;
  RETURN jsonb_build_object('id',d.id,'created',false,'status',d.status,
   'ticket_id',d.ticket_id,'opportunity_id',d.opportunity_id,'name',d.name,
   'phone',d.phone,'template_key',d.template_key);
 END IF;
 IF NOT coalesce((SELECT settings->'enabled'='true'::jsonb
   FROM public.integration_settings WHERE key='dispatch_bridge'),false) THEN
  RAISE EXCEPTION 'Canal de disparo desativado' USING ERRCODE='42501';
 END IF;
 SELECT * INTO stage FROM public.funnel_stages WHERE id=p_stage_id AND is_active;
 IF stage.id IS NULL OR NOT EXISTS(SELECT 1 FROM public.sales_funnels
   WHERE id=stage.funnel_id AND is_active) THEN
  RAISE EXCEPTION 'Etapa inicial indisponivel' USING ERRCODE='22023';
 END IF;
 -- Mesma chave e ordem telefone -> cliente -> atendimento da recepcao WhatsApp.
 PERFORM pg_advisory_xact_lock(hashtextextended('whatsapp:phone:'||phone,0));
 SELECT count(*) INTO existing_count FROM public.customers WHERE phone_normalized=ANY(aliases);
 IF existing_count>1 THEN RAISE EXCEPTION 'Telefone ambiguo' USING ERRCODE='PT409'; END IF;
 SELECT * INTO c FROM public.customers WHERE phone_normalized=ANY(aliases) FOR UPDATE;
 IF NOT FOUND THEN
  INSERT INTO public.customers(name,phone,phone_normalized,status)
   VALUES(btrim(p_name),phone,phone,'active') RETURNING * INTO c;
 ELSIF c.status<>'active' THEN
  RAISE EXCEPTION 'Cliente inativo' USING ERRCODE='42501';
 END IF;
 SELECT * INTO t FROM public.tickets
  WHERE customer_id=c.id AND source='whatsapp' AND status NOT IN ('finalizado','cancelado')
  ORDER BY created_at DESC,id LIMIT 1 FOR UPDATE;
 IF NOT FOUND THEN
  INSERT INTO public.tickets(title,customer_id,source,status,assigned_user_id,automation_mode)
   VALUES(left('Contato iniciado por Disparos - '||c.name,120),c.id,'whatsapp','novo',p_actor_id,'human')
   RETURNING * INTO t;
 END IF;
 SELECT * INTO o FROM public.opportunities
  WHERE customer_id=c.id AND ticket_id=t.id AND status='open' AND archived_at IS NULL
  ORDER BY created_at DESC,id LIMIT 1;
 IF NOT FOUND THEN
  INSERT INTO public.opportunities(customer_id,ticket_id,title,funnel_id,stage_id,assigned_user_id)
   VALUES(c.id,t.id,left('Oportunidade WhatsApp - '||c.name,180),stage.funnel_id,stage.id,p_actor_id)
   RETURNING * INTO o;
 END IF;
 INSERT INTO public.messages(ticket_id,sender_id,sender_kind,body,channel,direction,is_internal,delivery_status)
  VALUES(t.id,p_actor_id,'human','Template aguardando reserva','whatsapp','outbound',false,'pending')
  RETURNING id INTO message_id;
 INSERT INTO public.dispatches(customer_id,ticket_id,message_id,opportunity_id,name,phone,
  status,template_key,idempotency_key,requested_by)
  VALUES(c.id,t.id,message_id,o.id,btrim(p_name),phone,'pending',
   'continuar_atendimento_vendra',request_key,p_actor_id) RETURNING * INTO d;
 INSERT INTO public.audit_log(actor_id,entity_type,entity_id,action,payload)
  VALUES(p_actor_id,'dispatch',d.id::text,'dispatch_requested',
   jsonb_build_object('ticket_id',t.id,'opportunity_id',o.id,'origin','portal','queued',false));
 RETURN jsonb_build_object('id',d.id,'created',true,'status',d.status,
  'ticket_id',t.id,'opportunity_id',o.id,'name',d.name,'phone',d.phone,'template_key',d.template_key);
END; $function$;
REVOKE ALL ON FUNCTION public.vendra_dispatch_request_v1(p_actor_id uuid, p_name text, p_phone text, p_stage_id uuid, p_request_id uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_dispatch_request_v1(p_actor_id uuid, p_name text, p_phone text, p_stage_id uuid, p_request_id uuid) TO service_role;

CREATE OR REPLACE FUNCTION public.vendra_whatsapp_ai_prepare_v1(p_ticket_id uuid, p_inbound_message_id uuid, p_body text, p_expected_version integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE t public.tickets%ROWTYPE; incoming public.messages%ROWTYPE; e public.integration_events%ROWTYPE;
 c public.customers%ROWTYPE; m public.messages%ROWTYPE; o public.whatsapp_outbox%ROWTYPE;
 control jsonb; event_key text; fingerprint text; claim_token text;
BEGIN
 IF p_body IS NULL OR length(btrim(p_body)) NOT BETWEEN 1 AND 10000 OR p_expected_version IS NULL THEN
  RAISE EXCEPTION 'Resposta IA invalida' USING ERRCODE='22023';
 END IF;
 SELECT * INTO t FROM public.tickets WHERE id=p_ticket_id FOR UPDATE;
 IF NOT FOUND OR t.source<>'whatsapp' THEN RAISE EXCEPTION 'Atendimento invalido' USING ERRCODE='22023'; END IF;
 control := public.vendra_whatsapp_control_v1(t.id);
 IF t.automation_version<>p_expected_version THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,'reason','stale_control_version');
 END IF;
 IF NOT (control->>'route_to_ai')::boolean THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,'reason','ai_or_window_disabled');
 END IF;
 SELECT * INTO incoming FROM public.messages WHERE id=p_inbound_message_id AND ticket_id=t.id
  AND direction='inbound' AND channel='whatsapp' AND NOT is_internal;
 IF NOT FOUND THEN RAISE EXCEPTION 'Mensagem de entrada divergente' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM public.messages WHERE ticket_id=t.id AND direction='inbound'
  AND channel='whatsapp' AND NOT is_internal AND created_at>incoming.created_at) THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,'reason','newer_customer_message');
 END IF;
 event_key := 'ai-reply:'||incoming.id::text;
 fingerprint := encode(sha256(convert_to(jsonb_build_array(t.id,incoming.id,btrim(p_body),p_expected_version)::text,'UTF8')),'hex');
 SELECT * INTO e FROM public.integration_events WHERE provider='ai' AND external_id=event_key;
 IF FOUND THEN
  IF e.payload_hash IS DISTINCT FROM fingerprint THEN RAISE EXCEPTION 'Outra resposta para a mesma entrada' USING ERRCODE='PT409'; END IF;
  -- Nunca devolver nova autorizacao de envio em uma repeticao.
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,'duplicate',true,
    'reason','already_prepared','outbox_id',e.entity_id);
 END IF;
 SELECT * INTO c FROM public.customers WHERE id=t.customer_id;
 IF NOT FOUND OR c.status<>'active' OR c.phone_normalized IS NULL THEN
  RAISE EXCEPTION 'Cliente/telefone invalido' USING ERRCODE='22023';
 END IF;
 INSERT INTO public.messages(ticket_id,sender_kind,body,channel,direction,is_internal,delivery_status)
  VALUES(t.id,'ai',btrim(p_body),'whatsapp','outbound',false,'claimed') RETURNING * INTO m;
 claim_token := gen_random_uuid()::text;
 INSERT INTO public.whatsapp_outbox(ticket_id,message_id,customer_id,phone,body,status,attempt_count,claimed_at,claimed_by)
  VALUES(t.id,m.id,c.id,c.phone_normalized,m.body,'claimed',1,now(),claim_token) RETURNING * INTO o;
 INSERT INTO public.integration_events(provider,external_id,event_type,status,payload_hash,payload,entity_type,entity_id,processed_at)
  VALUES('ai',event_key,'message.ai.outbound','processed',fingerprint,
   jsonb_build_object('inbound_message_id',incoming.id,'message_id',m.id,'control_version',p_expected_version),
   'whatsapp_outbox',o.id::text,now());
 RETURN jsonb_build_object('accepted',true,'authorized',true,'suppressed',false,'duplicate',false,
  'template_required',false,'outbox_id',o.id,'message_id',m.id,'outbox',
  jsonb_build_object('id',o.id,'phone',o.phone,'body',o.body,'claim_token',claim_token,
   'delivery_policy',jsonb_build_object('authorized_to_send',true,'template_required',false)));
END; $function$;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_ai_prepare_v1(p_ticket_id uuid, p_inbound_message_id uuid, p_body text, p_expected_version integer) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_ai_prepare_v1(p_ticket_id uuid, p_inbound_message_id uuid, p_body text, p_expected_version integer) TO service_role;

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
REVOKE ALL ON FUNCTION public.vendra_whatsapp_bind_v1(p_outbox_id uuid, p_provider_message_id text, p_claim_token text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_bind_v1(p_outbox_id uuid, p_provider_message_id text, p_claim_token text) TO service_role;

CREATE OR REPLACE FUNCTION public.vendra_whatsapp_control_v1(p_ticket_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE t public.tickets%ROWTYPE; enabled boolean; last_inbound timestamptz; is_open boolean;
BEGIN
 SELECT * INTO t FROM public.tickets WHERE id=p_ticket_id;
 IF NOT FOUND OR t.source<>'whatsapp' THEN RAISE EXCEPTION 'Atendimento WhatsApp nao encontrado' USING ERRCODE='22023'; END IF;
 enabled := coalesce((SELECT settings->>'ai_enabled'='true' FROM public.integration_settings WHERE key='whatsapp_bridge'),
   (SELECT settings->>'enabled'='true' FROM public.integration_settings WHERE key='ai_automation'),false);
 SELECT max(created_at) INTO last_inbound FROM public.messages
  WHERE ticket_id=t.id AND channel='whatsapp' AND direction='inbound' AND NOT is_internal;
 is_open := coalesce(last_inbound<=now() AND last_inbound>now()-interval '24 hours',false);
 RETURN jsonb_build_object('accepted',true,'ticket_id',t.id,'mode',t.automation_mode,
  'enabled',enabled,'control_version',t.automation_version,
  'connected',enabled AND t.automation_mode='ai' AND t.status NOT IN ('finalizado','cancelado'),
  'route_to_ai',enabled AND t.automation_mode='ai' AND is_open AND t.status NOT IN ('finalizado','cancelado'),
  'window_open',is_open,'expires_at',last_inbound+interval '24 hours','thread_id','VENDRA-'||t.id::text);
END; $function$;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_control_v1(p_ticket_id uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_control_v1(p_ticket_id uuid) TO service_role;

CREATE OR REPLACE FUNCTION public.vendra_whatsapp_human_prepare_v1(p_outbox_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE o public.whatsapp_outbox%ROWTYPE; t public.tickets%ROWTYPE;
 m public.messages%ROWTYPE; c public.customers%ROWTYPE; v_ticket_id uuid;
 control jsonb; token text; outgoing_phone text; customer_phone text;
BEGIN
 SELECT w.ticket_id INTO v_ticket_id FROM public.whatsapp_outbox w WHERE w.id=p_outbox_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Saida nao encontrada' USING ERRCODE='22023'; END IF;
 -- Mesma ordem do handoff: ticket, depois outbox. Concorrentes serializados.
 SELECT * INTO t FROM public.tickets WHERE id=v_ticket_id FOR UPDATE;
 SELECT * INTO o FROM public.whatsapp_outbox WHERE id=p_outbox_id FOR UPDATE;
 IF NOT FOUND OR o.ticket_id IS DISTINCT FROM t.id THEN
  RAISE EXCEPTION 'Atendimento/saida divergentes' USING ERRCODE='22023';
 END IF;
 -- Mesmo chamador nao recebe autorizacao outra vez. Resultado incerto nao e reenvio.
 IF o.status<>'pending' OR o.provider_message_id IS NOT NULL THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,
   'duplicate',true,'reason','already_reserved_or_final','outbox_id',o.id);
 END IF;
 IF t.source<>'whatsapp' OR t.status IN ('finalizado','cancelado') OR t.automation_mode<>'human' THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,
   'reason','ticket_not_human_or_open','outbox_id',o.id);
 END IF;
 control:=public.vendra_whatsapp_control_v1(t.id);
 IF NOT (control->>'window_open')::boolean THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,
   'reason','window_closed','outbox_id',o.id);
 END IF;
 SELECT * INTO m FROM public.messages WHERE id=o.message_id AND ticket_id=t.id;
 IF NOT FOUND OR m.direction<>'outbound' OR m.channel<>'whatsapp' OR m.is_internal
    OR coalesce(m.sender_kind,'')<>'human' OR m.sender_id IS NULL OR coalesce(length(btrim(m.body)),0) NOT BETWEEN 1 AND 4096
    OR m.body IS DISTINCT FROM o.body OR m.external_message_id IS NOT NULL OR m.delivery_status<>'pending' THEN
  RAISE EXCEPTION 'Mensagem humana divergente' USING ERRCODE='22023';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM public.profiles WHERE id=m.sender_id AND status='active'
    AND access_level IN ('administrativo','comercial','gerencial')) THEN
  RAISE EXCEPTION 'Autor humano ativo obrigatorio' USING ERRCODE='42501';
 END IF;
 -- Anexos exigem contrato proprio de mensagens/WAMIDs; nao liberar envio parcial.
 IF EXISTS(SELECT 1 FROM public.attachments WHERE message_id=m.id) THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,
   'reason','media_contract_required','outbox_id',o.id);
 END IF;
 SELECT * INTO c FROM public.customers WHERE id=t.customer_id;
 IF NOT FOUND OR c.status<>'active' OR c.id IS DISTINCT FROM o.customer_id
    OR c.phone_normalized IS NULL OR o.phone IS NULL THEN
  RAISE EXCEPTION 'Cliente/telefone divergentes' USING ERRCODE='22023';
 END IF;
 outgoing_phone:=regexp_replace(o.phone,'[^0-9]','','g');
 customer_phone:=regexp_replace(c.phone_normalized,'[^0-9]','','g');
 IF outgoing_phone !~ '^55[0-9]{10,11}$' OR customer_phone !~ '^55[0-9]{10,11}$' THEN
  RAISE EXCEPTION 'Telefone brasileiro invalido' USING ERRCODE='22023';
 END IF;
 IF length(outgoing_phone)=13 AND substr(outgoing_phone,5,1)='9' THEN
  outgoing_phone:=substr(outgoing_phone,1,4)||substr(outgoing_phone,6);
 END IF;
 IF length(customer_phone)=13 AND substr(customer_phone,5,1)='9' THEN
  customer_phone:=substr(customer_phone,1,4)||substr(customer_phone,6);
 END IF;
 IF outgoing_phone IS DISTINCT FROM customer_phone THEN
  RAISE EXCEPTION 'Cliente/telefone divergentes' USING ERRCODE='22023';
 END IF;
 token:=gen_random_uuid()::text;
 UPDATE public.whatsapp_outbox SET status='claimed',claimed_by=token,claimed_at=now(),
  attempt_count=coalesce(attempt_count,0)+1,updated_at=now(),last_error=NULL WHERE id=o.id;
 UPDATE public.messages SET delivery_status='claimed',external_status_updated_at=now() WHERE id=m.id;
 RETURN jsonb_build_object('accepted',true,'authorized',true,'suppressed',false,
  'duplicate',false,'outbox_id',o.id,'message_id',m.id,'outbox',
  jsonb_build_object('id',o.id,'phone',outgoing_phone,'body',o.body,'claim_token',token,
   'delivery_policy',jsonb_build_object('authorized_to_send',true,'template_required',false)));
END; $function$;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_human_prepare_v1(p_outbox_id uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_human_prepare_v1(p_outbox_id uuid) TO service_role;

CREATE OR REPLACE FUNCTION public.vendra_whatsapp_human_request_v1(p_actor_id uuid, p_ticket_id uuid, p_body text, p_request_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE t public.tickets%ROWTYPE; c public.customers%ROWTYPE; m public.messages%ROWTYPE;
 o public.whatsapp_outbox%ROWTYPE; e public.integration_events%ROWTYPE;
 event_key text; fingerprint text; phone text; control jsonb;
BEGIN
 IF p_actor_id IS NULL OR p_ticket_id IS NULL OR p_request_id IS NULL
    OR length(btrim(coalesce(p_body,''))) NOT BETWEEN 1 AND 4096 THEN
  RAISE EXCEPTION 'Comando humano invalido' USING ERRCODE='22023';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM public.profiles WHERE id=p_actor_id AND status='active'
    AND access_level IN ('administrativo','comercial','gerencial')) THEN
  RAISE EXCEPTION 'Equipe de atendimento ativa obrigatoria' USING ERRCODE='42501';
 END IF;
 event_key:='human-request:'||p_request_id::text;
 fingerprint:=encode(sha256(convert_to(jsonb_build_array(p_actor_id,p_ticket_id,btrim(p_body))::text,'UTF8')),'hex');
 -- A mesma chave nao pode criar mensagens diferentes, mesmo em tickets distintos.
 PERFORM pg_advisory_xact_lock(hashtextextended(event_key,0));
 SELECT * INTO e FROM public.integration_events WHERE provider='vendra' AND external_id=event_key;
 IF FOUND THEN
  IF e.event_type<>'message.human.requested' OR e.payload_hash IS DISTINCT FROM fingerprint THEN
   RAISE EXCEPTION 'Formulario ja utilizado com outro comando' USING ERRCODE='PT409';
  END IF;
  SELECT * INTO o FROM public.whatsapp_outbox WHERE id=e.entity_id::uuid;
  IF NOT FOUND OR o.ticket_id<>p_ticket_id THEN
   RAISE EXCEPTION 'Comando anterior indisponivel; nao repetir envio automaticamente' USING ERRCODE='PT409';
  END IF;
  SELECT * INTO m FROM public.messages WHERE id=o.message_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'Mensagem anterior indisponivel' USING ERRCODE='PT409'; END IF;
  RETURN jsonb_build_object('accepted',true,'duplicate',true,'message_id',m.id,'outbox_id',o.id,
   'status',o.status,'message',to_jsonb(m),'outbox',jsonb_build_object(
    'id',o.id,'ticket_id',o.ticket_id,'message_id',o.message_id,'status',o.status,'created_at',o.created_at));
 END IF;
 SELECT * INTO t FROM public.tickets WHERE id=p_ticket_id FOR UPDATE;
 IF NOT FOUND OR t.source<>'whatsapp' OR t.status IN ('finalizado','cancelado') THEN
  RAISE EXCEPTION 'Atendimento nao permite resposta humana' USING ERRCODE='22023';
 END IF;
 control:=public.vendra_whatsapp_control_v1(t.id);
 IF NOT (control->>'window_open')::boolean THEN
  RAISE EXCEPTION 'Janela WhatsApp encerrada; template obrigatorio' USING ERRCODE='22023';
 END IF;
 SELECT * INTO c FROM public.customers WHERE id=t.customer_id;
 IF NOT FOUND OR c.status<>'active' OR c.phone_normalized IS NULL THEN
  RAISE EXCEPTION 'Cliente ativo com telefone obrigatorio' USING ERRCODE='22023';
 END IF;
 phone:=regexp_replace(c.phone_normalized,'[^0-9]','','g');
 IF phone !~ '^55[0-9]{10,11}$' THEN RAISE EXCEPTION 'Telefone brasileiro invalido' USING ERRCODE='22023'; END IF;
 IF length(phone)=13 AND substr(phone,5,1)='9' THEN phone:=substr(phone,1,4)||substr(phone,6); END IF;
 -- Handoff, mensagem, outbox e ledger pertencem a mesma transacao.
 PERFORM public.vendra_whatsapp_mode_v1(t.id,'human',t.automation_version,p_actor_id);
 INSERT INTO public.messages(ticket_id,sender_id,sender_kind,body,channel,direction,is_internal,delivery_status)
  VALUES(t.id,p_actor_id,'human',btrim(p_body),'whatsapp','outbound',false,'pending') RETURNING * INTO m;
 INSERT INTO public.whatsapp_outbox(ticket_id,message_id,customer_id,phone,body,status)
  VALUES(t.id,m.id,c.id,phone,m.body,'pending') RETURNING * INTO o;
 UPDATE public.tickets SET updated_at=now() WHERE id=t.id;
 INSERT INTO public.integration_events(provider,external_id,event_type,status,payload_hash,payload,entity_type,entity_id,processed_at)
  VALUES('vendra',event_key,'message.human.requested','processed',fingerprint,
   jsonb_build_object('request_id',p_request_id,'ticket_id',t.id,'message_id',m.id,'actor_id',p_actor_id),
   'whatsapp_outbox',o.id::text,now());
 INSERT INTO public.audit_log(actor_id,entity_type,entity_id,action,payload)
  VALUES(p_actor_id,'ticket',t.id::text,'human_message_requested',jsonb_build_object('request_id',p_request_id,'message_id',m.id,'outbox_id',o.id));
 RETURN jsonb_build_object('accepted',true,'duplicate',false,'message_id',m.id,'outbox_id',o.id,
  'status',o.status,'message',to_jsonb(m),'outbox',jsonb_build_object(
   'id',o.id,'ticket_id',o.ticket_id,'message_id',o.message_id,'status',o.status,'created_at',o.created_at));
END; $function$;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_human_request_v1(p_actor_id uuid, p_ticket_id uuid, p_body text, p_request_id uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_human_request_v1(p_actor_id uuid, p_ticket_id uuid, p_body text, p_request_id uuid) TO service_role;

CREATE OR REPLACE FUNCTION public.vendra_whatsapp_mode_v1(p_ticket_id uuid, p_mode text, p_expected_version integer, p_actor_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE t public.tickets%ROWTYPE;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.profiles WHERE id=p_actor_id AND access_level IN ('administrativo','comercial','gerencial') AND status='active') THEN
  RAISE EXCEPTION 'Perfil ativo de atendimento obrigatorio' USING ERRCODE='42501';
 END IF;
 IF p_mode IS NULL OR p_mode NOT IN ('human','ai') OR p_expected_version IS NULL THEN
  RAISE EXCEPTION 'Controle invalido' USING ERRCODE='22023';
 END IF;
 SELECT * INTO t FROM public.tickets WHERE id=p_ticket_id FOR UPDATE;
 IF NOT FOUND OR t.source<>'whatsapp' OR t.status IN ('finalizado','cancelado') THEN
  RAISE EXCEPTION 'Atendimento nao permite alterar IA' USING ERRCODE='22023';
 END IF;
 IF t.automation_version<>p_expected_version THEN RAISE EXCEPTION 'Controle desatualizado' USING ERRCODE='PT409'; END IF;
 IF t.automation_mode<>p_mode THEN
  UPDATE public.tickets SET automation_mode=p_mode,automation_version=automation_version+1,updated_at=now(),
    ai_paused_at=CASE WHEN p_mode='human' THEN now() ELSE ai_paused_at END,
    ai_paused_by=CASE WHEN p_mode='human' THEN p_actor_id::text ELSE ai_paused_by END,
    ai_resumed_at=CASE WHEN p_mode='ai' THEN now() ELSE ai_resumed_at END,
    ai_resumed_by=CASE WHEN p_mode='ai' THEN p_actor_id::text ELSE ai_resumed_by END WHERE id=t.id;
  -- Apenas pendencias ainda nao reservadas. Claimed pode estar em voo no provedor.
  WITH cancelled AS (
   UPDATE public.whatsapp_outbox SET status='cancelled',updated_at=now()
    WHERE ticket_id=t.id AND status='pending' AND provider_message_id IS NULL AND p_mode='human'
    RETURNING message_id
  ) UPDATE public.messages SET delivery_status='cancelled',external_status_updated_at=now()
    WHERE id IN (SELECT message_id FROM cancelled);
  INSERT INTO public.audit_log(actor_id,entity_type,entity_id,action,payload)
    VALUES(p_actor_id,'ticket',t.id::text,'whatsapp_ai_mode',jsonb_build_object('mode',p_mode,'version',t.automation_version+1));
 END IF;
 RETURN public.vendra_whatsapp_control_v1(t.id);
END; $function$;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_mode_v1(p_ticket_id uuid, p_mode text, p_expected_version integer, p_actor_id uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_mode_v1(p_ticket_id uuid, p_mode text, p_expected_version integer, p_actor_id uuid) TO service_role;

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
REVOKE ALL ON FUNCTION public.vendra_whatsapp_receive_v1(p_phone text, p_name text, p_body text, p_external_message_id text, p_occurred_at timestamp with time zone) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_receive_v1(p_phone text, p_name text, p_body text, p_external_message_id text, p_occurred_at timestamp with time zone) TO service_role;

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
REVOKE ALL ON FUNCTION public.vendra_whatsapp_status_v1(p_provider_message_id text, p_status text, p_occurred_at timestamp with time zone, p_recipient_id text, p_error_message text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_status_v1(p_provider_message_id text, p_status text, p_occurred_at timestamp with time zone, p_recipient_id text, p_error_message text) TO service_role;

NOTIFY pgrst,'reload schema';

