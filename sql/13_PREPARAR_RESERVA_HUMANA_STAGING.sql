-- APLICADO somente VENDRA-STAGING com autorizacao especifica em 15/10/2026.
-- Migration vendra_whatsapp_human_reservation_v1; copiar nao executa SQL.
-- Limite Meta ajustado na migration vendra_whatsapp_human_text_limit_v1.
-- Reserva exclusiva de UM texto humano existente; nao cria worker nem envia.
BEGIN;
DO $guard$ BEGIN
 IF to_regclass('public.staging_transport_contracts') IS NULL OR
    to_regprocedure('public.vendra_whatsapp_bind_v1(uuid,text,text)') IS NULL THEN
  RAISE EXCEPTION 'Exige VENDRA-STAGING homologado; nao aplicar no principal';
 END IF;
 IF to_regprocedure('public.vendra_whatsapp_human_prepare_v1(uuid)') IS NOT NULL THEN
  RAISE EXCEPTION 'Funcao humana ja existe; revisar migration antes de repetir';
 END IF;
END; $guard$;
CREATE FUNCTION public.vendra_whatsapp_human_prepare_v1(p_outbox_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
DECLARE o public.whatsapp_outbox%ROWTYPE; t public.tickets%ROWTYPE;
 m public.messages%ROWTYPE; c public.customers%ROWTYPE; v_ticket_id uuid;
 control jsonb; token text; outgoing_phone text; customer_phone text;
BEGIN
 SELECT w.ticket_id INTO v_ticket_id FROM public.whatsapp_outbox w WHERE w.id=p_outbox_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Saida nao encontrada' USING ERRCODE='22023'; END IF;
 -- Mesma ordem do handoff: ticket, depois outbox. Concorrentes serializados.
 SELECT * INTO t FROM public.tickets WHERE id=v_ticket_id FOR UPDATE;
 SELECT * INTO o FROM public.whatsapp_outbox WHERE id=p_outbox_id FOR UPDATE;
 IF NOT FOUND OR o.ticket_id IS DISTINCT FROM t.id THEN
  RAISE EXCEPTION 'Atendimento/saida divergentes' USING ERRCODE='22023';
 END IF;
 -- Mesmo chamador nao recebe autorizacao outra vez. Resultado incerto nao e reenvio.
 IF o.status<>'pending' OR o.provider_message_id IS NOT NULL THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,
   'duplicate',true,'reason','already_reserved_or_final','outbox_id',o.id);
 END IF;
 IF t.source<>'whatsapp' OR t.status IN ('finalizado','cancelado') OR t.automation_mode<>'human' THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,
   'reason','ticket_not_human_or_open','outbox_id',o.id);
 END IF;
 control:=public.vendra_whatsapp_control_v1(t.id);
 IF NOT (control->>'window_open')::boolean THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,
   'reason','window_closed','outbox_id',o.id);
 END IF;
 SELECT * INTO m FROM public.messages WHERE id=o.message_id AND ticket_id=t.id;
 IF NOT FOUND OR m.direction<>'outbound' OR m.channel<>'whatsapp' OR m.is_internal
    OR coalesce(m.sender_kind,'')<>'human' OR m.sender_id IS NULL OR coalesce(length(btrim(m.body)),0) NOT BETWEEN 1 AND 4096
    OR m.body IS DISTINCT FROM o.body OR m.external_message_id IS NOT NULL OR m.delivery_status<>'pending' THEN
  RAISE EXCEPTION 'Mensagem humana divergente' USING ERRCODE='22023';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM public.profiles WHERE id=m.sender_id AND status='active'
    AND access_level IN ('administrativo','comercial','gerencial')) THEN
  RAISE EXCEPTION 'Autor humano ativo obrigatorio' USING ERRCODE='42501';
 END IF;
 -- Anexos exigem contrato proprio de mensagens/WAMIDs; nao liberar envio parcial.
 IF EXISTS(SELECT 1 FROM public.attachments WHERE message_id=m.id) THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,
   'reason','media_contract_required','outbox_id',o.id);
 END IF;
 SELECT * INTO c FROM public.customers WHERE id=t.customer_id;
 IF NOT FOUND OR c.status<>'active' OR c.id IS DISTINCT FROM o.customer_id
    OR c.phone_normalized IS NULL OR o.phone IS NULL THEN
  RAISE EXCEPTION 'Cliente/telefone divergentes' USING ERRCODE='22023';
 END IF;
 outgoing_phone:=regexp_replace(o.phone,'[^0-9]','','g');
 customer_phone:=regexp_replace(c.phone_normalized,'[^0-9]','','g');
 IF outgoing_phone !~ '^55[0-9]{10,11}$' OR customer_phone !~ '^55[0-9]{10,11}$' THEN
  RAISE EXCEPTION 'Telefone brasileiro invalido' USING ERRCODE='22023';
 END IF;
 IF length(outgoing_phone)=13 AND substr(outgoing_phone,5,1)='9' THEN
  outgoing_phone:=substr(outgoing_phone,1,4)||substr(outgoing_phone,6);
 END IF;
 IF length(customer_phone)=13 AND substr(customer_phone,5,1)='9' THEN
  customer_phone:=substr(customer_phone,1,4)||substr(customer_phone,6);
 END IF;
 IF outgoing_phone IS DISTINCT FROM customer_phone THEN
  RAISE EXCEPTION 'Cliente/telefone divergentes' USING ERRCODE='22023';
 END IF;
 token:=gen_random_uuid()::text;
 UPDATE public.whatsapp_outbox SET status='claimed',claimed_by=token,claimed_at=now(),
  attempt_count=coalesce(attempt_count,0)+1,updated_at=now(),last_error=NULL WHERE id=o.id;
 UPDATE public.messages SET delivery_status='claimed',external_status_updated_at=now() WHERE id=m.id;
 RETURN jsonb_build_object('accepted',true,'authorized',true,'suppressed',false,
  'duplicate',false,'outbox_id',o.id,'message_id',m.id,'outbox',
  jsonb_build_object('id',o.id,'phone',outgoing_phone,'body',o.body,'claim_token',token,
   'delivery_policy',jsonb_build_object('authorized_to_send',true,'template_required',false)));
END; $fn$;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_human_prepare_v1(uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_human_prepare_v1(uuid) TO service_role;
COMMIT;
