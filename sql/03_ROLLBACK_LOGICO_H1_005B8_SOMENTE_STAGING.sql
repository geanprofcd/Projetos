-- REFERENCIA DE ROLLBACK LOGICO - NAO EXECUTAR SEM REVISAO E BACKUP.
-- Desativar somente rotas da H1-005B8 voltando tools/staging_start.py ao backup.
-- Nao apagar tabela, contratos, eventos ou auditores: retencao para analise.
-- Contrato ja e IMUTAVEL quanto a transporte_enabled = false (CHECK).
-- Em caso de erro grave, interromper a aplicacao de STAGING na porta 8011.
SELECT 'Rollback logico: nao executar DDL ou DELETE. Reverter arquivos pelo backup.' AS instrucao;
