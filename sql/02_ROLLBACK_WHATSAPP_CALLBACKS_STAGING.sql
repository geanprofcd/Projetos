-- Operacao separada; nao executar automaticamente com o pacote.
-- Desconectar primeiro o consumidor. Preserva dados, tabelas e RLS.
BEGIN;
DO $guard$
BEGIN
 IF to_regclass('public.staging_transport_contracts') IS NULL THEN
   RAISE EXCEPTION 'Rollback permitido somente em STAGING identificado';
 END IF;
END;
$guard$;
DROP FUNCTION IF EXISTS public.vendra_whatsapp_receive_v1(text,text,text,text,timestamptz);
DROP FUNCTION IF EXISTS public.vendra_whatsapp_status_v1(text,text,timestamptz,text,text);
COMMIT;
