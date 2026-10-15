-- Deve retornar 3 linhas, presente=true, anon=false, authenticated=false, service_role=true.
WITH expected(name,signature) AS (VALUES
  ('vendra_staging_create_funnel','public.vendra_staging_create_funnel(text,text[],uuid)'),
  ('vendra_staging_create_opportunity','public.vendra_staging_create_opportunity(uuid,uuid,text,uuid)'),
  ('vendra_staging_move_opportunity','public.vendra_staging_move_opportunity(uuid,uuid,integer,uuid)')
)
SELECT name, to_regprocedure(signature) IS NOT NULL AS presente,
  COALESCE(has_function_privilege('anon',to_regprocedure(signature),'EXECUTE'),false) AS anon_executa,
  COALESCE(has_function_privilege('authenticated',to_regprocedure(signature),'EXECUTE'),false) AS authenticated_executa,
  COALESCE(has_function_privilege('service_role',to_regprocedure(signature),'EXECUTE'),false) AS service_role_executa
FROM expected ORDER BY name;
