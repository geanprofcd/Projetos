-- VENDRA — draft NÃO aplicado automaticamente.
-- A numeração definitiva das migrations CRM permanece pendente de reconciliação
-- com a linha Plantar documentada 007-013.

create table if not exists lost_reasons (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists opportunities (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references customers(id),
  ticket_id uuid null references tickets(id),
  title text not null,
  funnel_id uuid not null references sales_funnels(id),
  stage_id uuid not null references funnel_stages(id),
  assigned_user_id uuid null references profiles(id),
  status text not null default 'open' check (status in ('open','won','lost')),
  currency_code text not null default 'BRL',
  calculated_value numeric(18,2) not null default 0,
  final_value numeric(18,2) null,
  expected_close_date date null,
  won_at timestamptz null,
  lost_at timestamptz null,
  lost_reason_id uuid null references lost_reasons(id),
  lost_notes text null,
  kanban_position bigint not null default 1000,
  lock_version integer not null default 1,
  archived_at timestamptz null,
  archived_by uuid null references profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists opportunity_items (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  product_id uuid null references products(id),
  name_snapshot text not null,
  description_snapshot text null,
  unit_snapshot text null,
  quantity numeric(18,4) not null check (quantity > 0),
  unit_price numeric(18,2) not null check (unit_price >= 0),
  discount_amount numeric(18,2) not null default 0,
  subtotal numeric(18,2) not null check (subtotal >= 0),
  line_position integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists opportunity_stage_history (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  from_stage_id uuid null references funnel_stages(id),
  to_stage_id uuid not null references funnel_stages(id),
  moved_by uuid null references profiles(id),
  source text not null default 'detail',
  moved_at timestamptz not null default now()
);

-- Integridade que deve ser consolidada na migration definitiva:
-- 1) stage_id pertence ao funnel_id da oportunidade;
-- 2) no máximo uma oportunidade OPEN por ticket na v0.1;
-- 3) calculated_value é derivado dos opportunity_items;
-- 4) itens históricos preservam snapshots mesmo se produto for inativado;
-- 5) excluir card no Kanban significa arquivar (archived_at/archived_by), não apagar histórico.
