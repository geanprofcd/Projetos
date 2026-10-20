-- Homologacao STAGING. Todas as fixtures sao revertidas na mesma transacao.
BEGIN;
DO $test$
DECLARE c uuid; f uuid; s uuid; ta uuid; tb uuid; tc uuid;
 a uuid; b uuid; z uuid; result jsonb; column_data jsonb;
BEGIN
 SELECT id INTO c FROM public.customers WHERE name='CODEX-ROLAGEM' LIMIT 1;
 SELECT id INTO f FROM public.sales_funnels WHERE id IN
  (SELECT funnel_id FROM public.opportunities WHERE customer_id=c) LIMIT 1;
 SELECT id INTO s FROM public.funnel_stages WHERE funnel_id=f AND name='Novo Lead' LIMIT 1;
 IF c IS NULL OR f IS NULL OR s IS NULL THEN RAISE EXCEPTION 'Fixture isolada ausente'; END IF;
 INSERT INTO public.tickets(customer_id,title,source) VALUES(c,'CODEX-WINDOW-A','whatsapp') RETURNING id INTO ta;
 INSERT INTO public.tickets(customer_id,title,source) VALUES(c,'CODEX-WINDOW-B','whatsapp') RETURNING id INTO tb;
 INSERT INTO public.tickets(customer_id,title,source) VALUES(c,'CODEX-WINDOW-C','whatsapp') RETURNING id INTO tc;
 INSERT INTO public.opportunities(customer_id,ticket_id,title,funnel_id,stage_id,calculated_value)
  VALUES(c,ta,'CODEX-WINDOW-ORDER A',f,s,1) RETURNING id INTO a;
 INSERT INTO public.opportunities(customer_id,ticket_id,title,funnel_id,stage_id,calculated_value)
  VALUES(c,tb,'CODEX-WINDOW-ORDER B',f,s,2) RETURNING id INTO b;
 INSERT INTO public.opportunities(customer_id,ticket_id,title,funnel_id,stage_id,calculated_value)
  VALUES(c,tc,'CODEX-WINDOW-ORDER C',f,s,3) RETURNING id INTO z;
 INSERT INTO public.messages(ticket_id,body,direction,channel,created_at,delivery_status) VALUES
  (ta,'Recebida antiga','inbound','whatsapp',now()-interval '2 hours',NULL),
  (ta,'Reserva ainda nao enviada','outbound','whatsapp',now()-interval '1 minute','claimed'),
  (tb,'Resposta enviada','outbound','whatsapp',now()-interval '1 minute','sent'),
  (tc,'Recebida mais recente','inbound','whatsapp',now()-interval '40 minutes',NULL),
  (tc,'Nota interna','outbound','internal',now(),NULL);
 UPDATE public.messages SET is_internal=true WHERE ticket_id=tc AND channel='internal';
 result:=public.vendra_kanban_window_v1(f,'CODEX-WINDOW-ORDER',NULL,'{}',1);
 SELECT value INTO column_data FROM jsonb_array_elements(result) WHERE value->>'stage_id'=s::text;
 IF (column_data->>'count')::int<>3 OR (column_data->>'total')::numeric<>6
  OR column_data->'cards'->0->>'id'<>z::text OR jsonb_array_length(column_data->'cards')<>1
 THEN RAISE EXCEPTION 'Totais, limite ou prioridade recebida incorretos'; END IF;
 result:=public.vendra_kanban_window_v1(f,'CODEX-WINDOW-ORDER',NULL,jsonb_build_object(s,1),1);
 SELECT value INTO column_data FROM jsonb_array_elements(result) WHERE value->>'stage_id'=s::text;
 IF column_data->'cards'->0->>'id'<>a::text OR column_data->'cards'->0->>'last_direction'<>'inbound'
 THEN RAISE EXCEPTION 'Reserva nao enviada removeu prioridade de recebida'; END IF;
 result:=public.vendra_kanban_window_v1(f,'CODEX-WINDOW-ORDER',NULL,jsonb_build_object(s,2),999999);
 SELECT value INTO column_data FROM jsonb_array_elements(result) WHERE value->>'stage_id'=s::text;
 IF column_data->'cards'->0->>'id'<>b::text THEN RAISE EXCEPTION 'Pagina final incorreta'; END IF;
 IF has_function_privilege('anon','public.vendra_kanban_window_v1(uuid,text,uuid,jsonb,integer)','EXECUTE')
  OR has_function_privilege('authenticated','public.vendra_kanban_window_v1(uuid,text,uuid,jsonb,integer)','EXECUTE')
 THEN RAISE EXCEPTION 'RPC exposta'; END IF;
END;
$test$;
ROLLBACK;
