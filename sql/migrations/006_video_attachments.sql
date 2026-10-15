-- Plantar 0.5.5 - amplia o bucket privado para vídeo.
-- Execute após 005_admin_integration_settings.sql em ambientes já existentes.

update storage.buckets
set
  file_size_limit = 52428800,
  allowed_mime_types = array[
    'image/jpeg','image/png','image/webp','image/gif',
    'application/pdf',
    'audio/mpeg','audio/ogg','audio/wav','audio/x-wav','audio/mp4',
    'video/mp4','video/quicktime','video/webm','video/ogg','video/x-msvideo','video/x-matroska',
    'video/mpeg','video/3gpp','video/3gpp2','video/x-ms-wmv','video/x-ms-asf','video/x-flv','video/mp2t',
    'text/plain','text/csv'
  ]
where id = 'ticket-attachments';
