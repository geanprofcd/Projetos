# H1-006B: banco preparado para controle e vinculo

Aplicado exclusivamente em VENDRA-STAGING (`ljufhqnadzltqbtdaulv`), apos autorizacao especifica do usuario, em 14/10/2026 (Brasilia). Migration: `vendra_whatsapp_control_bind_v1`.

## Alteracao aplicada

Quatro RPCs SECURITY INVOKER, search_path vazio e EXECUTE somente service_role: control, mode, ai_prepare e bind. Indice unico parcial de WAMID na outbox. Nao altera RLS, habilita IA, worker ou envio. Arquivos 03/04/05 em sql sao aplicacao, teste transacional descartavel e rollback manual separado.

O controle exige configuracao global, modo IA, atendimento aberto e mensagem recente dentro de 24 horas. Troca de modo exige administrador ativo e versao esperada. Preparacao reserva uma unica saida por entrada: repeticoes nunca reautorizam envio; payload divergente gera conflito. Entrada mais recente e handoff anterior a autorizacao suprimem respostas antigas.

O vinculo exige token da reserva, impede WAMID em outra saida e reconcilia status previamente recebidos. Confirmacao sent do conector nao comprova delivered/read, que exigem eventos Meta. Uma mensagem ja autorizada/em voo pode chegar depois do handoff; a troca de modo cancela apenas pendencias ainda nao reservadas. Nao prometer cancelamento de envio aceito pelo provedor.

## Evidencia real desta entrega

27 verificacoes executadas no PostgreSQL remoto, em transacao encerrada com ROLLBACK. Incluem ator nao administrador, versao antiga, no-op de modo, janela encerrada, entrada divergente, duplicata sem nova autorizacao/saida, resposta conflitante, entrada mais recente, handoff, token incorreto, status antes do vinculo, reconciliacao delivered/read com timestamp original, repeticao do vinculo, troca/colisao de WAMID, atendimento finalizado e ACL das quatro funcoes. Todas aprovadas.

Teste de ativacao global existiu somente dentro da transacao, invisivel a outros processos e revertido. Consulta posterior: zero clientes/atendimentos/outboxes da fixture, configuracao whatsapp_bridge ausente, mensagem real H1-006A preservada e migration registrada. Nao foram enviadas mensagens nesta rodada. Testes desta etapa sao transacionais sequenciais; concorrencia da nova preparacao ainda precisa ser verificada por chamadas independentes.

## Estado e proxima etapa

Ponte HTTP 8012 e cenarios Make continuam no contrato H1-006A; IA desabilitada. Nenhuma rota HTTP de IA/vinculo foi publicada nesta entrega. Os 170 testes Windows da entrega anterior continuam sendo evidencia de H1-006A, nao de um fluxo IA H1-006B completo.

Proxima etapa concreta: implementar endpoints autenticados com escopo de destinatario/entidade, testar concorrencia e passagem para humano, depois adaptar os modulos Make e homologar o fluxo real. Nao promover ao principal nem afirmar homologacao integral. Checkout da nuvem sem acesso comprovado nesta sessao Windows.

## Comandos e operacoes

Nao e necessario reiniciar o aplicativo: nenhum codigo Python foi alterado. Nao executar novamente 03 no STAGING ja migrado (CREATE FUNCTION/INDEX nao idempotentes). Conferir o registro em Database / Migrations do projeto correto. O arquivo 04 pode ser executado no SQL Editor exclusivamente desse projeto; termina com ROLLBACK. 05 e rollback preparado, nao executado, e exige consumidores H1-006B desligados.

Para validar a integridade do pacote Windows: `Get-FileHash -LiteralPath '.\VENDRA_H1_006B_SQL_STAGING_20261014.zip' -Algorithm SHA256`. Extrair em pasta nova, conferir manifest.json e manter os arquivos SQL separados de qualquer instalacao automatica. Configuracoes, sessoes e credenciais ficam fora desta entrega.
