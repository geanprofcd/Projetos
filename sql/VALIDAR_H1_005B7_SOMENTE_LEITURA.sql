-- H1-005B7 | SOMENTE VENDRA-STAGING | READ ONLY
-- Sem modificacoes, sem chamadas RPC, sem tocar nas filas.
SELECT
  (SELECT COUNT(*) FROM pg_catalog.pg_tables WHERE schemaname='public') AS tabelas_publicas,
  (SELECT COUNT(*) FROM public.staging_dispatch_simulations) AS simulacoes,
  (SELECT COUNT(*) FROM public.dispatches) AS disparos_reais,
  (SELECT COUNT(*) FROM public.whatsapp_outbox) AS outbox_real,
  (SELECT COUNT(*) FROM public.messages) AS mensagens_reais,
  (SELECT COUNT(*) FROM public.audit_log WHERE entity_type='staging_dispatch_simulation') AS auditorias_simulacao;
