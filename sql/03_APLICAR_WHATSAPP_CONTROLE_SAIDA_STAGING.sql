-- H1-006B: operacao separada somente VENDRA-STAGING; nao habilita IA ou worker.
BEGIN;
DO $guard$ BEGIN
 IF to_regclass('public.staging_transport_contracts') IS NULL OR
    to_regprocedure('public.vendra_whatsapp_status_v1(text,text,timestamptz,text,text)') IS NULL THEN
  RAISE EXCEPTION 'Exige STAGING com H1-006A';
 END IF;
END; $guard$;
CREATE UNIQUE INDEX whatsapp_outbox_wamid_unique_v1 ON public.whatsapp_outbox(provider_message_id)
 WHERE provider_message_id IS NOT NULL;

CREATE FUNCTION public.vendra_whatsapp_control_v1(p_ticket_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
DECLARE t public.tickets%ROWTYPE; enabled boolean; last_inbound timestamptz; is_open boolean;
BEGIN
 SELECT * INTO t FROM public.tickets WHERE id=p_ticket_id;
 IF NOT FOUND OR t.source<>'whatsapp' THEN RAISE EXCEPTION 'Atendimento WhatsApp nao encontrado' USING ERRCODE='22023'; END IF;
 enabled := coalesce((SELECT settings->>'ai_enabled'='true' FROM public.integration_settings WHERE key='whatsapp_bridge'),false);
 SELECT max(created_at) INTO last_inbound FROM public.messages
  WHERE ticket_id=t.id AND channel='whatsapp' AND direction='inbound' AND NOT is_internal;
 is_open := coalesce(last_inbound<=now() AND last_inbound>now()-interval '24 hours',false);
 RETURN jsonb_build_object('accepted',true,'ticket_id',t.id,'mode',t.automation_mode,
  'enabled',enabled,'control_version',t.automation_version,
  'connected',enabled AND t.automation_mode='ai' AND t.status NOT IN ('finalizado','cancelado'),
  'route_to_ai',enabled AND t.automation_mode='ai' AND is_open AND t.status NOT IN ('finalizado','cancelado'),
  'window_open',is_open,'expires_at',last_inbound+interval '24 hours','thread_id','VENDRA-'||t.id::text);
END; $fn$;

CREATE FUNCTION public.vendra_whatsapp_mode_v1(p_ticket_id uuid,p_mode text,p_expected_version integer,p_actor_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
DECLARE t public.tickets%ROWTYPE;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.profiles WHERE id=p_actor_id AND access_level='administrativo' AND status='active') THEN
  RAISE EXCEPTION 'Administrador ativo obrigatorio' USING ERRCODE='42501';
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
END; $fn$;

CREATE FUNCTION public.vendra_whatsapp_ai_prepare_v1(
 p_ticket_id uuid,p_inbound_message_id uuid,p_body text,p_expected_version integer
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
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
END; $fn$;

CREATE FUNCTION public.vendra_whatsapp_bind_v1(p_outbox_id uuid,p_provider_message_id text,p_claim_token text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
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
END; $fn$;

REVOKE ALL ON FUNCTION public.vendra_whatsapp_control_v1(uuid) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_mode_v1(uuid,text,integer,uuid) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_ai_prepare_v1(uuid,uuid,text,integer) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_bind_v1(uuid,text,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_control_v1(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_mode_v1(uuid,text,integer,uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_ai_prepare_v1(uuid,uuid,text,integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_bind_v1(uuid,text,text) TO service_role;
COMMIT;
