-- Rodar em BEGIN/ROLLBACK com as definicoes SQL28. Sem envio externo.
DO $test$
DECLARE v_actor uuid; v_customer uuid; v_ticket uuid; v_opportunity uuid; v_funnel uuid;
 v_lead uuid; v_qualified uuid; v_proposal uuid; v_message uuid; v_result jsonb;
 v_control jsonb; v_prepared jsonb; v_outbox uuid; v_token text;
 v_phone text:='551176543216'; v_instant timestamptz:=now();
BEGIN
 SELECT id INTO v_actor FROM public.profiles WHERE status='active' AND access_level='comercial' LIMIT 1;
 IF v_actor IS NULL THEN RAISE EXCEPTION 'Conta Comercial necessaria'; END IF;
 IF EXISTS(SELECT 1 FROM public.customers WHERE phone_normalized=v_phone) THEN RAISE EXCEPTION 'Fixture ocupada'; END IF;
 SELECT id INTO v_funnel FROM public.sales_funnels WHERE name='Funil Comercial';
 SELECT id INTO v_lead FROM public.funnel_stages WHERE funnel_id=v_funnel AND lower(name)='novo lead';
 SELECT id INTO v_qualified FROM public.funnel_stages WHERE funnel_id=v_funnel AND name='Qualificação';
 SELECT id INTO v_proposal FROM public.funnel_stages WHERE funnel_id=v_funnel AND name='Proposta';
 INSERT INTO public.integration_settings(key,settings) VALUES('ai_automation','{"enabled":true,"default_mode":"ai"}')
 ON CONFLICT(key) DO UPDATE SET settings=excluded.settings;
 INSERT INTO public.customers(name,phone,phone_normalized,status) VALUES('CODEX-ETAPA',v_phone,v_phone,'active') RETURNING id INTO v_customer;
 INSERT INTO public.tickets(title,customer_id,source,status,automation_mode,ai_paused_by,ai_paused_at)
 VALUES('CODEX-ETAPA',v_customer,'whatsapp','novo','human',v_actor::text,now()-interval '2 hours') RETURNING id INTO v_ticket;
 INSERT INTO public.opportunities(customer_id,ticket_id,title,funnel_id,stage_id,status)
 VALUES(v_customer,v_ticket,'CODEX-ETAPA',v_funnel,v_lead,'open') RETURNING id INTO v_opportunity;
 -- Historico de resposta e pausa antigos NAO impedem um novo ciclo de disparo.
 INSERT INTO public.messages(ticket_id,body,sender_kind,channel,direction,is_internal,delivery_status,created_at)
 VALUES(v_ticket,'Resposta historica','customer','whatsapp','inbound',false,'received',now()-interval '3 hours');
 INSERT INTO public.messages(ticket_id,body,sender_kind,channel,direction,is_internal,delivery_status,created_at)
 VALUES(v_ticket,'Template inicial','human','whatsapp','outbound',false,'sent',now()-interval '1 hour') RETURNING id INTO v_message;
 INSERT INTO public.dispatches(customer_id,ticket_id,message_id,opportunity_id,name,phone,status,template_key,idempotency_key,requested_by,provider_message_id,created_at)
 VALUES(v_customer,v_ticket,v_message,v_opportunity,'CODEX-ETAPA',v_phone,'sent','continuar_atendimento_vendra',gen_random_uuid()::text,v_actor,'CODEX-INITIAL',now()-interval '1 hour');
 v_result:=public.vendra_whatsapp_receive_v1(v_phone,'CODEX-ETAPA','Resposta do novo ciclo','CODEX-ETAPA-1',v_instant);
 IF NOT EXISTS(SELECT 1 FROM public.opportunities WHERE id=v_opportunity AND stage_id=v_qualified) THEN RAISE EXCEPTION 'Historico bloqueou Novo Lead -> Qualificacao'; END IF;
 v_control:=public.vendra_whatsapp_control_v1(v_ticket);
 IF v_control->>'route_to_ai'<>'true' THEN RAISE EXCEPTION 'Pausa antiga bloqueou IA apos novo disparo'; END IF;
 -- Calendly enviado em Qualificacao avanca no aceite sent, sem esperar delivered/read.
 v_prepared:=public.vendra_whatsapp_ai_prepare_v1(v_ticket,(v_result->>'message_id')::uuid,'Agende https://calendly.com/codex/teste',(v_control->>'control_version')::integer);
 IF v_prepared->>'authorized'<>'true' THEN RAISE EXCEPTION 'Reserva IA bloqueada'; END IF;
 v_outbox:=(v_prepared->'outbox'->>'id')::uuid;v_token:=v_prepared->'outbox'->>'claim_token';
 IF NOT EXISTS(SELECT 1 FROM public.opportunities WHERE id=v_opportunity AND stage_id=v_qualified) THEN RAISE EXCEPTION 'Avancou antes de enviar'; END IF;
 PERFORM public.vendra_whatsapp_bind_v1(v_outbox,'CODEX-ETAPA-CALENDLY',v_token);
 IF NOT EXISTS(SELECT 1 FROM public.opportunities WHERE id=v_opportunity AND stage_id=v_proposal) THEN RAISE EXCEPTION 'Envio Calendly nao avancou Qualificacao -> Proposta'; END IF;
 IF public.vendra_whatsapp_control_v1(v_ticket)->>'mode'<>'ai' THEN RAISE EXCEPTION 'Calendly desligou IA'; END IF;
 UPDATE public.opportunities SET stage_id=v_lead WHERE id=v_opportunity;
 PERFORM public.vendra_whatsapp_bind_v1(v_outbox,'CODEX-ETAPA-CALENDLY',v_token);
 PERFORM public.vendra_whatsapp_status_v1('CODEX-ETAPA-CALENDLY','delivered',now(),v_phone,NULL);
 IF NOT EXISTS(SELECT 1 FROM public.opportunities WHERE id=v_opportunity AND stage_id=v_lead) THEN RAISE EXCEPTION 'Replay ou delivered sobrescreveu movimento manual'; END IF;
 IF public.vendra_commercial_stage_v1(v_ticket,'proposal','test')->>'applied'<>'false' THEN RAISE EXCEPTION 'Pulou Novo Lead direto para Proposta'; END IF;
 -- Botao Comercial desliga; novas respostas nao religam uma pausa atual.
 v_control:=public.vendra_whatsapp_control_v1(v_ticket);
 PERFORM public.vendra_whatsapp_mode_v1(v_ticket,'human',(v_control->>'control_version')::integer,v_actor);
 v_result:=public.vendra_whatsapp_receive_v1(v_phone,'CODEX-ETAPA','Resposta apos botao','CODEX-ETAPA-2',v_instant);
 IF NOT EXISTS(SELECT 1 FROM public.opportunities WHERE id=v_opportunity AND stage_id=v_qualified) THEN RAISE EXCEPTION 'Nova resposta em Novo Lead nao qualificou'; END IF;
 IF public.vendra_whatsapp_control_v1(v_ticket)->>'mode'<>'human' THEN RAISE EXCEPTION 'Pausa do botao foi sobrescrita'; END IF;
 IF public.vendra_whatsapp_receive_v1(v_phone,'CODEX-ETAPA','Resposta apos botao','CODEX-ETAPA-2',v_instant)->>'duplicate'<>'true' THEN RAISE EXCEPTION 'Replay perdeu idempotencia'; END IF;
 PERFORM public.vendra_whatsapp_receive_v1(v_phone,'CODEX-ETAPA','Outra resposta qualificada','CODEX-ETAPA-3',v_instant);
 IF NOT EXISTS(SELECT 1 FROM public.opportunities WHERE id=v_opportunity AND stage_id=v_qualified) THEN RAISE EXCEPTION 'Recepcao em Qualificacao moveu indevidamente'; END IF;
 IF has_function_privilege('anon','public.vendra_whatsapp_receive_v1(text,text,text,text,timestamp with time zone)','EXECUTE') THEN RAISE EXCEPTION 'ACL ampliada'; END IF;
END $test$;
