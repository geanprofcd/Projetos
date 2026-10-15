-- Teste transacional descartavel: nao envia mensagens nem persiste configuracao.
-- Executar somente no VENDRA-STAGING apos a migration H1-006B.
BEGIN;
CREATE TEMP TABLE codex_control_checks(name text PRIMARY KEY, ok boolean NOT NULL CHECK(ok));
DO $test$
DECLARE c uuid; t uuid; m uuid; m2 uuid; actor uuid; r jsonb; prepared jsonb;
 token text; oid uuid; mid uuid; wamid text := 'wamid.CODEX-CONTROL-'||gen_random_uuid()::text;
BEGIN
 IF to_regclass('public.staging_transport_contracts') IS NULL THEN RAISE EXCEPTION 'Exige STAGING'; END IF;
 IF EXISTS(SELECT 1 FROM public.customers WHERE phone_normalized='551100000000') THEN
  RAISE EXCEPTION 'Telefone sintetico ja pertence a registro existente';
 END IF;
 SELECT id INTO actor FROM public.profiles WHERE access_level='administrativo' AND status='active' LIMIT 1;
 IF actor IS NULL THEN RAISE EXCEPTION 'Administrador ativo ausente'; END IF;
 INSERT INTO public.customers(name,phone,phone_normalized) VALUES('CODEX-CONTROL descartavel','551100000000','551100000000') RETURNING id INTO c;
 INSERT INTO public.tickets(title,customer_id,source) VALUES('CODEX-CONTROL descartavel',c,'whatsapp') RETURNING id INTO t;
 INSERT INTO public.messages(ticket_id,sender_kind,body,channel,direction,created_at)
  VALUES(t,'customer','Fixture sem envio','whatsapp','inbound',now()-interval '1 minute') RETURNING id INTO m;
 INSERT INTO public.integration_settings(key,settings) VALUES('whatsapp_bridge','{"ai_enabled":false}')
  ON CONFLICT(key) DO UPDATE SET settings=excluded.settings;
 r := public.vendra_whatsapp_control_v1(t);
 INSERT INTO codex_control_checks VALUES('global desligado bloqueia IA',NOT (r->>'route_to_ai')::boolean);
 BEGIN
  PERFORM public.vendra_whatsapp_mode_v1(t,'ai',1,gen_random_uuid());
  RAISE EXCEPTION 'Aceitou ator nao administrador';
 EXCEPTION WHEN SQLSTATE '42501' THEN INSERT INTO codex_control_checks VALUES('ator nao administrador recusado',true); END;
 r := public.vendra_whatsapp_mode_v1(t,'ai',1,actor);
 INSERT INTO codex_control_checks VALUES('modo persistido incrementa versao',(r->>'control_version')::int=2 AND r->>'mode'='ai');
 r := public.vendra_whatsapp_mode_v1(t,'ai',2,actor);
 INSERT INTO codex_control_checks VALUES('mesmo modo nao incrementa versao',(r->>'control_version')::int=2);
 BEGIN
  PERFORM public.vendra_whatsapp_mode_v1(t,'human',1,actor); RAISE EXCEPTION 'Aceitou versao antiga';
 EXCEPTION WHEN SQLSTATE 'PT409' THEN INSERT INTO codex_control_checks VALUES('troca com versao antiga recusada',true); END;
 -- Esta alteracao existe apenas nesta transacao, invisivel a outros processos.
 UPDATE public.integration_settings SET settings='{"ai_enabled":true}' WHERE key='whatsapp_bridge';
 r := public.vendra_whatsapp_control_v1(t);
 INSERT INTO codex_control_checks VALUES('janela recente e modo ai autorizam preparacao',(r->>'route_to_ai')::boolean);
 UPDATE public.messages SET created_at=now()-interval '25 hours' WHERE id=m;
 r := public.vendra_whatsapp_ai_prepare_v1(t,m,'Resposta descartavel',2);
 INSERT INTO codex_control_checks VALUES('janela encerrada bloqueia resposta',r->>'reason'='ai_or_window_disabled');
 UPDATE public.messages SET created_at=now()-interval '1 minute' WHERE id=m;
 BEGIN
  PERFORM public.vendra_whatsapp_ai_prepare_v1(t,gen_random_uuid(),'Resposta descartavel',2);
  RAISE EXCEPTION 'Aceitou entrada de outro atendimento';
 EXCEPTION WHEN SQLSTATE '22023' THEN INSERT INTO codex_control_checks VALUES('entrada divergente recusada',true); END;
 prepared := public.vendra_whatsapp_ai_prepare_v1(t,m,'Resposta descartavel',2);
 oid := (prepared->>'outbox_id')::uuid; mid := (prepared->>'message_id')::uuid;
 token := prepared->'outbox'->>'claim_token';
 INSERT INTO codex_control_checks VALUES('preparacao reserva uma saida',(prepared->>'authorized')::boolean AND length(token)>=32);
 r := public.vendra_whatsapp_ai_prepare_v1(t,m,'Resposta descartavel',2);
 INSERT INTO codex_control_checks VALUES('duplicata nunca reautoriza envio',(r->>'duplicate')::boolean AND NOT (r->>'authorized')::boolean AND NOT (r ? 'outbox'));
 INSERT INTO codex_control_checks VALUES('duplicata nao cria outra saida',(SELECT count(*)=1 FROM public.whatsapp_outbox WHERE ticket_id=t));
 BEGIN
  PERFORM public.vendra_whatsapp_ai_prepare_v1(t,m,'Resposta diferente',2); RAISE EXCEPTION 'Aceitou resposta conflitante';
 EXCEPTION WHEN SQLSTATE 'PT409' THEN INSERT INTO codex_control_checks VALUES('resposta conflitante recusada',true); END;
 INSERT INTO public.messages(ticket_id,sender_kind,body,channel,direction,created_at)
  VALUES(t,'customer','Entrada mais recente','whatsapp','inbound',now()) RETURNING id INTO m2;
 r := public.vendra_whatsapp_ai_prepare_v1(t,m,'Resposta descartavel',2);
 INSERT INTO codex_control_checks VALUES('entrada nova suprime resposta antiga',r->>'reason'='newer_customer_message');
 PERFORM public.vendra_whatsapp_mode_v1(t,'human',2,actor);
 r := public.vendra_whatsapp_ai_prepare_v1(t,m2,'Resposta tardia',2);
 INSERT INTO codex_control_checks VALUES('handoff impede autorizacao com versao antiga',r->>'reason'='stale_control_version');
 BEGIN
  PERFORM public.vendra_whatsapp_bind_v1(oid,wamid,repeat('x',36)); RAISE EXCEPTION 'Aceitou token incorreto';
 EXCEPTION WHEN SQLSTATE '42501' THEN INSERT INTO codex_control_checks VALUES('token incorreto recusado',true); END;
 r := public.vendra_whatsapp_status_v1(wamid,'delivered',now()-interval '20 seconds','551100000000',NULL);
 INSERT INTO codex_control_checks VALUES('delivered antes de vinculo fica pendente',(r->>'pending_match')::boolean);
 PERFORM public.vendra_whatsapp_status_v1(wamid,'read',now()-interval '10 seconds','551100000000',NULL);
 r := public.vendra_whatsapp_bind_v1(oid,wamid,token);
 INSERT INTO codex_control_checks VALUES('vinculo reconcilia delivered e read',(r->>'reconciled')::int=2 AND r->>'status'='read');
 INSERT INTO codex_control_checks VALUES('mensagem e saida consistentes',(SELECT delivery_status='read' AND external_status_updated_at=now()-interval '10 seconds' FROM public.messages WHERE id=mid));
 INSERT INTO codex_control_checks VALUES('eventos pendentes consumidos',NOT EXISTS(SELECT 1 FROM public.integration_events WHERE status='received' AND payload->>'provider_message_id'=wamid));
 r := public.vendra_whatsapp_bind_v1(oid,wamid,token);
 INSERT INTO codex_control_checks VALUES('vinculo repetido nao regride status',r->>'status'='read' AND (r->>'reconciled')::int=0);
 BEGIN
  PERFORM public.vendra_whatsapp_bind_v1(oid,wamid||'-outro',token); RAISE EXCEPTION 'Aceitou novo WAMID';
 EXCEPTION WHEN SQLSTATE 'PT409' THEN INSERT INTO codex_control_checks VALUES('troca de WAMID recusada',true); END;
 BEGIN
  INSERT INTO public.whatsapp_outbox(ticket_id,message_id,customer_id,phone,body,status,provider_message_id)
   VALUES(t,m2,c,'551100000000','Colisao descartavel','sent',wamid);
  RAISE EXCEPTION 'Indice aceitou WAMID duplicado';
 EXCEPTION WHEN unique_violation THEN INSERT INTO codex_control_checks VALUES('indice impede WAMID duplicado',true); END;
 UPDATE public.tickets SET status='finalizado' WHERE id=t;
 r := public.vendra_whatsapp_control_v1(t);
 INSERT INTO codex_control_checks VALUES('atendimento finalizado bloqueia IA',NOT (r->>'route_to_ai')::boolean);
 INSERT INTO codex_control_checks
 SELECT 'ACL restrita '||p.proname, NOT p.prosecdef AND
  NOT has_function_privilege('anon',p.oid,'execute') AND NOT has_function_privilege('authenticated',p.oid,'execute')
  AND has_function_privilege('service_role',p.oid,'execute')
 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public'
  AND p.proname IN ('vendra_whatsapp_control_v1','vendra_whatsapp_mode_v1','vendra_whatsapp_ai_prepare_v1','vendra_whatsapp_bind_v1');
END; $test$;
SELECT name,ok FROM codex_control_checks ORDER BY name;
ROLLBACK;
