-- NAO EXECUTAR automaticamente. Apenas tabelas criadas pelo SQL19, vazias.
-- DROP sem CASCADE: dependencias novas impedem reversao.
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM public.farms) OR EXISTS(SELECT 1 FROM public.crops) OR EXISTS(SELECT 1 FROM public.categories) THEN
  RAISE EXCEPTION 'Ha dados; preservar e planejar reversao especifica';
 END IF;
END $$;
DROP TABLE public.farms,public.crops,public.categories;
NOTIFY pgrst,'reload schema';
