from __future__ import annotations

import hashlib
import logging
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services.demo_store import DEMO_ATTACHMENTS


ROOT = Path(__file__).resolve().parents[2]
DEMO_STORAGE_ROOT = ROOT / "runtime" / "demo_storage" / "attachments"
logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "application/pdf",
    "audio/mpeg",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/ogg",
    "video/x-msvideo",
    "video/x-matroska",
    "video/mpeg",
    "video/3gpp",
    "video/3gpp2",
    "video/x-ms-wmv",
    "video/x-ms-asf",
    "video/x-flv",
    "video/mp2t",
    "text/plain",
    "text/csv",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".webm", ".m4v", ".3gp", ".3g2", ".avi", ".mkv",
    ".mpeg", ".mpg", ".wmv", ".asf", ".ogv", ".flv", ".ts", ".mts",
    ".m2ts", ".vob",
}

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf",
    ".mp3", ".ogg", ".wav", ".m4a", ".txt", ".csv",
    *VIDEO_EXTENSIONS,
}

EXTENSION_MIME_TYPES = {
    ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"},
    ".png": {"image/png"}, ".webp": {"image/webp"}, ".gif": {"image/gif"},
    ".pdf": {"application/pdf"}, ".mp3": {"audio/mpeg"}, ".ogg": {"audio/ogg"},
    ".wav": {"audio/wav", "audio/x-wav"}, ".m4a": {"audio/mp4"},
    ".mp4": {"video/mp4"}, ".mov": {"video/quicktime"}, ".webm": {"video/webm"},
    ".m4v": {"video/mp4"}, ".3gp": {"video/3gpp"}, ".3g2": {"video/3gpp2"},
    ".avi": {"video/x-msvideo"}, ".mkv": {"video/x-matroska"},
    ".mpeg": {"video/mpeg"}, ".mpg": {"video/mpeg"}, ".vob": {"video/mpeg"},
    ".wmv": {"video/x-ms-wmv"}, ".asf": {"video/x-ms-asf"},
    ".ogv": {"video/ogg"}, ".flv": {"video/x-flv"},
    ".ts": {"video/mp2t"}, ".mts": {"video/mp2t"}, ".m2ts": {"video/mp2t"},
    ".txt": {"text/plain"}, ".csv": {"text/csv", "text/plain"},
}



class AttachmentError(ValueError):
    pass


@dataclass(slots=True)
class PreparedAttachment:
    file_name: str
    mime_type: str
    content: bytes
    size_bytes: int
    checksum_sha256: str


def _safe_filename(value: str | None) -> str:
    raw = Path(value or "arquivo").name.strip()
    raw = re.sub(r"[^A-Za-z0-9À-ÿ._() -]+", "_", raw)
    raw = re.sub(r"\s+", " ", raw).strip(" .")
    return (raw or "arquivo")[:160]


def _sniff_mime(data: bytes, fallback: str, extension: str = "") -> str:
    head = data[:64]
    ext = extension.lower()
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"OggS"):
        return "video/ogg" if ext == ".ogv" or fallback == "video/ogg" else "audio/ogg"
    if head.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio/wav"
    if head.startswith(b"RIFF") and data[8:12] == b"AVI ":
        return "video/x-msvideo"
    if head.startswith(b"ID3") or (len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return "audio/mpeg"
    # ISO Base Media containers: MP4/M4A/M4V/MOV/3GP/3G2 all use an ftyp box.
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12].lower()
        if ext == ".m4a":
            return "audio/mp4"
        if ext == ".mov" or brand == b"qt  ":
            return "video/quicktime"
        if ext == ".3gp" or brand.startswith(b"3gp"):
            return "video/3gpp"
        if ext == ".3g2" or brand.startswith(b"3g2"):
            return "video/3gpp2"
        return "video/mp4"
    # Matroska/WebM share the EBML signature; extension + declared type disambiguate.
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm" if ext == ".webm" or fallback == "video/webm" else "video/x-matroska"
    # ASF container is used by WMV and legacy ASF files.
    if head.startswith(bytes.fromhex("3026b2758e66cf11a6d900aa0062ce6c")):
        return "video/x-ms-wmv" if ext == ".wmv" else "video/x-ms-asf"
    if head.startswith(b"FLV"):
        return "video/x-flv"
    # MPEG program/elementary streams (also common in VOB/MPG files).
    if head.startswith((b"\x00\x00\x01\xba", b"\x00\x00\x01\xb3")):
        return "video/mpeg"
    # MPEG-TS packets start with sync byte 0x47 every 188 bytes. M2TS commonly adds 4 bytes.
    if ext in {".ts", ".mts", ".m2ts"}:
        if len(data) >= 377 and data[0] == 0x47 and data[188] == 0x47 and data[376] == 0x47:
            return "video/mp2t"
        if len(data) >= 381 and data[4] == 0x47 and data[192] == 0x47 and data[380] == 0x47:
            return "video/mp2t"
    if ext in VIDEO_EXTENSIONS:
        return "application/octet-stream"
    return fallback


def prepare_attachment(file_name: str | None, declared_mime: str | None, content: bytes) -> PreparedAttachment:
    settings = get_settings()
    if not content:
        raise AttachmentError("O arquivo selecionado está vazio.")

    safe_name = _safe_filename(file_name)
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AttachmentError("Tipo de arquivo não permitido. Use imagem, PDF, áudio, vídeo, TXT ou CSV.")

    limit_mb = settings.attachment_video_max_mb if ext in VIDEO_EXTENSIONS else settings.attachment_max_mb
    max_bytes = max(1, limit_mb) * 1024 * 1024
    if len(content) > max_bytes:
        raise AttachmentError(f"O arquivo excede o limite de {limit_mb} MB para este tipo de mídia.")

    guessed = (declared_mime or mimetypes.guess_type(safe_name)[0] or "application/octet-stream").lower().split(";", 1)[0].strip()
    detected = _sniff_mime(content, guessed, ext)
    if detected not in ALLOWED_MIME_TYPES:
        raise AttachmentError("Conteúdo do arquivo não corresponde a um formato permitido.")
    if detected not in EXTENSION_MIME_TYPES.get(ext, set()):
        raise AttachmentError("A extensão do arquivo não corresponde ao conteúdo enviado.")
    if detected.startswith("text/") and b"\x00" in content[:4096]:
        raise AttachmentError("O arquivo de texto contém dados binários e foi bloqueado.")

    # Para formatos com assinatura conhecida, o conteúdo real prevalece sobre o header do navegador.
    mime_type = detected
    return PreparedAttachment(
        file_name=safe_name,
        mime_type=mime_type,
        content=content,
        size_bytes=len(content),
        checksum_sha256=hashlib.sha256(content).hexdigest(),
    )


def _storage_path(ticket_id: str, message_id: str, file_name: str) -> str:
    return f"tickets/{ticket_id}/{message_id}/{uuid4().hex}-{file_name}"


def save_attachment(*, ticket_id: str, message_id: str, uploaded_by: str | None, prepared: PreparedAttachment) -> dict:
    storage_path = _storage_path(ticket_id, message_id, prepared.file_name)
    payload = {
        "id": str(uuid4()),
        "message_id": message_id,
        "file_name": prepared.file_name,
        "mime_type": prepared.mime_type,
        "storage_path": storage_path,
        "size_bytes": prepared.size_bytes,
        "checksum_sha256": prepared.checksum_sha256,
        "uploaded_by": uploaded_by,
    }

    settings = get_settings()
    if settings.demo_mode:
        absolute = DEMO_STORAGE_ROOT / storage_path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_bytes(prepared.content)
        DEMO_ATTACHMENTS.setdefault(message_id, []).append(payload.copy())
        return payload

    admin = get_admin_client()
    bucket = admin.storage.from_(settings.attachment_bucket)
    try:
        bucket.upload(
            path=storage_path,
            file=prepared.content,
            file_options={"content-type": prepared.mime_type, "upsert": "false"},
        )
        row = admin.table("attachments").insert({k: v for k, v in payload.items() if k != "id"}).execute().data[0]
        return row
    except Exception:
        try:
            bucket.remove([storage_path])
        except Exception:
            pass
        raise


def list_attachments_for_messages(message_ids: list[str]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {message_id: [] for message_id in message_ids}
    if not message_ids:
        return result

    if get_settings().demo_mode:
        for message_id in message_ids:
            result[message_id] = [row.copy() for row in DEMO_ATTACHMENTS.get(message_id, [])]
        return result

    rows = (
        get_admin_client()
        .table("attachments")
        .select("id,message_id,file_name,mime_type,storage_path,size_bytes,checksum_sha256,created_at")
        .in_("message_id", message_ids)
        .order("created_at")
        .execute()
        .data
        or []
    )
    for row in rows:
        result.setdefault(row["message_id"], []).append(row)
    return result


def get_attachment(attachment_id: str) -> dict | None:
    if get_settings().demo_mode:
        for rows in DEMO_ATTACHMENTS.values():
            for row in rows:
                if row.get("id") == attachment_id:
                    return row.copy()
        return None

    rows = (
        get_admin_client()
        .table("attachments")
        .select("id,message_id,file_name,mime_type,storage_path,size_bytes,checksum_sha256,created_at")
        .eq("id", attachment_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def get_attachment_ticket_id(attachment: dict) -> str | None:
    message_id = attachment.get("message_id")
    if not message_id:
        return None
    if get_settings().demo_mode:
        # O path é criado pelo servidor e começa sempre em tickets/<ticket_id>/...
        parts = str(attachment.get("storage_path") or "").split("/")
        return parts[1] if len(parts) >= 4 and parts[0] == "tickets" else None
    rows = (
        get_admin_client()
        .table("messages")
        .select("ticket_id")
        .eq("id", message_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0].get("ticket_id") if rows else None


def demo_file_path(attachment: dict) -> Path:
    base = DEMO_STORAGE_ROOT.resolve()
    target = (DEMO_STORAGE_ROOT / str(attachment["storage_path"])).resolve()
    if base != target and base not in target.parents:
        raise AttachmentError("Caminho de anexo inválido.")
    return target


def signed_download_url(attachment: dict, expires_seconds: int = 300) -> str:
    settings = get_settings()
    try:
        response = (
            get_admin_client()
            .storage.from_(settings.attachment_bucket)
            .create_signed_url(attachment["storage_path"], expires_seconds)
        )
    except Exception as exc:
        logger.warning('Falha temporaria ao assinar anexo: %s',type(exc).__name__)
        raise AttachmentError('Download temporariamente indisponível. Tente novamente.') from None
    if isinstance(response, dict):
        url = response.get("signedURL") or response.get("signedUrl") or response.get("signed_url")
        if url:
            return url
    raise AttachmentError("Não foi possível gerar URL temporária para o anexo.")


def human_size(value: int | None) -> str:
    size = float(value or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def enrich_attachment(row: dict, ticket_id: str) -> dict:
    item = row.copy()
    mime_type = str(item.get("mime_type") or "")
    item["is_image"] = mime_type.startswith("image/")
    item["is_audio"] = mime_type.startswith("audio/")
    item["is_video"] = mime_type.startswith("video/")
    item["is_browser_playable_video"] = mime_type in {"video/mp4", "video/webm", "video/ogg", "video/quicktime"}
    item["is_pdf"] = mime_type == "application/pdf"
    item["size_label"] = human_size(item.get("size_bytes"))
    item["url"] = f"/atendimentos/{ticket_id}/anexos/{item['id']}"
    return item


def delete_attachment(attachment: dict) -> None:
    settings = get_settings()
    if settings.demo_mode:
        message_id = str(attachment.get("message_id") or "")
        rows = DEMO_ATTACHMENTS.get(message_id, [])
        DEMO_ATTACHMENTS[message_id] = [row for row in rows if str(row.get("id")) != str(attachment.get("id"))]
        try:
            demo_file_path(attachment).unlink(missing_ok=True)
        except Exception:
            pass
        return

    admin = get_admin_client()
    try:
        admin.storage.from_(settings.attachment_bucket).remove([attachment["storage_path"]])
    finally:
        if attachment.get("id"):
            admin.table("attachments").delete().eq("id", attachment["id"]).execute()
