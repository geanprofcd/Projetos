-- Somente depois de desconectar a copia Make/ponte de disparos. Nao remove dados.
BEGIN;
DROP FUNCTION IF EXISTS public.vendra_dispatch_prepare_v1(uuid,text,text,text);
DROP FUNCTION IF EXISTS public.vendra_dispatch_bind_v1(uuid,uuid,text,text);
DROP FUNCTION IF EXISTS public.vendra_dispatch_provider_status_v1(text,text,timestamptz,text,text);
COMMIT;
