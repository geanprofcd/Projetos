-- APLICADO 16/10/2026 somente VENDRA-STAGING, autorizacao especifica recebida.
-- Migration: vendra_whatsapp_human_command_v1. Nao reaplicar automaticamente.
-- Uma funcao; usa tabelas existentes. Nao ativa wake/worker nem envia.
BEGIN;
DO $guard$ BEGIN
 IF to_regclass('public.staging_transport_contracts') IS NULL OR
    to_regprocedure('public.vendra_whatsapp_human_prepare_v1(uuid)') IS NULL THEN
  RAISE EXCEPTION 'Exige VENDRA-STAGING com reserva humana; nao aplicar no principal';
 END IF;
 IF to_regprocedure('public.vendra_whatsapp_human_request_v1(uuid,uuid,text,uuid)') IS NOT NULL THEN
  RAISE EXCEPTION 'Comando humano ja existe; revisar antes de reaplicar';
 END IF;
END; $guard$;
CREATE FUNCTION public.vendra_whatsapp_human_request_v1(
 p_actor_id uuid,p_ticket_id uuid,p_body text,p_request_id uuid
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
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
END; $fn$;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_human_request_v1(uuid,uuid,text,uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_human_request_v1(uuid,uuid,text,uuid) TO service_role;
COMMIT;
