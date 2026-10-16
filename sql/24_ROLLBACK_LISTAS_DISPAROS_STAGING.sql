-- Somente apos desativar worker/canal e conferir que nao existem registros.
do $$ begin
 if exists(select 1 from public.dispatch_import_batches) or exists(select 1 from public.dispatch_import_items) then
  raise exception 'Rollback bloqueado: preserve dados e evidencias das listas';
 end if;
end $$;
drop function if exists public.vendra_dispatch_list_claim_v1(uuid);
drop function if exists public.vendra_dispatch_list_import_v1(uuid,text,text,jsonb,jsonb);
drop function if exists public.vendra_dispatch_list_item_v1(uuid,uuid,uuid,uuid);
drop function if exists public.vendra_dispatch_list_start_v1(uuid,uuid,integer);
drop table public.dispatch_import_items;
drop table public.dispatch_import_batches;
