-- H1-006F: operacao separada, SOMENTE VENDRA-STAGING.
-- Nao habilita flag, worker, IA, webhook ou envio. Preserva tabelas/RLS e RPCs anteriores.
BEGIN;
DO $guard$ BEGIN
 IF to_regclass('public.staging_transport_contracts') IS NULL OR
    to_regprocedure('public.vendra_whatsapp_bind_v1(uuid,text,text)') IS NULL THEN
  RAISE EXCEPTION 'Exige STAGING com H1-006B';
 END IF;
END; $guard$;

CREATE FUNCTION public.vendra_dispatch_prepare_v1(p_dispatch_id uuid,p_phone text,p_name text,p_template_key text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
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
               AND access_level IN ('administrativo','comercial')) THEN
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
END; $fn$;

CREATE FUNCTION public.vendra_dispatch_bind_v1(p_dispatch_id uuid,p_outbox_id uuid,p_provider_message_id text,p_claim_token text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
DECLARE d public.dispatches%ROWTYPE; o public.whatsapp_outbox%ROWTYPE; result jsonb;
BEGIN
 SELECT * INTO d FROM public.dispatches WHERE id=p_dispatch_id;
 SELECT * INTO o FROM public.whatsapp_outbox WHERE id=p_outbox_id;
 IF d.id IS NULL OR o.id IS NULL OR d.message_id<>o.message_id OR d.ticket_id<>o.ticket_id OR d.customer_id<>o.customer_id THEN
  RAISE EXCEPTION 'Reserva nao pertence ao disparo' USING ERRCODE='42501';
 END IF;
 -- Ordem WAMID -> outbox -> mensagem -> dispatch, igual ao wrapper de status.
 result:=public.vendra_whatsapp_bind_v1(p_outbox_id,p_provider_message_id,p_claim_token);
 UPDATE public.dispatches SET provider_message_id=p_provider_message_id,status=result->>'status',updated_at=now()
  WHERE id=d.id AND (provider_message_id IS NULL OR provider_message_id=p_provider_message_id);
 IF NOT FOUND THEN RAISE EXCEPTION 'Disparo ja tem outro WAMID' USING ERRCODE='PT409'; END IF;
 RETURN result||jsonb_build_object('dispatch_id',d.id);
END; $fn$;

CREATE FUNCTION public.vendra_dispatch_provider_status_v1(p_provider_message_id text,p_status text,
 p_occurred_at timestamptz,p_recipient_id text,p_error_message text DEFAULT NULL)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
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
END; $fn$;

REVOKE ALL ON FUNCTION public.vendra_dispatch_prepare_v1(uuid,text,text,text) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.vendra_dispatch_bind_v1(uuid,uuid,text,text) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.vendra_dispatch_provider_status_v1(text,text,timestamptz,text,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_dispatch_prepare_v1(uuid,text,text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.vendra_dispatch_bind_v1(uuid,uuid,text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.vendra_dispatch_provider_status_v1(text,text,timestamptz,text,text) TO service_role;
COMMIT;
