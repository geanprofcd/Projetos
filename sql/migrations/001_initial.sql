-- Plantar - schema inicial
-- Execute no SQL Editor do Supabase.
create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null,
  email text,
  phone text unique,
  role text not null default 'agronomo' check (role in ('agronomo','responsavel','administrador')),
  status text not null default 'active' check (status in ('active','inactive')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.farms (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.profiles(id) on delete cascade,
  name text not null,
  city text,
  state text,
  area_hectares numeric(12,2),
  created_at timestamptz not null default now()
);

create table if not exists public.crops (
  id uuid primary key default gen_random_uuid(),
  name text not null unique
);

create table if not exists public.categories (
  id uuid primary key default gen_random_uuid(),
  name text not null unique
);

create table if not exists public.tickets (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  customer_id uuid not null references public.profiles(id),
  farm_id uuid references public.farms(id),
  crop_id uuid references public.crops(id),
  category_id uuid references public.categories(id),
  assigned_user_id uuid references public.profiles(id),
  status text not null default 'novo' check (status in ('novo','em_atendimento','aguardando_cliente','aguardando_orcamento','finalizado')),
  priority text not null default 'normal' check (priority in ('baixa','normal','alta','urgente')),
  source text not null default 'portal' check (source in ('portal','whatsapp','interno')),
  external_thread_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  closed_at timestamptz
);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid not null references public.tickets(id) on delete cascade,
  sender_id uuid references public.profiles(id),
  body text not null,
  channel text not null default 'internal' check (channel in ('internal','whatsapp','portal')),
  direction text not null default 'outbound' check (direction in ('inbound','outbound')),
  is_internal boolean not null default false,
  external_message_id text unique,
  created_at timestamptz not null default now()
);

create table if not exists public.attachments (
  id uuid primary key default gen_random_uuid(),
  message_id uuid not null references public.messages(id) on delete cascade,
  file_name text not null,
  mime_type text,
  storage_path text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.products (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  manufacturer text,
  category text,
  description text,
  unit text,
  price numeric(14,2),
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.quotes (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid references public.tickets(id),
  customer_id uuid not null references public.profiles(id),
  status text not null default 'draft' check (status in ('draft','sent','accepted','rejected','expired')),
  total numeric(14,2) not null default 0,
  valid_until date,
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now()
);

create table if not exists public.quote_items (
  id uuid primary key default gen_random_uuid(),
  quote_id uuid not null references public.quotes(id) on delete cascade,
  product_id uuid references public.products(id),
  description text not null,
  quantity numeric(12,3) not null default 1,
  unit_price numeric(14,2) not null default 0,
  total numeric(14,2) generated always as (quantity * unit_price) stored
);

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid references public.tickets(id) on delete cascade,
  type text not null,
  title text not null,
  storage_path text not null,
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now()
);

create table if not exists public.internal_notes (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid not null references public.tickets(id) on delete cascade,
  user_id uuid not null references public.profiles(id),
  content text not null,
  created_at timestamptz not null default now()
);

-- Sessão da aplicação: o navegador guarda apenas o token opaco.
create table if not exists public.app_sessions (
  id uuid primary key default gen_random_uuid(),
  token_hash text not null unique,
  user_id uuid not null references public.profiles(id) on delete cascade,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

create index if not exists tickets_status_idx on public.tickets(status);
create index if not exists tickets_customer_idx on public.tickets(customer_id);
create index if not exists tickets_assigned_idx on public.tickets(assigned_user_id);
create index if not exists messages_ticket_created_idx on public.messages(ticket_id, created_at);
create index if not exists sessions_expires_idx on public.app_sessions(expires_at);

insert into public.crops(name) values ('Soja'),('Milho'),('Algodão'),('Café'),('Cana'),('Feijão'),('Trigo') on conflict do nothing;
insert into public.categories(name) values ('Plantio'),('Adubação'),('Pragas'),('Doenças'),('Defensivos'),('Irrigação'),('Colheita'),('Máquinas'),('Análise de solo'),('Orçamento'),('Documentação'),('Comercial'),('Outros') on conflict do nothing;

-- RLS ligado por padrão. A primeira versão acessa dados somente pelo backend Python
-- com service_role. Não exponha essa chave no navegador.
alter table public.profiles enable row level security;
alter table public.farms enable row level security;
alter table public.crops enable row level security;
alter table public.categories enable row level security;
alter table public.tickets enable row level security;
alter table public.messages enable row level security;
alter table public.attachments enable row level security;
alter table public.products enable row level security;
alter table public.quotes enable row level security;
alter table public.quote_items enable row level security;
alter table public.documents enable row level security;
alter table public.internal_notes enable row level security;
alter table public.app_sessions enable row level security;
