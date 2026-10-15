-- VENDRA H1-005B9 | SOMENTE LEITURA | Executar no Supabase VENDRA-STAGING.
SELECT
  (pg_get_functiondef('public.vendra_staging_move_opportunity(uuid,uuid,integer,uuid)'::regprocedure)
   LIKE '%ERRCODE=''PT409''%') AS crm_pt409,
  (pg_get_functiondef('public.vendra_staging_move_opportunity(uuid,uuid,integer,uuid)'::regprocedure)
   LIKE '%ERRCODE=''40001''%') AS crm_40001_antigo,
  (pg_get_functiondef('public.vendra_staging_change_dispatch_simulation(uuid,text,integer,uuid)'::regprocedure)
   LIKE '%ERRCODE=''PT409''%') AS simulacoes_pt409,
  (pg_get_functiondef('public.vendra_staging_change_dispatch_simulation(uuid,text,integer,uuid)'::regprocedure)
   LIKE '%ERRCODE=''40001''%') AS simulacoes_40001_antigo,
  (SELECT count(*) FROM public.dispatches) AS disparos_reais,
  (SELECT count(*) FROM public.whatsapp_outbox) AS fila_real,
  (SELECT count(*) FROM public.messages) AS mensagens_reais,
  (SELECT count(*) FROM public.staging_transport_contracts WHERE transport_enabled) AS transporte_habilitado,
  (SELECT count(*) FROM public.staging_transport_contracts) AS contratos,
  (SELECT count(*) FROM public.staging_transport_events) AS eventos;
