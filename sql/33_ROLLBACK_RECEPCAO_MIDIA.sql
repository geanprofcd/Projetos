-- Antes de executar: retirar SOMENTE a rota nova de midia do Make e desabilitar
-- VENDRA_BRIDGE_INBOUND_MEDIA_ENABLED. Nao pausar cenarios originais de texto/IA.
-- Preserva mensagens, anexos, eventos, arquivos privados e todas as RPCs anteriores.
DROP FUNCTION IF EXISTS public.vendra_whatsapp_media_receive_v1(text,text,text,text,timestamptz,text,jsonb);
