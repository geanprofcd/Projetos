-- VENDRA H1-005B9 | CORRECAO PT409 (SQLSTATE)
-- Projeto-alvo: SOMENTE VENDRA-STAGING (nao executar no projeto principal).
-- Corrige loop de retries no PostgREST 14 ao usar SQLSTATE 40001 para conflito comercial.
-- Mantem toda a maquina de estados e todas as permissoes existentes sem mudancas.
-- Zero INSERT/UPDATE/DELETE, zero envio WhatsApp, zero modificacao nas filas reais.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '20s';
DO $patch$
DECLARE
  v_definition text;
  v_new text;
  v_reg regprocedure;
BEGIN
  IF to_regclass('public.staging_transport_contracts') IS NULL OR
     to_regclass('public.staging_transport_events') IS NULL OR
     to_regclass('public.staging_dispatch_simulations') IS NULL THEN
    RAISE EXCEPTION 'STAGING H1-005B8 nao identificado. Nenhuma alteracao.';
  END IF;
  IF (SELECT count(*) FROM public.dispatches) <> 0 OR
     (SELECT count(*) FROM public.whatsapp_outbox) <> 0 OR
     (SELECT count(*) FROM public.messages) <> 0 THEN
    RAISE EXCEPTION 'Fila real nao vazia. Nenhuma alteracao.';
  END IF;
  v_reg := to_regprocedure('public.vendra_staging_h1_005b8_transition(uuid,text,integer,uuid)');
  IF v_reg IS NULL THEN
    RAISE EXCEPTION 'RPC H1-005B8 ausente. Nenhuma alteracao.';
  END IF;
  v_definition := pg_get_functiondef(v_reg);
  IF v_definition IS NULL THEN
    RAISE EXCEPTION 'Definicao da RPC indisponivel. Nenhuma alteracao.';
  END IF;
  -- Reconhece exclusivamente a implementacao ja homologada, com o erro antigo.
  IF position('Versao divergente; atualize a pagina' in v_definition) = 0 OR
     position('ERRCODE=''40001''' in v_definition) = 0 OR
     position('ERRCODE=''PT409''' in v_definition) <> 0 OR
     position('vendra_staging_h1_005b8_transition' in v_definition) = 0 THEN
    RAISE EXCEPTION 'Definicao da RPC diferente do esperado; nao aplicar substituicao automatica.';
  END IF;
  v_new := replace(v_definition, 'ERRCODE=''40001''', 'ERRCODE=''PT409''');
  IF v_new = v_definition OR position('ERRCODE=''40001''' in v_new) <> 0 THEN
    RAISE EXCEPTION 'Substituicao PT409 nao validada.';
  END IF;
  EXECUTE v_new; -- CREATE OR REPLACE FUNCTION; preserva corpo, assinatura e grants.
  IF position('ERRCODE=''PT409''' in pg_get_functiondef(v_reg)) = 0 THEN
    RAISE EXCEPTION 'Verificacao apos alteracao falhou; rollback automatico.';
  END IF;
END;
$patch$;
COMMIT;
-- Execute a consulta de leitura separada para validar a substituicao.
