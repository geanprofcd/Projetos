-- Primeiro restaurar Make/portal ao contrato anterior; nao altera mensagens existentes.
DROP FUNCTION IF EXISTS public.vendra_whatsapp_human_or_media_prepare_v1(uuid);
DROP FUNCTION IF EXISTS public.vendra_whatsapp_media_prepare_v1(uuid);
DROP FUNCTION IF EXISTS public.vendra_whatsapp_media_request_v1(uuid,uuid,text,uuid,jsonb);
DROP FUNCTION IF EXISTS public.vendra_whatsapp_uncertain_v1(uuid,text);
