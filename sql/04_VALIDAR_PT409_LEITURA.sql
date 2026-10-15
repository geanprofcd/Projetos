-- VENDRA H1-005B9 | VALIDACAO PT409 | SOMENTE LEITURA
SELECT
  pg_get_functiondef('public.vendra_staging_h1_005b8_transition(uuid,text,integer,uuid)'::regprocedure)
     LIKE '%ERRCODE=''PT409''%' AS conflito_pt409_instalado,
  pg_get_functiondef('public.vendra_staging_h1_005b8_transition(uuid,text,integer,uuid)'::regprocedure)
     LIKE '%ERRCODE=''40001''%' AS conflito_40001_antigo,
  (SELECT count(*) FROM public.staging_transport_contracts WHERE transport_enabled) AS transporte_habilitado,
  (SELECT count(*) FROM public.dispatches) AS disparos_reais,
  (SELECT count(*) FROM public.whatsapp_outbox) AS outbox_real,
  (SELECT count(*) FROM public.messages) AS mensagens_reais,
  (SELECT count(*) FROM public.staging_transport_events) AS eventos;
