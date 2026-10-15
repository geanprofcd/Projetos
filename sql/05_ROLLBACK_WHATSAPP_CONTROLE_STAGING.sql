-- Operacao manual separada: reverte somente H1-006B; preserva dados e H1-006A.
-- Desligar consumidores H1-006B antes de executar. Nao executar no principal.
BEGIN;
DO $guard$ BEGIN
 IF to_regclass('public.staging_transport_contracts') IS NULL THEN RAISE EXCEPTION 'Exige STAGING'; END IF;
END; $guard$;
DROP FUNCTION IF EXISTS public.vendra_whatsapp_bind_v1(uuid,text,text);
DROP FUNCTION IF EXISTS public.vendra_whatsapp_ai_prepare_v1(uuid,uuid,text,integer);
DROP FUNCTION IF EXISTS public.vendra_whatsapp_mode_v1(uuid,text,integer,uuid);
DROP FUNCTION IF EXISTS public.vendra_whatsapp_control_v1(uuid);
DROP INDEX IF EXISTS public.whatsapp_outbox_wamid_unique_v1;
COMMIT;
