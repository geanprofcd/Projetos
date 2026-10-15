-- VENDRA v0.0.21 — aplicar manualmente APÓS conciliar a linhagem histórica.
-- NÃO executar sobre o banco real sem prévia homologação do schema.
-- Mantém profiles.role legado para compatibilidade com o código existente.
BEGIN;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS access_level text;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS can_manage_users boolean NOT NULL DEFAULT false;
UPDATE public.profiles SET access_level = CASE
 WHEN role = 'administrador' THEN 'administrativo'
 WHEN role = 'responsavel' THEN 'comercial'
 ELSE 'comum' END
WHERE access_level IS NULL;
ALTER TABLE public.profiles ALTER COLUMN access_level SET DEFAULT 'comum';
ALTER TABLE public.profiles ALTER COLUMN access_level SET NOT NULL;
ALTER TABLE public.profiles DROP CONSTRAINT IF EXISTS profiles_access_level_check;
ALTER TABLE public.profiles ADD CONSTRAINT profiles_access_level_check
 CHECK (access_level IN ('comum','comercial','gerencial','administrativo'));

CREATE TABLE IF NOT EXISTS public.user_invitations (
 id uuid PRIMARY KEY,
 email text NOT NULL,
 full_name text NOT NULL,
 access_level text NOT NULL CHECK (access_level IN ('comum','comercial','gerencial','administrativo')),
 invited_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
 token_hash text UNIQUE NOT NULL,
 expires_at timestamptz NOT NULL,
 status text NOT NULL CHECK (status IN ('pending','sent','processing','accepted','revoked','failed')),
 created_at timestamptz NOT NULL DEFAULT now(),
 consumed_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_user_invites_email ON public.user_invitations (lower(email));
CREATE INDEX IF NOT EXISTS idx_user_invites_expiry ON public.user_invitations (expires_at);
ALTER TABLE public.user_invitations ENABLE ROW LEVEL SECURITY;
-- Não conceder políticas públicas: apenas service_role pode gerenciar convites.
COMMIT;
