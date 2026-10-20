-- Preparado para homologacao STAGING; nao executado automaticamente.
-- Leitura somente. Nenhuma tabela, RLS, trigger ou configuracao e alterada.
CREATE OR REPLACE FUNCTION public.vendra_kanban_window_v1(
 p_funnel_id uuid, p_search text DEFAULT NULL, p_assigned_user_id uuid DEFAULT NULL,
 p_windows jsonb DEFAULT '{}'::jsonb, p_limit integer DEFAULT 120)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path = '' AS $fn$
WITH candidates AS MATERIALIZED (
 SELECT o.id,o.stage_id,o.title,o.customer_id,o.ticket_id,o.assigned_user_id,
  o.lock_version,o.expected_close_date,o.calculated_value,o.created_at,o.updated_at,
  coalesce(c.name,'Cliente') AS customer_name,
  coalesce(p.full_name,'Sem responsável') AS assigned_name,
  t.created_at AS ticket_created_at,t.status AS ticket_status,
  latest.created_at AS last_activity_at,latest.direction AS last_direction,
  coalesce(latest.direction='inbound',false) AS inbound_priority,
  coalesce(latest.created_at,o.updated_at,o.created_at) AS activity_at
 FROM public.opportunities o
 JOIN public.funnel_stages s ON s.id=o.stage_id AND s.is_active
 JOIN public.sales_funnels f ON f.id=o.funnel_id AND f.is_active
 LEFT JOIN public.customers c ON c.id=o.customer_id
 LEFT JOIN public.tickets t ON t.id=o.ticket_id
 LEFT JOIN public.profiles p ON p.id=o.assigned_user_id AND p.status='active'
 LEFT JOIN LATERAL (
  SELECT m.created_at,m.direction FROM public.messages m
  WHERE m.ticket_id=o.ticket_id AND NOT m.is_internal AND m.created_at<=now()
   AND (m.direction='inbound' OR (m.direction='outbound'
    AND coalesce(m.delivery_status,'') NOT IN ('failed','cancelled','pending','claimed')))
  ORDER BY m.created_at DESC,(m.direction='inbound') DESC,m.id DESC LIMIT 1
 ) latest ON true
 WHERE o.funnel_id=p_funnel_id AND o.status='open' AND o.archived_at IS NULL
  AND (p_assigned_user_id IS NULL OR o.assigned_user_id=p_assigned_user_id)
  AND (nullif(btrim(p_search),'') IS NULL OR strpos(lower(concat_ws(' ',o.title,c.name,f.name,s.name,p.full_name)),lower(btrim(p_search)))>0)
), ranked AS MATERIALIZED (
 SELECT c.*,row_number() OVER (PARTITION BY stage_id ORDER BY inbound_priority DESC,activity_at DESC,id DESC)-1 AS position
 FROM candidates c
), totals AS (
 SELECT s.id AS stage_id,count(c.id) AS count,coalesce(sum(c.calculated_value),0) AS total
 FROM public.funnel_stages s LEFT JOIN candidates c ON c.stage_id=s.id
 WHERE s.funnel_id=p_funnel_id AND s.is_active GROUP BY s.id
), windows AS (
 SELECT t.*,greatest(0,least(greatest(t.count-1,0),
  CASE WHEN coalesce(p_windows->>t.stage_id::text,'0') ~ '^[0-9]{1,8}$'
   THEN coalesce(p_windows->>t.stage_id::text,'0')::bigint ELSE 0 END)) AS start_at
 FROM totals t
)
SELECT coalesce(jsonb_agg(jsonb_build_object('stage_id',w.stage_id,'count',w.count,
 'total',w.total,'offset',w.start_at,'cards',coalesce((
  SELECT jsonb_agg(to_jsonb(r) || jsonb_build_object('first_reply_at',(
   SELECT min(m.created_at) FROM public.messages m WHERE m.ticket_id=r.ticket_id
    AND NOT m.is_internal AND m.direction='inbound' AND m.created_at<=now()
  )) ORDER BY r.position)
  FROM ranked r WHERE r.stage_id=w.stage_id AND r.position>=w.start_at
   AND r.position<w.start_at+greatest(1,least(coalesce(p_limit,120),120))
 ),'[]'::jsonb))),'[]'::jsonb) FROM windows w;
$fn$;
REVOKE ALL ON FUNCTION public.vendra_kanban_window_v1(uuid,text,uuid,jsonb,integer) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.vendra_kanban_window_v1(uuid,text,uuid,jsonb,integer) TO service_role;
