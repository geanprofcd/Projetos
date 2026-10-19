"""Arquivos privados: comando atômico, uma mensagem/outbox por arquivo."""
import hashlib
import threading
from uuid import UUID

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.whatsapp_human_command_service import HumanCommandConflict, HumanCommandUnavailable


def media_type(mime):
    return {'image/jpeg':'image','image/png':'image','audio/mpeg':'audio',
            'audio/mp4':'audio','audio/ogg':'audio','video/mp4':'video',
            'application/pdf':'document','text/plain':'document'}.get(mime)


def validate_media(prepared):
    kind = media_type(prepared.mime_type)
    if not kind:
        raise ValueError('Formato não suportado pelo WhatsApp. Use JPG, PNG, PDF, TXT, MP3, M4A, OGG/Opus ou MP4.')
    limit = (5 if kind == 'image' else 16 if kind in ('audio','video') else 15)*1024*1024
    if prepared.size_bytes > limit:
        raise ValueError(f'O WhatsApp permite até {limit//1024//1024} MB para este tipo de arquivo.')
    if prepared.mime_type == 'audio/ogg' and b'OpusHead' not in prepared.content[:65536]:
        raise ValueError('O áudio OGG precisa usar o codec Opus para envio pelo WhatsApp.')
    return kind


def request_human_media(*, actor_id, ticket_id, body, request_id, files):
    s=get_settings()
    if s.demo_mode or not s.whatsapp_persistent_control_enabled or not s.supabase_configured:
        raise ValueError('Comando persistente de mídia não configurado.')
    try:actor_id,ticket_id,request_id=[str(UUID(str(v))) for v in (actor_id,ticket_id,request_id)]
    except (ValueError,TypeError,AttributeError):raise ValueError('Atualize o formulário antes de enviar arquivos.') from None
    if not 1<=len(files)<=6 or len(body.strip())>4096:
        raise ValueError('Envie até seis arquivos e texto de até 4096 caracteres.')
    for prepared in files:validate_media(prepared)
    db=get_admin_client()
    config=db.table('integration_settings').select('settings').eq('key','whatsapp_media').limit(1).execute().data or []
    if not config or config[0].get('settings',{}).get('enabled') is not True:
        raise ValueError('O canal de mídia WhatsApp ainda não está habilitado.')
    bucket=db.storage.from_(s.attachment_bucket);metadata=[]
    for i,prepared in enumerate(files,1):
        path=f'tickets/{ticket_id}/{request_id}/{i}-{prepared.checksum_sha256}-{prepared.file_name}'
        metadata.append(dict(file_name=prepared.file_name,mime_type=prepared.mime_type,
                             size_bytes=prepared.size_bytes,checksum_sha256=prepared.checksum_sha256,storage_path=path))
        try:bucket.upload(path,prepared.content,{'content-type':prepared.mime_type,'upsert':'false'})
        except Exception as exc:
            # Repetição/concorrrência só reutiliza o objeto se o conteúdo confere.
            if str(getattr(exc,'status',getattr(exc,'status_code',''))) not in ('409',) and 'Duplicate' not in str(exc):
                raise HumanCommandUnavailable('Não foi possível confirmar o upload. Reenvie este mesmo formulário.') from None
            if hashlib.sha256(bucket.download(path)).hexdigest()!=prepared.checksum_sha256:
                raise HumanCommandConflict('Arquivo armazenado divergente; atualize o formulário.') from None
    try:
        result=db.rpc('vendra_whatsapp_media_request_v1',dict(p_actor_id=actor_id,p_ticket_id=ticket_id,
                      p_body=body.strip(),p_request_id=request_id,p_files=metadata)).execute().data
    except Exception as exc:
        code=str(getattr(exc,'code',''))
        if code in ('PT409','22023','42501'):
            # Rejeição conhecida: remover somente uploads sem vínculo no banco.
            for item in metadata:
                try:
                    used=db.table('attachments').select('id').eq('storage_path',item['storage_path']).limit(1).execute().data
                    if not used:bucket.remove([item['storage_path']])
                except Exception:
                    pass
        if code=='PT409':raise HumanCommandConflict('Este formulário já foi usado com outros arquivos ou texto.') from None
        if code in ('22023','42501'):raise ValueError('Confira sua permissão, a janela WhatsApp e o canal de mídia.') from None
        # Resultado incerto pode ter sido confirmado; não apagar objetos nem trocar nonce.
        raise HumanCommandUnavailable('Não foi possível confirmar o comando. Reenvie o mesmo formulário para conferir.') from None
    outputs=result.get('outboxes') if isinstance(result,dict) else None
    if (not isinstance(result,dict) or result.get('accepted') is not True
            or type(result.get('duplicate')) is not bool or not isinstance(outputs,list)
            or len(outputs)!=len(files)+bool(body.strip())):
        raise HumanCommandUnavailable('O banco não confirmou todos os arquivos. Reenvie o mesmo formulário.')
    for out in outputs:
        if str(out.get('ticket_id'))!=ticket_id or not out.get('message_id') or not out.get('id'):
            raise HumanCommandUnavailable('Vínculos de mídia divergentes; envio não acionado.')
    return result


def notify_media_batch(outputs):
    # Preservar a ordem do texto/arquivos; nenhuma tentativa automática de reenvio.
    from app.services.outbox_wake_service import send_make_outbox_wake
    pending=[dict(o) for o in outputs if o.get('status')=='pending']
    def worker():
        for out in pending:
            result=send_make_outbox_wake(out,timeout=30)
            db=get_admin_client()
            rows=db.table('whatsapp_outbox').select('status,provider_message_id,claimed_by').eq('id',out['id']).limit(1).execute().data or []
            confirmed=bool(rows and rows[0].get('provider_message_id') and rows[0].get('status') in ('sent','delivered','read'))
            if not result.get('sent') or not confirmed:
                if rows and rows[0].get('status')=='claimed' and rows[0].get('claimed_by'):
                    try:db.rpc('vendra_whatsapp_uncertain_v1',{'p_outbox_id':out['id'],'p_claim_token':rows[0]['claimed_by']}).execute()
                    except Exception:pass
                break
    if pending:threading.Thread(target=worker,name='vendra-media-wake',daemon=True).start()
