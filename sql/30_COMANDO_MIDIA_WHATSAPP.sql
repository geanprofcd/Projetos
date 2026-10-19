-- Uma mensagem/outbox/WAMID por arquivo; nenhuma tabela ou policy nova.
CREATE OR REPLACE FUNCTION public.vendra_whatsapp_media_request_v1(
 p_actor_id uuid,p_ticket_id uuid,p_body text,p_request_id uuid,p_files jsonb)
RETURNS jsonb LANGUAGE plpgsql SET search_path TO '' AS $function$
DECLARE e public.integration_events%ROWTYPE; f jsonb; part jsonb; fingerprint text;
 event_key text; child_id uuid; i integer:=0; outputs jsonb:='[]'::jsonb; media_config jsonb; v_phone text;
BEGIN
 IF p_actor_id IS NULL OR p_ticket_id IS NULL OR p_request_id IS NULL
  OR length(coalesce(p_body,''))>4096 OR jsonb_typeof(p_files) IS DISTINCT FROM 'array'
  OR jsonb_array_length(p_files) NOT BETWEEN 1 AND 6 THEN
  RAISE EXCEPTION 'Comando de midia invalido' USING ERRCODE='22023';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM public.profiles WHERE id=p_actor_id AND status='active'
  AND access_level IN ('administrativo','comercial','gerencial')) THEN
  RAISE EXCEPTION 'Equipe ativa obrigatoria' USING ERRCODE='42501';
 END IF;
 event_key:='media-request:'||p_request_id::text;
 fingerprint:=encode(sha256(convert_to(jsonb_build_array(p_actor_id,p_ticket_id,btrim(coalesce(p_body,'')),p_files)::text,'UTF8')),'hex');
 PERFORM pg_advisory_xact_lock(hashtextextended(event_key,0));
 SELECT * INTO e FROM public.integration_events WHERE provider='vendra' AND external_id=event_key;
 IF FOUND THEN
  IF e.event_type<>'message.human.media.requested' OR e.payload_hash IS DISTINCT FROM fingerprint THEN
   RAISE EXCEPTION 'Formulario ja usado com outros arquivos' USING ERRCODE='PT409';
  END IF;
  SELECT coalesce(jsonb_agg(jsonb_build_object('id',w.id,'ticket_id',w.ticket_id,
    'message_id',w.message_id,'status',w.status,'created_at',w.created_at) ORDER BY ids.ordinality),'[]'::jsonb)
   INTO outputs FROM jsonb_array_elements_text(e.payload->'outbox_ids') WITH ORDINALITY AS ids(id,ordinality)
   JOIN public.whatsapp_outbox w ON w.id=ids.id::uuid AND w.ticket_id=p_ticket_id;
  IF jsonb_array_length(outputs)<>jsonb_array_length(e.payload->'outbox_ids') THEN
   RAISE EXCEPTION 'Comando anterior indisponivel' USING ERRCODE='PT409';
  END IF;
  RETURN jsonb_build_object('accepted',true,'duplicate',true,'outboxes',outputs);
 END IF;
 SELECT settings INTO media_config FROM public.integration_settings WHERE key='whatsapp_media';
 IF coalesce(media_config->>'enabled','false')<>'true' THEN
  RAISE EXCEPTION 'Canal de midia desativado' USING ERRCODE='42501';
 END IF;
 SELECT regexp_replace(c.phone_normalized,'[^0-9]','','g') INTO v_phone
  FROM public.tickets t JOIN public.customers c ON c.id=t.customer_id WHERE t.id=p_ticket_id;
 IF length(v_phone)=13 AND substr(v_phone,5,1)='9' THEN v_phone:=substr(v_phone,1,4)||substr(v_phone,6); END IF;
 IF jsonb_array_length(coalesce(media_config->'allowed_phones','[]'::jsonb))>0
  AND NOT (media_config->'allowed_phones' ? coalesce(v_phone,'')) THEN
  RAISE EXCEPTION 'Destinatario fora do teste de midia' USING ERRCODE='42501';
 END IF;
 -- Validar o conjunto antes de criar qualquer mensagem.
 FOR f IN SELECT value FROM jsonb_array_elements(p_files) LOOP
  IF coalesce(f->>'file_name','')='' OR length(f->>'file_name')>160
   OR coalesce(f->>'checksum_sha256','') !~ '^[a-f0-9]{64}$'
   OR coalesce(f->>'storage_path','') NOT LIKE 'tickets/'||p_ticket_id::text||'/'||p_request_id::text||'/%'
   OR position('/../' in f->>'storage_path')>0
   OR coalesce(f->>'mime_type','') NOT IN ('image/jpeg','image/png','audio/mpeg','audio/mp4','audio/ogg','video/mp4','application/pdf','text/plain')
   OR coalesce((f->>'size_bytes')::bigint,0) NOT BETWEEN 1 AND
    (CASE WHEN f->>'mime_type' LIKE 'image/%' THEN 5242880
         WHEN f->>'mime_type' LIKE 'video/%' OR f->>'mime_type' LIKE 'audio/%' THEN 16777216 ELSE 15728640 END) THEN
   RAISE EXCEPTION 'Arquivo fora do contrato WhatsApp' USING ERRCODE='22023';
  END IF;
 END LOOP;
 IF btrim(coalesce(p_body,''))<>'' THEN
  child_id:=md5(p_request_id::text||':text')::uuid;
  part:=public.vendra_whatsapp_human_request_v1(p_actor_id,p_ticket_id,btrim(p_body),child_id);
  outputs:=outputs||jsonb_build_array(part->'outbox');
 END IF;
 FOR f IN SELECT value FROM jsonb_array_elements(p_files) LOOP
  i:=i+1;child_id:=md5(p_request_id::text||':file:'||i::text)::uuid;
  part:=public.vendra_whatsapp_human_request_v1(p_actor_id,p_ticket_id,'Arquivo: '||(f->>'file_name'),child_id);
  INSERT INTO public.attachments(message_id,file_name,mime_type,storage_path,size_bytes,checksum_sha256,uploaded_by)
   VALUES((part->>'message_id')::uuid,f->>'file_name',f->>'mime_type',f->>'storage_path',
    (f->>'size_bytes')::bigint,f->>'checksum_sha256',p_actor_id);
  UPDATE public.messages SET created_at=clock_timestamp() WHERE id=(part->>'message_id')::uuid;
  outputs:=outputs||jsonb_build_array(part->'outbox');
 END LOOP;
 INSERT INTO public.integration_events(provider,external_id,event_type,status,payload_hash,payload,entity_type,entity_id,processed_at)
  VALUES('vendra',event_key,'message.human.media.requested','processed',fingerprint,
   jsonb_build_object('request_id',p_request_id,'ticket_id',p_ticket_id,'actor_id',p_actor_id,
    'outbox_ids',(SELECT jsonb_agg(value->>'id') FROM jsonb_array_elements(outputs))),
   'ticket',p_ticket_id::text,now());
 RETURN jsonb_build_object('accepted',true,'duplicate',false,'outboxes',outputs);
END; $function$;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_media_request_v1(uuid,uuid,text,uuid,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_media_request_v1(uuid,uuid,text,uuid,jsonb) TO service_role;

CREATE OR REPLACE FUNCTION public.vendra_whatsapp_media_prepare_v1(p_outbox_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE o public.whatsapp_outbox%ROWTYPE; t public.tickets%ROWTYPE;
 m public.messages%ROWTYPE; c public.customers%ROWTYPE; v_ticket_id uuid;
 control jsonb; token text; outgoing_phone text; customer_phone text;
 attachment public.attachments%ROWTYPE; media_type text;
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
 IF NOT EXISTS(SELECT 1 FROM public.integration_settings WHERE key='whatsapp_media' AND settings->>'enabled'='true') THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,'reason','media_disabled','outbox_id',o.id);
 END IF;
 IF (SELECT count(*) FROM public.attachments WHERE message_id=m.id)<>1 THEN
  RAISE EXCEPTION 'Um arquivo por mensagem obrigatorio' USING ERRCODE='22023';
 END IF;
 SELECT * INTO attachment FROM public.attachments WHERE message_id=m.id;
 media_type:=CASE WHEN attachment.mime_type IN ('image/jpeg','image/png') THEN 'image'
  WHEN attachment.mime_type IN ('audio/mpeg','audio/mp4','audio/ogg') THEN 'audio'
  WHEN attachment.mime_type='video/mp4' THEN 'video'
  WHEN attachment.mime_type IN ('application/pdf','text/plain') THEN 'document' END;
 IF media_type IS NULL OR attachment.uploaded_by IS DISTINCT FROM m.sender_id THEN
  RAISE EXCEPTION 'Anexo divergente' USING ERRCODE='22023';
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
 IF EXISTS(SELECT 1 FROM public.integration_settings WHERE key='whatsapp_media'
  AND jsonb_array_length(coalesce(settings->'allowed_phones','[]'::jsonb))>0
  AND NOT (settings->'allowed_phones' ? outgoing_phone)) THEN
  RETURN jsonb_build_object('accepted',true,'authorized',false,'suppressed',true,'reason','media_recipient_scope','outbox_id',o.id);
 END IF;
 token:=gen_random_uuid()::text;
 UPDATE public.whatsapp_outbox SET status='claimed',claimed_by=token,claimed_at=now(),
  attempt_count=coalesce(attempt_count,0)+1,updated_at=now(),last_error=NULL WHERE id=o.id;
 UPDATE public.messages SET delivery_status='claimed',external_status_updated_at=now() WHERE id=m.id;
 RETURN jsonb_build_object('accepted',true,'authorized',true,'suppressed',false,
  'duplicate',false,'outbox_id',o.id,'message_id',m.id,'outbox',
  jsonb_build_object('id',o.id,'phone',outgoing_phone,'body',o.body,'claim_token',token,
   'message_type',media_type,'media',jsonb_build_object('id',attachment.id,'file_name',attachment.file_name,'mime_type',attachment.mime_type),
   'delivery_policy',jsonb_build_object('authorized_to_send',true,'template_required',false)));
END; $function$;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_media_prepare_v1(p_outbox_id uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_media_prepare_v1(p_outbox_id uuid) TO service_role;

CREATE OR REPLACE FUNCTION public.vendra_whatsapp_human_or_media_prepare_v1(p_outbox_id uuid)
 RETURNS jsonb LANGUAGE plpgsql SET search_path TO '' AS $function$
 DECLARE result jsonb;
 BEGIN
  IF EXISTS(SELECT 1 FROM public.attachments a JOIN public.whatsapp_outbox o ON o.message_id=a.message_id WHERE o.id=p_outbox_id) THEN
   RETURN public.vendra_whatsapp_media_prepare_v1(p_outbox_id);
  END IF;
  result:=public.vendra_whatsapp_human_prepare_v1(p_outbox_id);
  IF result->>'authorized'='true' THEN result:=jsonb_set(result,'{outbox,message_type}','"text"'::jsonb); END IF;
  RETURN result;
 END; $function$;
 REVOKE ALL ON FUNCTION public.vendra_whatsapp_human_or_media_prepare_v1(uuid) FROM PUBLIC,anon,authenticated;
 GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_human_or_media_prepare_v1(uuid) TO service_role;

CREATE OR REPLACE FUNCTION public.vendra_whatsapp_uncertain_v1(p_outbox_id uuid,p_claim_token text)
 RETURNS jsonb LANGUAGE plpgsql SET search_path TO '' AS $function$
DECLARE o public.whatsapp_outbox%ROWTYPE;
BEGIN
 SELECT * INTO o FROM public.whatsapp_outbox WHERE id=p_outbox_id FOR UPDATE;
 IF NOT FOUND OR o.claimed_by IS DISTINCT FROM p_claim_token OR length(coalesce(p_claim_token,''))<32 THEN
  RAISE EXCEPTION 'Reserva divergente' USING ERRCODE='42501';
 END IF;
 IF o.provider_message_id IS NOT NULL OR o.status IN ('sent','delivered','read','cancelled') THEN
  RETURN jsonb_build_object('accepted',true,'suppressed',true,'reason','provider_already_bound');
 END IF;
 IF o.status<>'claimed' THEN RAISE EXCEPTION 'Reserva nao confirmada' USING ERRCODE='22023'; END IF;
 UPDATE public.whatsapp_outbox SET last_error='Envio nao confirmado. Revisar a execucao Make antes de repetir.',updated_at=now() WHERE id=o.id;
 RETURN jsonb_build_object('accepted',true,'status','claimed','review_required',true,'outbox_id',o.id);
END; $function$;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_uncertain_v1(uuid,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_uncertain_v1(uuid,text) TO service_role;
