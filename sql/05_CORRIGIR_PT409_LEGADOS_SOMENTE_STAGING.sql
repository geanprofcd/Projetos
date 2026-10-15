-- VENDRA H1-005B9 | CORRECAO PT409 LEGADOS (CRM H1-005B4 e simulacoes H1-005B6)
-- APLICAR EXCLUSIVAMENTE NO PROJETO VENDRA-STAGING. NAO EXECUTAR NO BANCO PRINCIPAL.
-- Muda apenas o SQLSTATE de dois conflitos de versao. Nao cria/edita registros.
-- NAO liga Meta, Make, workers, dispatches nem whatsapp_outbox.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '20s';
DO $patch$
DECLARE
  v_signature text;
  v_expected_message text;
  v_target regprocedure;
  v_definition text;
  v_new text;
  v_old_code constant text := 'ERRCODE=''40001''';
  v_new_code constant text := 'ERRCODE=''PT409''';
BEGIN
  IF to_regclass('public.staging_transport_contracts') IS NULL
     OR to_regclass('public.staging_dispatch_simulations') IS NULL
     OR to_regclass('public.opportunity_stage_history') IS NULL THEN
    RAISE EXCEPTION 'Identificacao do STAGING falhou. Nenhuma alteracao.';
  END IF;
  IF (SELECT count(*) FROM public.dispatches) <> 0
     OR (SELECT count(*) FROM public.whatsapp_outbox) <> 0
     OR (SELECT count(*) FROM public.messages) <> 0
     OR (SELECT count(*) FROM public.staging_transport_contracts WHERE transport_enabled) <> 0 THEN
    RAISE EXCEPTION 'Filas reais nao estao vazias, ou transporte habilitado. Pare.';
  END IF;
  IF position('ERRCODE=''PT409''' in pg_get_functiondef(
      'public.vendra_staging_h1_005b8_transition(uuid,text,integer,uuid)'::regprocedure)) = 0 THEN
    RAISE EXCEPTION 'H1-005B8 ainda sem PT409. Pare.';
  END IF;

  FOR v_signature, v_expected_message IN
    SELECT * FROM (VALUES
      ('public.vendra_staging_move_opportunity(uuid,uuid,integer,uuid)',
       'Etapa alterada por outro usuario; atualize a tela'),
      ('public.vendra_staging_change_dispatch_simulation(uuid,text,integer,uuid)',
       'Registro modificado; atualize a pagina')
    ) AS targets(signature, expected_message)
  LOOP
    v_target := to_regprocedure(v_signature);
    IF v_target IS NULL THEN
      RAISE EXCEPTION 'Funcao ausente: %', v_signature;
    END IF;
    IF (SELECT prosecdef FROM pg_proc WHERE oid=v_target::oid) THEN
      RAISE EXCEPTION 'Funcao SECURITY DEFINER inesperada: %', v_signature;
    END IF;
    IF NOT has_function_privilege('service_role',v_target::oid,'EXECUTE')
       OR has_function_privilege('anon',v_target::oid,'EXECUTE')
       OR has_function_privilege('authenticated',v_target::oid,'EXECUTE') THEN
      RAISE EXCEPTION 'Permissoes de RPC divergentes: %', v_signature;
    END IF;
    v_definition := pg_get_functiondef(v_target);
    IF position(v_expected_message in v_definition)=0
       OR position(v_old_code in v_definition)=0
       OR position(v_new_code in v_definition)<>0
       OR (length(v_definition)-length(replace(v_definition,v_old_code,'')))
          <> length(v_old_code) THEN
      RAISE EXCEPTION 'Corpo de funcao divergente (ou ja atualizado): %',v_signature;
    END IF;
    v_new := replace(v_definition,v_old_code,v_new_code);
    EXECUTE v_new; -- CREATE OR REPLACE FUNCTION; assinatura e GRANTs preservados.
    IF position(v_new_code in pg_get_functiondef(v_target))=0
       OR position(v_old_code in pg_get_functiondef(v_target))<>0 THEN
      RAISE EXCEPTION 'Verificacao falhou; rollback automatico: %',v_signature;
    END IF;
  END LOOP;
END;
$patch$;
COMMIT;
