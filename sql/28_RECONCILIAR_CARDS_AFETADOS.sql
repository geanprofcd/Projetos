-- Reconciliacao de cards presos pela regra anterior. Sem mensagem/outbox/envio.
-- Backup privado antes de executar. Cada correcao registra estado anterior em audit_log.
BEGIN;
DO $repair$
DECLARE r record; t public.tickets%ROWTYPE; result jsonb; v_enabled boolean; changed integer:=0; activated integer:=0;
BEGIN
 SELECT coalesce(settings->>'enabled','false')='true' INTO v_enabled FROM public.integration_settings WHERE key='ai_automation';
 FOR r IN
  SELECT o.id AS opportunity_id,tickets.id AS ticket_id,o.stage_id AS previous_stage,o.lock_version AS previous_lock,
   dispatch.at AS dispatch_at
  FROM public.opportunities o JOIN public.tickets tickets ON tickets.id=o.ticket_id
  JOIN public.funnel_stages stage ON stage.id=o.stage_id
  JOIN LATERAL(SELECT max(created_at) AS at FROM public.dispatches WHERE ticket_id=tickets.id
    AND provider_message_id IS NOT NULL AND status IN ('sent','delivered','read')) dispatch ON dispatch.at IS NOT NULL
  JOIN LATERAL(SELECT max(created_at) AS at FROM public.messages WHERE ticket_id=tickets.id
    AND direction='inbound' AND is_internal=false) inbound ON inbound.at>=dispatch.at
  WHERE o.status='open' AND o.archived_at IS NULL AND lower(btrim(stage.name))='novo lead'
   AND tickets.status NOT IN ('finalizado','cancelado')
   AND NOT EXISTS(SELECT 1 FROM public.opportunity_stage_history h WHERE h.opportunity_id=o.id
    AND h.source IN ('kanban','detail') AND h.moved_at>inbound.at)
  FOR UPDATE OF o,tickets
 LOOP
  SELECT * INTO t FROM public.tickets WHERE id=r.ticket_id;
  result:=public.vendra_commercial_stage_v1(t.id,'qualification','commercial_v3_repair');
  IF result->>'applied'='true' THEN
   INSERT INTO public.audit_log(entity_type,entity_id,action,payload)
    VALUES('opportunity',r.opportunity_id::text,'commercial_v3_repair_backup',jsonb_build_object(
     'previous_stage_id',r.previous_stage,'previous_lock_version',r.previous_lock,
     'ticket_id',t.id,'previous_mode',t.automation_mode,'previous_automation_version',t.automation_version,
     'previous_resumed_at',t.ai_resumed_at,'previous_resumed_by',t.ai_resumed_by));
   changed:=changed+1;
   IF coalesce(v_enabled,false) AND t.automation_mode<>'ai' AND NOT(t.ai_paused_by IS NOT NULL
     AND t.ai_paused_at>=r.dispatch_at AND t.ai_paused_at>=coalesce(t.ai_resumed_at,'-infinity'::timestamptz)) THEN
    UPDATE public.tickets SET automation_mode='ai',automation_version=automation_version+1,
     ai_resumed_at=now(),ai_resumed_by='new_lead_reply_repair',updated_at=now() WHERE id=t.id;
    activated:=activated+1;
   END IF;
  END IF;
 END LOOP;
 PERFORM set_config('vendra.repair_cards',changed::text,true);
 PERFORM set_config('vendra.repair_ai',activated::text,true);
END $repair$;
SELECT current_setting('vendra.repair_cards')::integer AS cards_reconciled,
 current_setting('vendra.repair_ai')::integer AS ai_activated;
COMMIT;
