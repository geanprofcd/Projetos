-- APLICADO em 15/10/2026 somente VENDRA-STAGING, com autorizacao especifica.
-- Migration: vendra_whatsapp_team_global_control_v1. Copiar arquivo nao executa SQL.
-- Duas funcoes existentes; sem tabelas/RLS/worker/envio. Override whatsapp_bridge prevalece.
BEGIN;
DO $guard$ BEGIN
 IF to_regclass('public.staging_transport_contracts') IS NULL OR
    to_regprocedure('public.vendra_whatsapp_mode_v1(uuid,text,integer,uuid)') IS NULL THEN
   RAISE EXCEPTION 'Exige VENDRA-STAGING homologado; nao aplicar no principal';
 END IF;
END; $guard$;
CREATE OR REPLACE FUNCTION public.vendra_whatsapp_control_v1(p_ticket_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
DECLARE t public.tickets%ROWTYPE; enabled boolean; last_inbound timestamptz; is_open boolean;
BEGIN
 SELECT * INTO t FROM public.tickets WHERE id=p_ticket_id;
 IF NOT FOUND OR t.source<>'whatsapp' THEN RAISE EXCEPTION 'Atendimento WhatsApp nao encontrado' USING ERRCODE='22023'; END IF;
 enabled := coalesce((SELECT settings->>'ai_enabled'='true' FROM public.integration_settings WHERE key='whatsapp_bridge'),
   (SELECT settings->>'enabled'='true' FROM public.integration_settings WHERE key='ai_automation'),false);
 SELECT max(created_at) INTO last_inbound FROM public.messages
  WHERE ticket_id=t.id AND channel='whatsapp' AND direction='inbound' AND NOT is_internal;
 is_open := coalesce(last_inbound<=now() AND last_inbound>now()-interval '24 hours',false);
 RETURN jsonb_build_object('accepted',true,'ticket_id',t.id,'mode',t.automation_mode,
  'enabled',enabled,'control_version',t.automation_version,
  'connected',enabled AND t.automation_mode='ai' AND t.status NOT IN ('finalizado','cancelado'),
  'route_to_ai',enabled AND t.automation_mode='ai' AND is_open AND t.status NOT IN ('finalizado','cancelado'),
  'window_open',is_open,'expires_at',last_inbound+interval '24 hours','thread_id','VENDRA-'||t.id::text);
END; $fn$;

CREATE OR REPLACE FUNCTION public.vendra_whatsapp_mode_v1(p_ticket_id uuid,p_mode text,p_expected_version integer,p_actor_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
DECLARE t public.tickets%ROWTYPE;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.profiles WHERE id=p_actor_id AND access_level IN ('administrativo','comercial','gerencial') AND status='active') THEN
  RAISE EXCEPTION 'Perfil ativo de atendimento obrigatorio' USING ERRCODE='42501';
 END IF;
 IF p_mode IS NULL OR p_mode NOT IN ('human','ai') OR p_expected_version IS NULL THEN
  RAISE EXCEPTION 'Controle invalido' USING ERRCODE='22023';
 END IF;
 SELECT * INTO t FROM public.tickets WHERE id=p_ticket_id FOR UPDATE;
 IF NOT FOUND OR t.source<>'whatsapp' OR t.status IN ('finalizado','cancelado') THEN
  RAISE EXCEPTION 'Atendimento nao permite alterar IA' USING ERRCODE='22023';
 END IF;
 IF t.automation_version<>p_expected_version THEN RAISE EXCEPTION 'Controle desatualizado' USING ERRCODE='PT409'; END IF;
 IF t.automation_mode<>p_mode THEN
  UPDATE public.tickets SET automation_mode=p_mode,automation_version=automation_version+1,updated_at=now(),
    ai_paused_at=CASE WHEN p_mode='human' THEN now() ELSE ai_paused_at END,
    ai_paused_by=CASE WHEN p_mode='human' THEN p_actor_id::text ELSE ai_paused_by END,
    ai_resumed_at=CASE WHEN p_mode='ai' THEN now() ELSE ai_resumed_at END,
    ai_resumed_by=CASE WHEN p_mode='ai' THEN p_actor_id::text ELSE ai_resumed_by END WHERE id=t.id;
  -- Apenas pendencias ainda nao reservadas. Claimed pode estar em voo no provedor.
  WITH cancelled AS (
   UPDATE public.whatsapp_outbox SET status='cancelled',updated_at=now()
    WHERE ticket_id=t.id AND status='pending' AND provider_message_id IS NULL AND p_mode='human'
    RETURNING message_id
  ) UPDATE public.messages SET delivery_status='cancelled',external_status_updated_at=now()
    WHERE id IN (SELECT message_id FROM cancelled);
  INSERT INTO public.audit_log(actor_id,entity_type,entity_id,action,payload)
    VALUES(p_actor_id,'ticket',t.id::text,'whatsapp_ai_mode',jsonb_build_object('mode',p_mode,'version',t.automation_version+1));
 END IF;
 RETURN public.vendra_whatsapp_control_v1(t.id);
END; $fn$;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_control_v1(uuid) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_mode_v1(uuid,text,integer,uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_control_v1(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_mode_v1(uuid,text,integer,uuid) TO service_role;
COMMIT;
