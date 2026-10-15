-- H1-006H: revisar/aplicar SOMENTE VENDRA-STAGING. Nao habilita envio ou flags.
-- Cria comando atomico do portal: cliente/atendimento/CRM/mensagem/disparo.
BEGIN;
DO $guard$ BEGIN
 IF to_regclass('public.staging_transport_contracts') IS NULL OR
    to_regprocedure('public.vendra_dispatch_prepare_v1(uuid,text,text,text)') IS NULL THEN
  RAISE EXCEPTION 'Exige STAGING com H1-006F';
 END IF;
END; $guard$;

CREATE FUNCTION public.vendra_dispatch_request_v1(
 p_actor_id uuid,p_name text,p_phone text,p_stage_id uuid,p_request_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
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
END; $fn$;
REVOKE ALL ON FUNCTION public.vendra_dispatch_request_v1(uuid,text,text,uuid,uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_dispatch_request_v1(uuid,text,text,uuid,uuid) TO service_role;
-- Alinha a reserva ao perfil Gerencial, que ja possui o modulo Disparos.
CREATE OR REPLACE FUNCTION public.vendra_dispatch_prepare_v1(p_dispatch_id uuid,p_phone text,p_name text,p_template_key text)
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
END; $fn$;
COMMIT;

