-- Plantar 0.3.0 - núcleo operacional
-- Clientes independentes de login, histórico/auditoria e idempotência de integrações.

create table if not exists public.customers (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid unique references public.profiles(id) on delete set null,
  name text not null,
  phone text,
  phone_normalized text unique,
  email text,
  document text,
  company_name text,
  status text not null default 'active' check (status in ('active','inactive')),
  tags text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Preserva IDs dos clientes que, na migration 001, eram apontados diretamente para profiles.
insert into public.customers (id, profile_id, name, phone, phone_normalized, email, status)
select distinct
  p.id,
  p.id,
  p.full_name,
  p.phone,
  nullif(regexp_replace(coalesce(p.phone, ''), '[^0-9]', '', 'g'), ''),
  p.email,
  p.status
from public.profiles p
where p.id in (
  select customer_id from public.farms
  union
  select customer_id from public.tickets
  union
  select customer_id from public.quotes
)
on conflict (id) do nothing;

-- Telefones vazios não devem competir pela restrição unique.
update public.customers set phone_normalized = null where phone_normalized = '';

alter table public.farms add column if not exists updated_at timestamptz not null default now();

alter table public.farms drop constraint if exists farms_customer_id_fkey;
alter table public.farms add constraint farms_customer_id_fkey foreign key (customer_id) references public.customers(id) on delete cascade;

alter table public.tickets drop constraint if exists tickets_customer_id_fkey;
alter table public.tickets add constraint tickets_customer_id_fkey foreign key (customer_id) references public.customers(id);

alter table public.quotes drop constraint if exists quotes_customer_id_fkey;
alter table public.quotes add constraint quotes_customer_id_fkey foreign key (customer_id) references public.customers(id);

-- Alinha os estados com a central interna definida no documento mestre.
alter table public.tickets drop constraint if exists tickets_status_check;
alter table public.tickets add constraint tickets_status_check check (
  status in ('novo','em_atendimento','aguardando_cliente','aguardando_interno','aguardando_orcamento','finalizado','cancelado')
);

create table if not exists public.audit_log (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid references public.profiles(id) on delete set null,
  entity_type text not null,
  entity_id text not null,
  action text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.integration_events (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  external_id text not null,
  event_type text not null,
  status text not null default 'received' check (status in ('received','processing','processed','failed','ignored')),
  payload_hash text,
  payload jsonb,
  entity_type text,
  entity_id text,
  error_message text,
  processed_at timestamptz,
  created_at timestamptz not null default now(),
  unique(provider, external_id)
);

create index if not exists customers_name_idx on public.customers (lower(name));
create index if not exists customers_phone_idx on public.customers (phone_normalized);
create index if not exists farms_customer_name_idx on public.farms (customer_id, name);
create index if not exists audit_entity_idx on public.audit_log (entity_type, entity_id, created_at desc);
create index if not exists integration_events_status_idx on public.integration_events (status, created_at desc);

alter table public.customers enable row level security;
alter table public.audit_log enable row level security;
alter table public.integration_events enable row level security;
