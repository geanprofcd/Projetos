-- PREPARADO, NAO EXECUTADO. Nao apaga dados. Desligar rotas/flags antes da reversao.
DROP FUNCTION public.vendra_dispatch_bind_v1(p_dispatch_id uuid, p_outbox_id uuid, p_provider_message_id text, p_claim_token text);
DROP FUNCTION public.vendra_dispatch_prepare_v1(p_dispatch_id uuid, p_phone text, p_name text, p_template_key text);
DROP FUNCTION public.vendra_dispatch_provider_status_v1(p_provider_message_id text, p_status text, p_occurred_at timestamp with time zone, p_recipient_id text, p_error_message text);
DROP FUNCTION public.vendra_dispatch_request_v1(p_actor_id uuid, p_name text, p_phone text, p_stage_id uuid, p_request_id uuid);
DROP FUNCTION public.vendra_whatsapp_ai_prepare_v1(p_ticket_id uuid, p_inbound_message_id uuid, p_body text, p_expected_version integer);
DROP FUNCTION public.vendra_whatsapp_bind_v1(p_outbox_id uuid, p_provider_message_id text, p_claim_token text);
DROP FUNCTION public.vendra_whatsapp_control_v1(p_ticket_id uuid);
DROP FUNCTION public.vendra_whatsapp_human_prepare_v1(p_outbox_id uuid);
DROP FUNCTION public.vendra_whatsapp_human_request_v1(p_actor_id uuid, p_ticket_id uuid, p_body text, p_request_id uuid);
DROP FUNCTION public.vendra_whatsapp_mode_v1(p_ticket_id uuid, p_mode text, p_expected_version integer, p_actor_id uuid);
DROP FUNCTION public.vendra_whatsapp_receive_v1(p_phone text, p_name text, p_body text, p_external_message_id text, p_occurred_at timestamp with time zone);
DROP FUNCTION public.vendra_whatsapp_status_v1(p_provider_message_id text, p_status text, p_occurred_at timestamp with time zone, p_recipient_id text, p_error_message text);
NOTIFY pgrst,'reload schema';

