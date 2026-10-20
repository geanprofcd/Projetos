-- Contrato separado: aplicar somente no destino autorizado, depois validar ACL.
-- Nao altera o contrato de texto, tabelas, RLS, flags ou cenarios Make.
CREATE OR REPLACE FUNCTION public.vendra_whatsapp_media_receive_v1(
 p_phone text,p_name text,p_body text,p_external_message_id text,p_occurred_at timestamptz,
 p_media_id text,p_attachment jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path TO '' AS $fn$
DECLARE
 ev public.integration_events%ROWTYPE;
 result jsonb; fingerprint text; attachment_id uuid; expected_path text;
 mime text:=p_attachment->>'mime_type'; ext text; size_limit bigint;
 phone text:=regexp_replace(coalesce(p_phone,''),'[^0-9]','','g');
BEGIN
 IF phone !~ '^55[0-9]{10,11}$' OR p_media_id IS NULL OR p_media_id !~ '^[0-9]{1,80}$'
  OR length(coalesce(p_external_message_id,'')) NOT BETWEEN 1 AND 430
  OR jsonb_typeof(p_attachment) IS DISTINCT FROM 'object'
  OR length(coalesce(p_attachment->>'file_name','')) NOT BETWEEN 1 AND 160
  OR coalesce(p_attachment->>'checksum_sha256','') !~ '^[0-9a-f]{64}$'
  OR coalesce(p_attachment->>'size_bytes','') !~ '^[0-9]{1,8}$' THEN
  RAISE EXCEPTION 'Metadados de midia invalidos' USING ERRCODE='22023';
 END IF;
 IF length(phone)=13 AND substr(phone,5,1)='9' THEN phone:=substr(phone,1,4)||substr(phone,6); END IF;
 ext:=CASE mime WHEN 'image/jpeg' THEN 'jpg' WHEN 'image/png' THEN 'png'
  WHEN 'application/pdf' THEN 'pdf' WHEN 'text/plain' THEN 'txt'
  WHEN 'audio/mpeg' THEN 'mp3' WHEN 'audio/mp4' THEN 'm4a'
  WHEN 'audio/ogg' THEN 'ogg' WHEN 'video/mp4' THEN 'mp4' END;
 size_limit:=(CASE WHEN mime LIKE 'image/%' THEN 5 WHEN mime='application/pdf' THEN 25 WHEN mime='text/plain' THEN 15 ELSE 16 END)::bigint*1024*1024;
 expected_path:='whatsapp-inbound/'||encode(sha256(convert_to(p_external_message_id,'UTF8')),'hex')
  ||'/'||(p_attachment->>'checksum_sha256')||'.'||ext;
 IF ext IS NULL OR (p_attachment->>'size_bytes')::bigint NOT BETWEEN 1 AND size_limit
  OR p_attachment->>'storage_path' IS DISTINCT FROM expected_path
  OR p_attachment->>'file_name' LIKE '%/%' OR p_attachment->>'file_name' LIKE E'%\\%'
  OR p_body IS NULL OR length(btrim(p_body)) NOT BETWEEN 1 AND 10000
  OR p_occurred_at IS NULL OR NOT isfinite(p_occurred_at)
  OR p_occurred_at > now()+interval '60 seconds' OR p_occurred_at < timestamptz '2020-01-01' THEN
  RAISE EXCEPTION 'Arquivo de midia invalido' USING ERRCODE='22023';
 END IF;
 fingerprint:=encode(sha256(convert_to(jsonb_build_array(phone,btrim(p_body),extract(epoch FROM p_occurred_at),p_media_id,p_attachment)::text,'UTF8')),'hex');
 PERFORM pg_advisory_xact_lock(hashtextextended('whatsapp:media:'||p_external_message_id,0));
 SELECT * INTO ev FROM public.integration_events
  WHERE provider='whatsapp' AND external_id='inbound-media:'||p_external_message_id FOR UPDATE;
 IF FOUND THEN
  IF ev.event_type IS DISTINCT FROM 'message.media' OR ev.status IS DISTINCT FROM 'processed'
   OR ev.payload_hash IS DISTINCT FROM fingerprint THEN
   RAISE EXCEPTION 'WAMID de midia reutilizado com outro arquivo' USING ERRCODE='PT409';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM public.attachments a JOIN public.messages m ON m.id=a.message_id
   WHERE a.id=(ev.payload->>'attachment_id')::uuid AND m.id=(ev.payload->>'message_id')::uuid
   AND m.external_message_id=p_external_message_id AND a.storage_path=expected_path) THEN
   RAISE EXCEPTION 'Evento de midia exige reconciliacao' USING ERRCODE='55000';
  END IF;
  RETURN ev.payload||jsonb_build_object('duplicate',true);
 END IF;
 -- Mesma transacao: janela, atividade, Novo Lead->Qualificacao e regra IA vigentes.
 result:=public.vendra_whatsapp_receive_v1(phone,p_name,p_body,p_external_message_id,p_occurred_at);
 IF result->>'duplicate' IS DISTINCT FROM 'false' THEN
  RAISE EXCEPTION 'WAMID ja registrado por outro contrato' USING ERRCODE='PT409';
 END IF;
 INSERT INTO public.attachments(message_id,file_name,mime_type,storage_path,size_bytes,checksum_sha256,uploaded_by)
  VALUES((result->>'message_id')::uuid,p_attachment->>'file_name',mime,expected_path,
   (p_attachment->>'size_bytes')::bigint,p_attachment->>'checksum_sha256',NULL)
  RETURNING id INTO attachment_id;
 result:=result||jsonb_build_object('media_stored',true,'attachment_id',attachment_id);
 INSERT INTO public.integration_events(provider,external_id,event_type,status,payload_hash,payload,entity_type,entity_id,processed_at)
  VALUES('whatsapp','inbound-media:'||p_external_message_id,'message.media','processed',fingerprint,result,
   'ticket',result->>'ticket_id',now());
 RETURN result;
END; $fn$;
REVOKE ALL ON FUNCTION public.vendra_whatsapp_media_receive_v1(text,text,text,text,timestamptz,text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_whatsapp_media_receive_v1(text,text,text,text,timestamptz,text,jsonb) TO service_role;
