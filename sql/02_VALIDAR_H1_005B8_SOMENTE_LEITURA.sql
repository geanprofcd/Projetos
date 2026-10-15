-- READ-ONLY | SOMENTE PROJETO VENDRA-STAGING | H1-005B8
-- Rode apos a migration e apos os testes de homologacao.
SELECT
 (SELECT count(*) FROM public.staging_transport_contracts) AS contratos,
 (SELECT count(*) FROM public.staging_transport_events) AS eventos,
 (SELECT count(*) FROM public.staging_transport_contracts WHERE state='dead_letter') AS dead_letter,
 (SELECT count(*) FROM public.staging_transport_contracts WHERE transport_enabled=true) AS transporte_autorizado,
 (SELECT count(*) FROM public.dispatches) AS disparos_reais,
 (SELECT count(*) FROM public.whatsapp_outbox) AS fila_real,
 (SELECT count(*) FROM public.messages) AS mensagens_reais,
 (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
    WHERE n.nspname='public' AND p.proname IN ('vendra_staging_h1_005b8_prepare','vendra_staging_h1_005b8_transition')) AS rpcs_presentes;

-- Visibilidade das protecoes RLS e privilegios (esperado: ambas true e anon sem grants):
SELECT c.relname,c.relrowsecurity AS rls_ativo,
 has_table_privilege('anon',c.oid,'SELECT') AS anon_pode_ler,
 has_table_privilege('authenticated',c.oid,'SELECT') AS usuario_pode_ler
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname IN ('staging_transport_contracts','staging_transport_events');
