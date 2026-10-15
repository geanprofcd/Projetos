-- Somente leitura. Execute no projeto VENDRA-STAGING.
SELECT
  to_regclass('public.staging_dispatch_simulations') IS NOT NULL AS tabela_isolada,
  to_regprocedure('public.vendra_staging_prepare_dispatch(uuid,text,uuid)') IS NOT NULL AS rpc_preparar,
  to_regprocedure('public.vendra_staging_change_dispatch_simulation(uuid,text,integer,uuid)') IS NOT NULL AS rpc_estados,
  has_function_privilege('anon','public.vendra_staging_prepare_dispatch(uuid,text,uuid)','EXECUTE') AS anon_pode_preparar,
  has_function_privilege('authenticated','public.vendra_staging_prepare_dispatch(uuid,text,uuid)','EXECUTE') AS usuario_pode_preparar,
  has_function_privilege('service_role','public.vendra_staging_prepare_dispatch(uuid,text,uuid)','EXECUTE') AS backend_pode_preparar;
SELECT
 (SELECT count(*) FROM public.staging_dispatch_simulations) AS simulacoes,
 (SELECT count(*) FROM public.audit_log WHERE entity_type='staging_dispatch_simulation') AS eventos_auditoria,
 (SELECT count(*) FROM public.dispatches) AS disparos_reais,
 (SELECT count(*) FROM public.whatsapp_outbox) AS outbox_real,
 (SELECT count(*) FROM public.messages) AS mensagens_reais;
