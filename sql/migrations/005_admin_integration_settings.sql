-- Plantar 0.5.1 - configuração administrativa de WhatsApp e webhooks.
-- Execute após as migrations 001 a 004.

create table if not exists public.integration_settings (
  key text primary key,
  settings jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.configured_webhooks (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null,
  public_id text not null unique,
  kind text not null check (kind in ('whatsapp_text','generic_json')),
  active boolean not null default true,
  secret_hash text not null,
  last_used_at timestamptz,
  last_status text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists configured_webhooks_active_idx on public.configured_webhooks(active, created_at desc);

alter table public.integration_settings enable row level security;
alter table public.configured_webhooks enable row level security;

-- As duas tabelas são administrativas. O starter usa service_role somente no backend,
-- e nenhuma policy é criada para anon/authenticated nesta fase.
