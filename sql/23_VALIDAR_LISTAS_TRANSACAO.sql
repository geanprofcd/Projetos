-- Anexar depois do SQL23 dentro de BEGIN/ROLLBACK. Nenhum HTTP/envio.
do $$
declare a uuid; stage uuid; b uuid=gen_random_uuid(); r jsonb; invalid_blocked boolean=false; first_dispatch uuid;
begin
 select id into a from public.profiles where status::text='active' and access_level::text in ('administrativo','comercial','gerencial') limit 1;
 if a is null then raise exception 'Fixture exige ator ativo'; end if;
 insert into public.dispatch_import_batches(id,filename,extension,imported_by,total_count,valid_count) values(b,'CODEX-lista-transacao.csv','.csv',a,3,2);
 insert into public.dispatch_import_items(batch_id,row_number,name,phone_raw,phone,status) values
 (b,1,'CODEX Lista A','5511987654301','551187654301','ready'),
 (b,2,'CODEX Lista B','5511987654302','551187654302','ready'),
 (b,3,'CODEX Lista invalida','0',null,'invalid');
 begin perform public.vendra_dispatch_list_start_v1(a,b,0); exception when others then invalid_blocked=true; end;
 if not invalid_blocked then raise exception 'Quantidade zero nao bloqueada'; end if;
 r=public.vendra_dispatch_list_start_v1(a,b,1);
 if (r->>'bulk_total')::integer<>1 then raise exception 'Quantidade divergente'; end if;
 r=public.vendra_dispatch_list_start_v1(a,b,2);
 if (r->>'bulk_total')::integer<>1 then raise exception 'Clique repetido alterou selecao'; end if;
 if (select count(*) from public.dispatch_import_items where batch_id=b and status='queued')<>1 then raise exception 'Selecionou mais de um'; end if;
 if (select count(*) from public.dispatch_import_items where batch_id=b and status='ready')<>1 then raise exception 'Contato restante perdido'; end if;
 if has_table_privilege('anon','public.dispatch_import_items','SELECT') or has_table_privilege('authenticated','public.dispatch_import_batches','SELECT') then raise exception 'ACL indevida'; end if;
 if has_function_privilege('anon','public.vendra_dispatch_list_start_v1(uuid,uuid,integer)','EXECUTE') then raise exception 'RPC publica'; end if;
 if not(select relrowsecurity from pg_class where oid='public.dispatch_import_items'::regclass) then raise exception 'RLS ausente'; end if;
 insert into public.integration_settings(key,settings) values('dispatch_lists','{"enabled":true}'),('dispatch_bridge','{"enabled":true}')
 on conflict(key) do update set settings=integration_settings.settings || excluded.settings;
 select id into stage from public.funnel_stages where is_active=true limit 1;
 r=public.vendra_dispatch_list_claim_v1(stage);
 if r->>'claimed'<>'true' then raise exception 'Reserva de fila falhou'; end if;
 first_dispatch=(r->'dispatch'->>'id')::uuid;
 r=public.vendra_dispatch_list_claim_v1(stage);
 if r->>'claimed'<>'false' then raise exception 'Item reservado duas vezes'; end if;
 if (select count(*) from public.dispatch_import_items where batch_id=b and dispatch_id=first_dispatch)<>1 then raise exception 'Vinculo duplicado'; end if;
 if exists(select 1 from public.whatsapp_outbox where message_id=(select message_id from public.dispatches where id=first_dispatch)) then raise exception 'Validacao nao deve reservar envio externo'; end if;
 -- Simula queda depois da confirmacao: reconciliar, sem selecionar novamente o item.
 update public.dispatches set status='sent' where id=first_dispatch;
 update public.dispatch_import_batches set bulk_status='completed' where id=b;
 perform public.vendra_dispatch_list_start_v1(a,b,1);
 if (select status from public.dispatch_import_items where dispatch_id=first_dispatch)<>'sent' then raise exception 'Retomada nao reconciliou confirmacao'; end if;
 if (select count(*) from public.dispatch_import_items where batch_id=b and status='queued')<>1 then raise exception 'Retomada duplicou selecao'; end if;
end $$;
select 'quantity_1_of_2,repeated_click,invalid_quantity,invalid_row_excluded,acl,rls,one_claim_no_duplicate,dispatch_link,no_outbox,resume_without_reselect:passed; no_external_send' as validation;
