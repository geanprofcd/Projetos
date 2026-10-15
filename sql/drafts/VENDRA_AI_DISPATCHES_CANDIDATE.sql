-- VENDRA 0.0.7 - CANDIDATO (NÃO APLICAR AUTOMATICAMENTE)
-- Dependência: reconciliar a linha oficial de migrations do Plantar/VENDRA antes
-- de numerar ou aplicar esta alteração no Supabase real.

-- Controle por atendimento. A versão invalida respostas da IA que ficaram
-- prontas depois de um handoff humano.
alter table public.tickets
  add column if not exists automation_mode text not null default 'human'
    check (automation_mode in ('ai','human')),
  add column if not exists automation_version integer not null default 1,
  add column if not exists ai_paused_at timestamptz,
  add column if not exists ai_paused_by uuid references public.profiles(id),
  add column if not exists ai_resumed_at timestamptz,
  add column if not exists ai_resumed_by uuid references public.profiles(id);

-- Autoria explícita para respostas geradas pela IA.
alter table public.messages
  add column if not exists sender_kind text not null default 'human'
    check (sender_kind in ('human','ai','customer','system')),
  add column if not exists sender_name_snapshot text;

-- Solicitações de mensagem pré-configurada via Make/Meta.
create table if not exists public.dispatches (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid references public.customers(id),
  name text not null,
  phone text not null,
  status text not null default 'pending'
    check (status in ('pending','submitted','sent','delivered','read','failed','cancelled')),
  template_key text,
  idempotency_key text not null unique,
  requested_by uuid references public.profiles(id),
  provider_message_id text,
  last_error text,
  make_status_code integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_dispatches_created_at on public.dispatches(created_at desc);
create index if not exists idx_dispatches_phone on public.dispatches(phone);
create index if not exists idx_dispatches_status on public.dispatches(status);
