-- Configuracao recuperada da pasta ORIGINAL, .vendra-data/demo_state.json.
-- Somente dados de configuracao: sem DDL, credenciais, clientes ou disparos.
-- Executar primeiro no STAGING; produzir backup antes da aplicacao no original.
BEGIN;
DO $restore$
DECLARE f uuid; s record;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtext('vendra-commercial-configuration-v1'));
  SELECT id INTO f FROM public.sales_funnels WHERE lower(btrim(name))='funil comercial';
  IF f IS NULL THEN
    INSERT INTO public.sales_funnels(name,description,is_active)
      VALUES ('Funil Comercial','Fluxo comercial original VENDRA.',true) RETURNING id INTO f;
  END IF;
  FOR s IN SELECT * FROM (VALUES
    ('Novo lead',1,'#64748b'),('Qualificação',2,'#3157d5'),
    ('Proposta',3,'#7c3aed'),('Negociação',4,'#d97706'),('Fechamento',5,'#15803d')
  ) AS stages(name,position,color) LOOP
    IF NOT EXISTS(SELECT 1 FROM public.funnel_stages WHERE funnel_id=f AND lower(btrim(name))=lower(s.name)) THEN
      IF EXISTS(SELECT 1 FROM public.funnel_stages WHERE funnel_id=f AND position=s.position) THEN
        RAISE EXCEPTION 'Posicao % ocupada: revisar configuracao antes de inserir %',s.position,s.name;
      END IF;
      INSERT INTO public.funnel_stages(funnel_id,name,position,color,is_active)
        VALUES(f,s.name,s.position,s.color,true);
    END IF;
  END LOOP;
  INSERT INTO public.lost_reasons(name,is_active)
    SELECT name,true FROM (VALUES ('Preço'),('Concorrente'),('Sem orçamento'),
      ('Sem retorno'),('Prazo'),('Desistência'),('Outro')) AS reasons(name)
    WHERE NOT EXISTS(SELECT 1 FROM public.lost_reasons current WHERE lower(btrim(current.name))=lower(reasons.name));
END $restore$;
COMMIT;
