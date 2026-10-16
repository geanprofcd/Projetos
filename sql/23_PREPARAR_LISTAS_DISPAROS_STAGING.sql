-- PREPARADO: validar no STAGING antes de aplicar/promover.
-- Persistencia de listas; aplicar este SQL nao inicia worker nem envia mensagens.
create table if not exists public.dispatch_import_batches (
 id uuid primary key default gen_random_uuid(), filename text not null,
 extension text not null, total_count integer not null default 0,
 valid_count integer not null default 0, invalid_count integer not null default 0,
 duplicate_count integer not null default 0, warnings jsonb not null default '[]',
 imported_by uuid not null references public.profiles(id),
 bulk_status text not null default 'idle' check(bulk_status in ('idle','queued','running','completed','completed_with_errors','interrupted')),
 bulk_total integer not null default 0, bulk_requested_by uuid references public.profiles(id),
 bulk_started_at timestamptz, bulk_completed_at timestamptz,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists public.dispatch_import_items (
 id uuid primary key default gen_random_uuid(),
 batch_id uuid not null references public.dispatch_import_batches(id),
 row_number integer not null, name text not null, phone_raw text not null,
 phone text, status text not null check(status in ('ready','invalid','duplicate','queued','processing','pending','submitted','sent','delivered','read','failed','cancelled')),
 last_error text, dispatch_id uuid references public.dispatches(id),
 queued_at timestamptz, claimed_at timestamptz,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(batch_id,row_number)
);
create index if not exists dispatch_import_queue_idx on public.dispatch_import_items(status,queued_at,row_number);
alter table public.dispatch_import_batches enable row level security;
alter table public.dispatch_import_items enable row level security;
revoke all on public.dispatch_import_batches,public.dispatch_import_items from public,anon,authenticated;
grant select,insert,update,delete on public.dispatch_import_batches,public.dispatch_import_items to service_role;

create or replace function public.vendra_dispatch_list_start_v1(p_actor_id uuid,p_batch_id uuid,p_quantity integer)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare b public.dispatch_import_batches%rowtype; n integer;
begin
 if not exists(select 1 from public.profiles where id=p_actor_id and status::text='active' and access_level::text in ('administrativo','comercial','gerencial')) then
  raise exception 'Ator nao autorizado' using errcode='42501';
 end if;
 if p_quantity is null or p_quantity<1 or p_quantity>20000 then raise exception 'Quantidade invalida'; end if;
 select * into b from public.dispatch_import_batches where id=p_batch_id for update;
 if not found then raise exception 'Lista nao encontrada'; end if;
 if b.bulk_status in ('queued','running') then return to_jsonb(b); end if;
 -- Se o processo caiu depois da confirmacao do provedor, reconciliar sem reenviar.
 update public.dispatch_import_items i set status=d.status,updated_at=clock_timestamp()
 from public.dispatches d where i.batch_id=p_batch_id and i.status='processing'
 and d.id=i.dispatch_id and d.status in ('submitted','sent','delivered','read','failed','cancelled');
 -- Processando nao volta para pronto: resultado incerto exige reconciliacao.
 if exists(select 1 from public.dispatch_import_items where batch_id=p_batch_id and status='processing') then
  raise exception 'A lista tem pedido pendente de confirmacao';
 end if;
 with chosen as (
  select id from public.dispatch_import_items where batch_id=p_batch_id and status='ready'
  order by row_number,id limit p_quantity for update
 ), queued as (
  update public.dispatch_import_items i set status='queued',queued_at=clock_timestamp(),updated_at=clock_timestamp()
  from chosen where i.id=chosen.id returning i.id
 ) select count(*) into n from queued;
 if n=0 then raise exception 'Nenhum contato pronto'; end if;
 update public.dispatch_import_batches set bulk_status='queued',bulk_total=n,bulk_requested_by=p_actor_id,
  bulk_started_at=clock_timestamp(),bulk_completed_at=null,updated_at=clock_timestamp()
 where id=p_batch_id returning * into b;
 return to_jsonb(b);
end $$;

create or replace function public.vendra_dispatch_list_claim_v1(p_stage_id uuid)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare i public.dispatch_import_items%rowtype; b public.dispatch_import_batches%rowtype; d jsonb;
begin
 if not coalesce((select settings->'enabled'='true'::jsonb from public.integration_settings where key='dispatch_lists'),false) then
  return jsonb_build_object('claimed',false,'reason','channel_disabled');
 end if;
 select x.* into i from public.dispatch_import_items x join public.dispatch_import_batches y on y.id=x.batch_id
 where x.status='queued' and y.bulk_status in ('queued','running')
 order by x.queued_at,x.row_number,x.id limit 1 for update of x skip locked;
 if not found then return jsonb_build_object('claimed',false); end if;
 select * into b from public.dispatch_import_batches where id=i.batch_id;
 -- O UUID do item e a chave idempotente: mesma linha nunca cria um segundo pedido.
 d=public.vendra_dispatch_request_v1(b.bulk_requested_by,i.name,i.phone,p_stage_id,i.id);
 update public.dispatch_import_items set status='processing',dispatch_id=(d->>'id')::uuid,
  claimed_at=clock_timestamp(),updated_at=clock_timestamp() where id=i.id;
 update public.dispatch_import_batches set bulk_status='running',updated_at=clock_timestamp() where id=i.batch_id;
 return jsonb_build_object('claimed',true,'item_id',i.id,'batch_id',i.batch_id,'dispatch',d);
end $$;
revoke all on function public.vendra_dispatch_list_start_v1(uuid,uuid,integer),public.vendra_dispatch_list_claim_v1(uuid) from public,anon,authenticated;
grant execute on function public.vendra_dispatch_list_start_v1(uuid,uuid,integer),public.vendra_dispatch_list_claim_v1(uuid) to service_role;

create or replace function public.vendra_dispatch_list_import_v1(p_actor_id uuid,p_filename text,p_extension text,p_records jsonb,p_warnings jsonb)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare b public.dispatch_import_batches%rowtype;
begin
 if not exists(select 1 from public.profiles where id=p_actor_id and status::text='active' and access_level::text in ('administrativo','comercial','gerencial')) then raise exception 'Ator nao autorizado' using errcode='42501'; end if;
 if jsonb_typeof(p_records)<>'array' or jsonb_array_length(p_records) not between 1 and 20000 then raise exception 'Lista invalida'; end if;
 insert into public.dispatch_import_batches(filename,extension,imported_by,warnings) values(left(p_filename,220),p_extension,p_actor_id,coalesce(p_warnings,'[]')) returning * into b;
 insert into public.dispatch_import_items(batch_id,row_number,name,phone_raw,phone,status,last_error)
 select b.id,x.row_number,x.name,x.phone_raw,x.phone,x.status,x.last_error
 from jsonb_to_recordset(p_records) as x(row_number integer,name text,phone_raw text,phone text,status text,last_error text);
 if exists(select 1 from public.dispatch_import_items where batch_id=b.id and status not in ('ready','invalid','duplicate')) then raise exception 'Estado inicial invalido'; end if;
 update public.dispatch_import_batches set total_count=(select count(*) from public.dispatch_import_items where batch_id=b.id),
 valid_count=(select count(*) from public.dispatch_import_items where batch_id=b.id and status='ready'),
 invalid_count=(select count(*) from public.dispatch_import_items where batch_id=b.id and status='invalid'),
 duplicate_count=(select count(*) from public.dispatch_import_items where batch_id=b.id and status='duplicate')
 where id=b.id returning * into b;
 return to_jsonb(b);
end $$;
create or replace function public.vendra_dispatch_list_item_v1(p_actor_id uuid,p_batch_id uuid,p_item_id uuid,p_stage_id uuid)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare i public.dispatch_import_items%rowtype; d jsonb;
begin
 select * into i from public.dispatch_import_items where id=p_item_id and batch_id=p_batch_id for update;
 if not found then raise exception 'Contato nao encontrado nesta lista'; end if;
 if i.status not in ('ready','processing','pending','submitted','sent','delivered','read') then raise exception 'Contato indisponivel'; end if;
 d=public.vendra_dispatch_request_v1(p_actor_id,i.name,i.phone,p_stage_id,i.id);
 update public.dispatch_import_items set status=case when i.status='ready' then 'processing' else i.status end,
 dispatch_id=(d->>'id')::uuid,claimed_at=coalesce(claimed_at,clock_timestamp()),updated_at=clock_timestamp() where id=i.id;
 return jsonb_build_object('item_id',i.id,'batch_id',i.batch_id,'dispatch',d);
end $$;
revoke all on function public.vendra_dispatch_list_import_v1(uuid,text,text,jsonb,jsonb),public.vendra_dispatch_list_item_v1(uuid,uuid,uuid,uuid) from public,anon,authenticated;
grant execute on function public.vendra_dispatch_list_import_v1(uuid,text,text,jsonb,jsonb),public.vendra_dispatch_list_item_v1(uuid,uuid,uuid,uuid) to service_role;
