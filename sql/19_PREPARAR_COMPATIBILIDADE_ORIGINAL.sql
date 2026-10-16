-- PREPARADO, NAO APLICADO. Compatibilidade com telas originais, sem alterar UI.
-- Destino persistente autorizado separadamente: znkjibqcikuigfwfsbjb.
-- Primeiro validar em transacao revertida no STAGING ljufhqnadzltqbtdaulv.
-- Aborta se qualquer tabela ja existir; nao sobrescreve estruturas existentes.
DO $$ BEGIN
 IF to_regclass('public.farms') IS NOT NULL OR to_regclass('public.crops') IS NOT NULL OR to_regclass('public.categories') IS NOT NULL THEN
  RAISE EXCEPTION 'Compatibilidade ja existe ou estado inesperado; interrompido';
 END IF;
END $$;
CREATE TABLE public.farms (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 customer_id uuid NOT NULL REFERENCES public.customers(id) ON DELETE CASCADE,
 name text NOT NULL,
 city text,
 state text,
 area_hectares numeric(12,2),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX farms_customer_name_idx ON public.farms(customer_id,name);
CREATE TABLE public.crops (id uuid PRIMARY KEY DEFAULT gen_random_uuid(),name text NOT NULL UNIQUE);
CREATE TABLE public.categories (id uuid PRIMARY KEY DEFAULT gen_random_uuid(),name text NOT NULL UNIQUE);
ALTER TABLE public.farms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crops ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.farms,public.crops,public.categories FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON TABLE public.farms,public.crops,public.categories TO service_role;
NOTIFY pgrst,'reload schema';
