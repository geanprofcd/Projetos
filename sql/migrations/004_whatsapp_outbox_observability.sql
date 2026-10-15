-- Plantar 0.5.0 - ponte WhatsApp/Make, status de entrega e observabilidade.
-- Execute após 001_initial.sql, 002_operational_core.sql e 003_private_attachments.sql.

alter table public.messages add column if not exists delivery_status text;
alter table public.messages add column if not exists external_status_updated_at timestamptz;

alter table public.messages drop constraint if exists messages_delivery_status_check;
alter table public.messages add constraint messages_delivery_status_check check (
  delivery_status is null or delivery_status in ('received','pending','claimed','sent','delivered','read','failed','cancelled')
);

create table if not exists public.whatsapp_outbox (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid not null references public.tickets(id) on delete cascade,
  message_id uuid not null unique references public.messages(id) on delete cascade,
  customer_id uuid not null references public.customers(id),
  phone text not null,
  body text not null default '',
  status text not null default 'pending' check (status in ('pending','claimed','sent','delivered','read','failed','cancelled')),
  attempt_count integer not null default 0,
  claimed_at timestamptz,
  claimed_by text,
  provider_message_id text,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists whatsapp_outbox_status_created_idx on public.whatsapp_outbox(status, created_at);
create index if not exists whatsapp_outbox_provider_message_idx on public.whatsapp_outbox(provider_message_id);
create index if not exists messages_delivery_status_idx on public.messages(delivery_status, external_status_updated_at);

alter table public.whatsapp_outbox enable row level security;

-- O backend usa service_role. A função oferece claim atômico para evitar que dois cenários Make
-- processem a mesma saída quando houver concorrência ou recuperação de worker travado.
create or replace function public.claim_whatsapp_outbox(
  p_limit integer default 10,
  p_claimed_by text default 'make-whatsapp',
  p_claim_ttl_seconds integer default 120
)
returns setof public.whatsapp_outbox
language plpgsql
security definer
set search_path = public
as $$
begin
  return query
  with candidates as (
    select id
    from public.whatsapp_outbox
    where status = 'pending'
       or (
         status = 'claimed'
         and (claimed_at is null or claimed_at < now() - make_interval(secs => greatest(p_claim_ttl_seconds, 30)))
       )
    order by created_at
    for update skip locked
    limit greatest(least(p_limit, 50), 1)
  ), updated as (
    update public.whatsapp_outbox o
       set status = 'claimed',
           claimed_at = now(),
           claimed_by = left(coalesce(p_claimed_by, 'make-whatsapp'), 120),
           attempt_count = attempt_count + 1,
           last_error = null,
           updated_at = now()
      from candidates c
     where o.id = c.id
     returning o.*
  )
  select * from updated order by created_at;
end;
$$;

revoke all on function public.claim_whatsapp_outbox(integer, text, integer) from public;
revoke all on function public.claim_whatsapp_outbox(integer, text, integer) from anon;
revoke all on function public.claim_whatsapp_outbox(integer, text, integer) from authenticated;
grant execute on function public.claim_whatsapp_outbox(integer, text, integer) to service_role;
