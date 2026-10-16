-- PREPARADO, NAO EXECUTADO. Somente mesmo STAGING; nao altera evidencias/dados.
BEGIN;
DO $guard$ BEGIN
 IF to_regclass('public.staging_transport_contracts') IS NULL THEN
  RAISE EXCEPTION 'Exige VENDRA-STAGING; nao aplicar no principal';
 END IF;
END; $guard$;
DROP FUNCTION IF EXISTS public.vendra_whatsapp_human_prepare_v1(uuid);
COMMIT;
