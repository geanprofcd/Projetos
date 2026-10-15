-- H1-006F: corrige somente a RPC de vinculo aprovada; nao envia/reenvia mensagens.
BEGIN;
CREATE OR REPLACE FUNCTION public.vendra_dispatch_bind_v1(p_dispatch_id uuid,p_outbox_id uuid,p_provider_message_id text,p_claim_token text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $fn$
DECLARE d public.dispatches%ROWTYPE; o public.whatsapp_outbox%ROWTYPE; result jsonb;
BEGIN
 SELECT * INTO d FROM public.dispatches WHERE id=p_dispatch_id;
 SELECT * INTO o FROM public.whatsapp_outbox WHERE id=p_outbox_id;
 IF d.id IS NULL OR o.id IS NULL OR d.message_id<>o.message_id OR d.ticket_id<>o.ticket_id OR d.customer_id<>o.customer_id THEN
  RAISE EXCEPTION 'Reserva nao pertence ao disparo' USING ERRCODE='42501';
 END IF;
 result:=public.vendra_whatsapp_bind_v1(p_outbox_id,p_provider_message_id,p_claim_token);
 UPDATE public.messages SET external_message_id=p_provider_message_id WHERE id=d.message_id
  AND (external_message_id IS NULL OR external_message_id=p_provider_message_id);
 IF NOT FOUND THEN RAISE EXCEPTION 'Mensagem ja tem outro WAMID' USING ERRCODE='PT409'; END IF;
 UPDATE public.dispatches SET provider_message_id=p_provider_message_id,status=result->>'status',updated_at=now()
  WHERE id=d.id AND (provider_message_id IS NULL OR provider_message_id=p_provider_message_id);
 IF NOT FOUND THEN RAISE EXCEPTION 'Disparo ja tem outro WAMID' USING ERRCODE='PT409'; END IF;
 RETURN result||jsonb_build_object('dispatch_id',d.id);
END; $fn$;
REVOKE ALL ON FUNCTION public.vendra_dispatch_bind_v1(uuid,uuid,text,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_dispatch_bind_v1(uuid,uuid,text,text) TO service_role;
COMMIT;
