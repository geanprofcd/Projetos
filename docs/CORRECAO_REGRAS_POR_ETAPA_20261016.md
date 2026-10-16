# Correcao das regras pela etapa atual - 16/10/2026

Este checkpoint substitui a regra de primeira mensagem historica e a espera por delivered/read descritas na v1.54. A falha relatada foi reproduzida pelo estado observado: cards em Novo Lead ja tinham respostas anteriores e continuavam nessa etapa. A validacao anterior nao cobria essa reutilizacao de conversa.

## Contrato vigente

1. Card aberto em Novo Lead recebe uma mensagem nova: vai para Qualificacao, mesmo que o atendimento ja tenha outras mensagens recebidas.
2. Se a resposta ocorre depois de um disparo inicial confirmado desse atendimento, a IA liga antes do retorno da recepcao ao Make. Uma pausa historica anterior ao novo disparo nao bloqueia o novo ciclo. Pausa manual atual, feita depois do disparo, e preservada. A configuracao global de automacao continua obrigatoria.
3. Card aberto em Qualificacao envia uma resposta contendo o link Calendly: vai para Proposta no primeiro aceite do envio pelo provedor, com WAMID. Nao espera delivered/read e nao avanca ao apenas preparar uma resposta pending.
4. Um link enviado enquanto o card esta em Novo Lead nao pula direto para Proposta. Receber outra mensagem em Qualificacao nao move para Proposta. Replay do callback e statuses posteriores nao repetem movimentos nem sobrescrevem uma movimentacao manual.
5. Depois da ativacao, a recepcao e o envio do link nao desligam a IA. O controle manual do Comercial continua prevalecendo. Reservas, versao, janela e autenticacao Make permanecem exigidos; nenhum filtro de seguranca foi removido.

## Executado

SQL28 altera somente quatro funcoes ja existentes: helper de etapa, recepcao, vinculo e status. Sem novas tabelas, RPCs, RLS, permissoes ou deploy de aplicacao. Migration `vendra_commercial_current_stage_v3` aplicada primeiro ao STAGING ljufhqnadzltqbtdaulv, validada, depois ao original znkjibqcikuigfwfsbjb. SQL29 guarda as definicoes imediatamente anteriores; nao executar automaticamente. O filtro Make8 continua route_to_ai=true, consultado depois da recepcao64.

Validacao transacional revertida nos dois bancos: historico antigo + novo disparo + pausa antiga; qualificacao e IA antes do controle; link enviado em Qualificacao; IA permanece ligada; replay e delivered posteriores; bloqueio do salto Novo Lead -> Proposta; pausa atual pelo Comercial; nova entrada respeitando a pausa; idempotencia e ACL. A fixture de disparo e os WAMIDs sao SINTETICOS, sem envio externo.

Onze verificacoes HTTP/SDK STAGING passaram com mensagem historica e disparo sintetico anterior: retorno CONTINUE_TO_AI, qualificacao, desligamento pela rota original do Comercial, proxima entrada humana, movimento manual e quadro. Fixtures e configuracao STAGING restauradas. A aplicacao nao mudou nesta correcao; nao repetir os56 testes anteriores como se fossem novos testes desta entrega.

## Cards afetados

Reconciliacao com backup privado previo e auditoria por card: cinco cards que receberam resposta apos disparo foram movidos de Novo Lead para Qualificacao. Uma IA foi ligada; as outras ja estavam ligadas. Movimentos manuais posteriores a ultima entrada sao excluidos da reconciliacao, e pausas atuais sao preservadas. A correcao nao cria mensagens/outbox, nao reenvia templates nem processa novamente perguntas antigas na IA.

SQL de reconciliacao validado no STAGING em transacao revertida, incluindo um caso que preserva pausa e outro que liga IA elegivel. Executado no original com resultado cards_reconciled=5, ai_activated=1. Estado anterior registrado privadamente em backup_cards_v3_original_20261016.json e no audit_log, acao commercial_v3_repair_backup. Nao publicar o backup privado nem apagar essas auditorias.

## Proxima evidencia real

Foi solicitada uma mensagem nova do numero de teste autorizado87988216094 para conferir pelo Make o envio real do link e o avanco para Proposta. Ate este checkpoint, essa nova rodada ainda nao esta confirmada. Nao declarar entrega real com base no teste SQL sintetico.

Portal: https://vendra-original-production.up.railway.app/atendimentos?view=funil

Nao ha comando necessario para aplicar: banco original ja corrigido. SQL28/29 e o script de reconciliacao sao entregas separadas da copia de arquivos e nao devem ser reaplicados ao baixar o pacote. A pasta original Windows recebe somente esses arquivos e a documentacao; app/design/.env/estado permanecem iguais ao deploy797c35cf.
