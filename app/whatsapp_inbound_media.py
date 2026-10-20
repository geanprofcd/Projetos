"""Recepção de arquivos do Make, sem token Meta, envio ou configuração global."""
from dataclasses import dataclass
import base64
import binascii
import hashlib
import re

MAX_MEDIA_BYTES = 25 * 1024 * 1024
MAX_BASE64_CHARS = 4 * ((MAX_MEDIA_BYTES + 2) // 3)
FORMATS = {
    'image/jpeg': ('image', 'jpg', 5),
    'image/png': ('image', 'png', 5),
    'application/pdf': ('document', 'pdf', 25),
    'text/plain': ('document', 'txt', 15),
    'audio/mpeg': ('audio', 'mp3', 16),
    'audio/mp4': ('audio', 'm4a', 16),
    'audio/ogg': ('audio', 'ogg', 16),
    'video/mp4': ('video', 'mp4', 16),
}


class MediaInvalid(ValueError):
    pass


class MediaUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ReceivedFile:
    content: bytes
    metadata: dict


def prepare_received_file(*, message_id, media_type, mime_type, file_name, content_base64, expected_sha256):
    spec = FORMATS.get(mime_type)
    if spec is None or spec[0] != media_type:
        raise MediaInvalid('Formato de mídia não suportado.')
    if len(content_base64) > MAX_BASE64_CHARS:
        raise MediaInvalid('Arquivo excede o limite de recepção.')
    try:
        content = base64.b64decode(content_base64, validate=True)
    except (ValueError, binascii.Error):
        raise MediaInvalid('Arquivo codificado inválido.') from None
    if not content or len(content) > spec[2] * 1024 * 1024:
        raise MediaInvalid('Arquivo vazio ou acima do limite permitido.')
    digest = hashlib.sha256(content).hexdigest()
    # A Meta informa o SHA em base64; aceitar também hexadecimal de ferramentas locais.
    try:
        expected = (expected_sha256.lower() if re.fullmatch(r'[a-fA-F0-9]{64}', expected_sha256)
                    else base64.b64decode(expected_sha256, validate=True).hex())
    except (ValueError, binascii.Error):
        raise MediaInvalid('Checksum de origem inválido.') from None
    if expected != digest:
        raise MediaInvalid('O arquivo recebido não confere com o checksum de origem.')
    valid = {
        'image/jpeg': content.startswith(b'\xff\xd8\xff'),
        'image/png': content.startswith(b'\x89PNG\r\n\x1a\n'),
        'application/pdf': content.startswith(b'%PDF-'),
        'text/plain': b'\x00' not in content,
        'audio/mpeg': content.startswith(b'ID3') or (len(content)>1 and content[0]==255 and content[1]&224==224),
        'audio/mp4': len(content)>12 and content[4:8]==b'ftyp',
        'audio/ogg': content.startswith(b'OggS') and b'OpusHead' in content[:65536],
        'video/mp4': len(content)>12 and content[4:8]==b'ftyp',
    }[mime_type]
    if not valid:
        raise MediaInvalid('O conteúdo não corresponde ao formato informado.')
    if mime_type == 'text/plain':
        try: content.decode('utf8')
        except UnicodeError: raise MediaInvalid('Documento TXT precisa usar UTF-8.') from None
    name = re.split(r'[/\\]', file_name or '')[-1]
    name = re.sub(r'[^A-Za-z0-9À-ÿ._() -]', '_', name).strip(' .')[:140]
    if not name: name = 'Arquivo.'+spec[1]
    # A extensão vem do formato conferido, nunca do caminho fornecido pelo cliente.
    name = re.sub(r'\.[^.]*$', '', name) if '.' in name else name
    name = (name or 'Arquivo')+'.'+spec[1]
    key = hashlib.sha256(message_id.encode('utf8')).hexdigest()
    return ReceivedFile(content, dict(file_name=name, mime_type=mime_type, size_bytes=len(content),
        checksum_sha256=digest, storage_path=f'whatsapp-inbound/{key}/{digest}.{spec[1]}'))


def store_received_file(client, prepared):
    """Chave determinística, sem upsert e sem remover resultado de escrita incerta."""
    bucket = client.storage.from_('ticket-attachments')
    try:
        bucket.upload(prepared.metadata['storage_path'], prepared.content,
                      {'content-type': prepared.metadata['mime_type'], 'upsert': 'false'})
    except Exception as exc:
        duplicate = (str(getattr(exc, 'status', getattr(exc, 'status_code', ''))) == '409'
                     or str(getattr(exc, 'code', '')) in ('409', 'Duplicate')
                     or 'Duplicate' in str(exc))
        if not duplicate:
            raise MediaUnavailable('Não foi possível confirmar o arquivo; repetir o mesmo evento.') from None
        try:
            current = bucket.download(prepared.metadata['storage_path'])
            if hashlib.sha256(current).hexdigest() != prepared.metadata['checksum_sha256']:
                raise MediaInvalid('Arquivo privado divergente.')
        except MediaInvalid:
            raise
        except Exception:
            raise MediaUnavailable('Não foi possível conferir o arquivo existente.') from None


def remove_unreferenced_file(client, prepared):
    """Só após rejeição definitiva da RPC; nunca após timeout/resultado incerto."""
    try:
        used = client.table('attachments').select('id').eq('storage_path', prepared.metadata['storage_path']).limit(1).execute().data
        if not used:
            client.storage.from_('ticket-attachments').remove([prepared.metadata['storage_path']])
    except Exception:
        # Falha de leitura não autoriza apagar objeto que pode estar em uso.
        pass
