# H1-006D: concorrencia e copia isolada

14/10/2026, Brasilia. Usuario esclareceu que os tuneis antigos pertencem ao VENDRA original programado/testado: trabalhar no STAGING copiando, nunca substituindo. Nenhum modulo do original foi alterado nesta rodada. REV9 6534261 permaneceu ativo e com lastEdit 2026-10-15T00:46:33.650Z (14/10 21:46:33 Brasilia). Alteracoes historicas 64/83 nao foram revertidas automaticamente. Original 8010 e seus tuneis/processos preservados.

## Concorrencia real

21 verificacoes remotas com oito clientes/conexoes SDK independentes aprovadas: uma troca de modo por CAS e sete conflitos; incremento/auditoria unicos; oito preparacoes com uma autorizacao, sete duplicatas suprimidas, uma resposta IA e uma outbox; payload conflitante recusado; handoff incrementa versao/cancela pendencia e mensagem; reserva em voo preservada; oito respostas tardias bloqueadas; delivered/read antes do vinculo pendentes; oito vinculos terminam em read sem regressao e reconciliam dois eventos uma unica vez; consistencia mensagem/outbox; zero pendencias; restauracao/limpeza e mensagem real anterior preservada.

A flag global foi criada temporariamente com identificador exclusivo da fixture, somente depois de conferir ponte 8012 ai_enabled=false/external_sends_enabled=false e portal 8011 simulation_only=true/external_sends_enabled=false. Nenhum agente/worker/provedor foi acionado. A configuracao foi removida com conferencia do valor esperado. Consulta independente confirmou zero configuracoes whatsapp_bridge, clientes/eventos/outboxes da fixture. Nao houve SQL DDL ou envio nesta rodada. Contas CODEX de homologacao permanecem ate conclusao total.

## Copia Make preservando original

Cenario 6639761: CODEX-STAGING | VENDRA REV9 | Copia isolada sem webhook | H1-006D, pasta Base de Testes. 23 modulos copiados/adaptados: entrada sob demanda com campos explicitos em vez de webhook Meta; roteamento/prompt/arquivos/conexoes existentes preservados. Callbacks apontam exclusivamente a ponte STAGING; respostas usam base64, UUID da entrada e versao; confirmacao exige token de reserva e metadata. Tres modulos de envio possuem filtro constante false=true, independente das demais autorizacoes. Nenhuma assinatura/webhook Meta criada ou compartilhada. Copia terminou inativa.

A tentativa de clonagem pela UI foi cancelada ao exigir webhook substituto. A copia foi criada pela API. Primeiro teste falhou antes de executar modulos com BlueprintValidationError: Missing expect specification for field module_78_query. Editor Make regravou apenas o modulo Knowledge da copia e o cenario, preservando arquivo de conhecimento e escolha pelo agente. Reteste a0c7b553e7f24735819af848844325f5 aprovado: executaram somente 71/64/99; entrada ja persistida deduplicada, IA/envio nao executados. Nao e teste de nova recepcao Meta ou de resposta completa.

https://us2.make.com/292724/scenarios/6639761/edit
https://us2.make.com/292724/scenarios/6639761/logs/a0c7b553e7f24735819af848844325f5

## Codigo e limites

Ponte revalida o telefone retornado na reserva antes de devolver authorized=true, protegendo contra troca de telefone entre leitura e preparacao. Se divergir, a autorizacao nao e devolvida; a reserva pode permanecer claimed e exige conciliacao, sem envio automatico. Token de reserva usa SecretStr e nao aparece no repr do modelo. Duas novas verificacoes locais; 31 testes focados e 188 de regressao Windows aprovados (copia limpa, 2.120s). Ponte 8012 reiniciada com o mesmo perfil desligado.

Pendente: exercitar as rotas de resposta/vinculo na copia com gates de teste controlados, validar agente/arquivos e handoff no fluxo completo, e somente entao testar envio autorizado. Cenario de Disparo Inicial ainda requer copia propria. Nenhuma promocao ao principal. Copia sob demanda nao substitui a homologacao de webhook real.

Comandos de sincronizacao/testes em docs/COMANDOS_OPERACAO.md. Nenhuma execucao manual do usuario e necessaria para aplicar esta entrega ja realizada na copia Windows. Pacote de codigo e operacao Make sao entregas separadas; credenciais, headers privados e payloads pessoais ficam fora do Git/pacote.
