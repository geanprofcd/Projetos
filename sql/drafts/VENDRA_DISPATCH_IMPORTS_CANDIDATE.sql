-- VENDRA 0.0.9 - CANDIDATO / NÃO APLICAR AUTOMATICAMENTE
-- A numeração oficial permanece pendente até reconciliação das migrations Plantar 007-013.

create table if not exists dispatch_import_batches (
    id uuid primary key default gen_random_uuid(),
    filename text not null,
    extension text,
    total_count integer not null default 0,
    valid_count integer not null default 0,
    invalid_count integer not null default 0,
    duplicate_count integer not null default 0,
    warnings jsonb not null default '[]'::jsonb,
    imported_by uuid null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists dispatch_import_items (
    id uuid primary key default gen_random_uuid(),
    batch_id uuid not null references dispatch_import_batches(id) on delete cascade,
    row_number integer,
    name text,
    phone_raw text,
    phone text,
    status text not null default 'ready',
    last_error text,
    dispatch_id uuid null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_dispatch_import_items_batch on dispatch_import_items(batch_id, row_number);
create index if not exists idx_dispatch_import_items_phone on dispatch_import_items(phone);
