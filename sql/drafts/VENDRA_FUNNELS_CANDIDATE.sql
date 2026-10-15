-- VENDRA — CANDIDATO, NÃO APLICAR AUTOMATICAMENTE
-- Baseline recebida possui migrations 001-006; a linha Plantar documentada
-- possui 001-013. Este arquivo permanece fora de version.json até reconciliação.

create table if not exists public.sales_funnels (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    description text,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists sales_funnels_name_ci_uq
    on public.sales_funnels (lower(name));

create table if not exists public.funnel_stages (
    id uuid primary key default gen_random_uuid(),
    funnel_id uuid not null references public.sales_funnels(id),
    name text not null,
    position integer not null,
    color text not null default '#3157d5',
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint funnel_stages_position_positive check (position > 0),
    constraint funnel_stages_color_hex check (color ~ '^#[0-9A-Fa-f]{6}$')
);

create unique index if not exists funnel_stages_name_ci_uq
    on public.funnel_stages (funnel_id, lower(name));
create unique index if not exists funnel_stages_position_uq
    on public.funnel_stages (funnel_id, position);
create index if not exists funnel_stages_funnel_idx
    on public.funnel_stages (funnel_id, is_active, position);
