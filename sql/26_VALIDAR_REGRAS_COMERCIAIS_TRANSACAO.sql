-- Executar dentro de BEGIN/ROLLBACK, apos as definicoes SQL26. Nao envia mensagens.
DO $test$
DECLARE actor uuid; c uuid; t uuid; f uuid; lead uuid; qualified uuid; proposal uuid;
 inbound jsonb; control jsonb; prepared jsonb; output_id uuid; token text; version integer;
 v_test_phone text:='551176543219'; instant timestamptz:=now(); ordered uuid[]; newer uuid;
BEGIN
 SELECT id INTO actor FROM public.profiles WHERE status='active' AND access_level='comercial' LIMIT 1;
 IF actor IS NULL THEN RAISE EXCEPTION 'Conta comercial de homologacao obrigatoria'; END IF;
 IF EXISTS(SELECT 1 FROM public.customers WHERE phone_normalized=v_test_phone) THEN RAISE EXCEPTION 'Telefone de fixture ocupado'; END IF;
 SELECT id INTO f FROM public.sales_funnels WHERE name='Funil Comercial';
 SELECT id INTO lead FROM public.funnel_stages WHERE funnel_id=f AND lower(name)='novo lead';
 SELECT id INTO qualified FROM public.funnel_stages WHERE funnel_id=f AND name='Qualificação';
 SELECT id INTO proposal FROM public.funnel_stages WHERE funnel_id=f AND name='Proposta';
 IF lead IS NULL OR qualified IS NULL OR proposal IS NULL THEN RAISE EXCEPTION 'Etapas incompletas'; END IF;
 INSERT INTO public.integration_settings(key,settings) VALUES('ai_automation','{"enabled":true,"default_mode":"ai"}')
  ON CONFLICT(key) DO UPDATE SET settings=excluded.settings;
 INSERT INTO public.customers(name,phone,phone_normalized,status) VALUES('CODEX-REGRAS',v_test_phone,v_test_phone,'active') RETURNING id INTO c;
 INSERT INTO public.tickets(title,customer_id,source,status,automation_mode) VALUES('CODEX-REGRAS',c,'whatsapp','novo','human') RETURNING id INTO t;
 INSERT INTO public.opportunities(customer_id,ticket_id,title,funnel_id,stage_id,status) VALUES(c,t,'CODEX-REGRAS',f,lead,'open');
 inbound:=public.vendra_whatsapp_receive_v1(v_test_phone,'CODEX-REGRAS','Primeira resposta','CODEX-FIRST-REPLY',instant);
 control:=public.vendra_whatsapp_control_v1(t);
 IF control->>'route_to_ai'<>'true' THEN RAISE EXCEPTION 'Primeira resposta nao ligou IA antes do controle'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.opportunities WHERE ticket_id=t AND stage_id=qualified) THEN RAISE EXCEPTION 'Primeira resposta nao qualificou'; END IF;
 PERFORM public.vendra_whatsapp_mode_v1(t,'human',(control->>'control_version')::integer,actor);
 PERFORM public.vendra_whatsapp_receive_v1(v_test_phone,'CODEX-REGRAS','Segunda resposta','CODEX-SECOND-REPLY',instant);
 IF public.vendra_whatsapp_control_v1(t)->>'route_to_ai'<>'false' THEN RAISE EXCEPTION 'Pausa comercial sobrescrita'; END IF;
 IF public.vendra_whatsapp_receive_v1(v_test_phone,'CODEX-REGRAS','Primeira resposta','CODEX-FIRST-REPLY',instant)->>'duplicate'<>'true' THEN RAISE EXCEPTION 'Replay duplicado'; END IF;
 IF public.vendra_whatsapp_control_v1(t)->>'mode'<>'human' THEN RAISE EXCEPTION 'Replay religou IA'; END IF;
 SELECT automation_version INTO version FROM public.tickets WHERE id=t;
 PERFORM public.vendra_whatsapp_mode_v1(t,'ai',version,actor);
 SELECT automation_version INTO version FROM public.tickets WHERE id=t;
 prepared:=public.vendra_whatsapp_ai_prepare_v1(t,(inbound->>'message_id')::uuid,'Agende https://calendly.com/codex/teste',version);
 IF prepared->>'authorized'<>'true' THEN RAISE EXCEPTION 'Reserva IA nao autorizada'; END IF;
 output_id:=(prepared->'outbox'->>'id')::uuid;token:=prepared->'outbox'->>'claim_token';
 IF NOT EXISTS(SELECT 1 FROM public.opportunities WHERE ticket_id=t AND stage_id=qualified) THEN RAISE EXCEPTION 'Avancou antes do aceite do provedor'; END IF;
 PERFORM public.vendra_whatsapp_bind_v1(output_id,'CODEX-SYNTHETIC-CALENDLY',token);
 IF NOT EXISTS(SELECT 1 FROM public.opportunities WHERE ticket_id=t AND stage_id=qualified) THEN RAISE EXCEPTION 'Avancou sem entrega Meta'; END IF;
 PERFORM public.vendra_whatsapp_status_v1('CODEX-SYNTHETIC-CALENDLY','delivered',now(),v_test_phone,NULL);
 IF NOT EXISTS(SELECT 1 FROM public.opportunities WHERE ticket_id=t AND stage_id=proposal) THEN RAISE EXCEPTION 'Calendly nao avancou para Proposta'; END IF;
 UPDATE public.opportunities SET stage_id=qualified WHERE ticket_id=t;
 PERFORM public.vendra_whatsapp_bind_v1(output_id,'CODEX-SYNTHETIC-CALENDLY',token);
 IF NOT EXISTS(SELECT 1 FROM public.opportunities WHERE ticket_id=t AND stage_id=qualified) THEN RAISE EXCEPTION 'Replay sobrescreveu movimento manual'; END IF;
 PERFORM public.vendra_whatsapp_status_v1('CODEX-SYNTHETIC-CALENDLY','read',now(),v_test_phone,NULL);
 IF NOT EXISTS(SELECT 1 FROM public.opportunities WHERE ticket_id=t AND stage_id=qualified) THEN RAISE EXCEPTION 'Leitura repetiu avancamento apos entrega'; END IF;
 -- Nova saida confirmada pode avancar novamente; apenas repetir o callback nao pode.
 UPDATE public.messages SET created_at=now()-interval '2 minutes' WHERE ticket_id=t;
 INSERT INTO public.tickets(title,customer_id,source,status,automation_mode) VALUES('CODEX-RECENTE',c,'interno','novo','human') RETURNING id INTO newer;
 INSERT INTO public.messages(ticket_id,body,channel,direction,is_internal,delivery_status,created_at)
  VALUES(newer,'Saida mais recente','internal','outbound',false,'sent',now()-interval '1 minute');
 INSERT INTO public.messages(ticket_id,body,channel,direction,is_internal,delivery_status,created_at)
  VALUES(t,'Entrada prioritaria','whatsapp','inbound',false,'received',now()-interval '90 seconds');
 SELECT array_agg(id) INTO ordered FROM public.vendra_ticket_activity_list_v1(ARRAY[c],10);
 IF ordered[1]<>t OR ordered[2]<>newer THEN RAISE EXCEPTION 'Prioridade recebida/recencia incorreta'; END IF;
 IF has_function_privilege('anon','public.vendra_commercial_stage_v1(uuid,text,text)','EXECUTE') OR
    has_function_privilege('authenticated','public.vendra_ticket_activity_list_v1(uuid[],integer)','EXECUTE') THEN RAISE EXCEPTION 'RPC publica'; END IF;
END $test$;
