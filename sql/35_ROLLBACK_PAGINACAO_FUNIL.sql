-- Desativar primeiro a leitura paginada no backend; nao apagar dados.
DROP FUNCTION IF EXISTS public.vendra_kanban_window_v1(uuid,text,uuid,jsonb,integer);
