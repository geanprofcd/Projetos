-- PREPARADO, NAO EXECUTADO. Somente STAGING; preserva mensagens/evidencias.
BEGIN;
DO $guard$ BEGIN
 IF to_regclass('public.staging_transport_contracts') IS NULL THEN
  RAISE EXCEPTION 'Exige VENDRA-STAGING; nao aplicar no principal';
 END IF;
END; $guard$;
DROP FUNCTION IF EXISTS public.vendra_whatsapp_human_request_v1(uuid,uuid,text,uuid);
COMMIT;
