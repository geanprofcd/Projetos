-- VENDRA 0.0.2 — contrato SQL candidato para Produtos e Serviços.
-- NÃO É MIGRATION OFICIAL e não integra version.json.
-- A numeração definitiva só será congelada após decisão sobre a baseline
-- 0.5.6.6 recebida versus a paridade 0.5.6.15 documentada.

create table if not exists public.products (
    id uuid primary key default gen_random_uuid(),
    kind text not null check (kind in ('product','service')),
    code text null,
    name text not null,
    description text null,
    category text null,
    unit text null,
    default_price numeric(18,2) not null default 0 check (default_price >= 0),
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- A regra final de unicidade/normalização do SKU deve ser congelada na migration
-- oficial. O código de aplicação já bloqueia duplicidade case-insensitive.
