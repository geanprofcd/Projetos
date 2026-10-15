-- H1-005B9 | APENAS SELECT. Usar SOMENTE no projeto VENDRA-STAGING.
-- Zero insert, update, delete, alter, create ou disparos.
SELECT
 (SELECT count(*) FROM public.staging_transport_contracts) AS contratos_homologacao,
 (SELECT count(*) FROM public.staging_transport_events) AS eventos_homologacao,
 (SELECT count(*) FROM public.staging_transport_contracts WHERE state='leased' AND lease_until <= now()) AS leases_expirados,
 (SELECT count(*) FROM public.staging_transport_contracts WHERE state='dead_letter') AS dead_letter,
 (SELECT count(*) FROM public.staging_transport_contracts WHERE transport_enabled) AS transporte_habilitado,
 (SELECT count(*) FROM public.dispatches) AS disparos_reais,
 (SELECT count(*) FROM public.whatsapp_outbox) AS whatsapp_outbox,
 (SELECT count(*) FROM public.messages) AS mensagens_reais;
SELECT c.relname AS tabela,c.relrowsecurity AS rls_ativo,
 has_table_privilege('anon', c.oid, 'SELECT') AS anon_leitura,
 has_table_privilege('authenticated', c.oid, 'SELECT') AS usuario_leitura
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname IN ('staging_transport_contracts','staging_transport_events')
ORDER BY c.relname;
SELECT p.proname AS funcao,
 has_function_privilege('anon',p.oid,'EXECUTE') AS anon_exec,
 has_function_privilege('authenticated',p.oid,'EXECUTE') AS usuario_exec,
 has_function_privilege('service_role',p.oid,'EXECUTE') AS backend_exec
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='public' AND p.proname IN ('vendra_staging_h1_005b8_prepare','vendra_staging_h1_005b8_transition')
ORDER BY p.proname;
