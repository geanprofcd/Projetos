# Funis com rolagem interna e 10.000 cards — 19/10/2026

## Estado vigente

Publicado no original/Railway na v1.62 após validação STAGING com10.000cards.
SQL34 aplicado nos dois destinos, com autorização por ambiente. Flag de produção
ativa;13 verificações funcionais no perfil Comercial hospedado aprovadas.
Design comercial preservado, cabeçalhos fixos, rolagem por mouse/toque/teclado
e barras verticais ocultas. Detalhes da publicação e backup no final deste relatório.

## Estrutura

- RPC `vendra_kanban_window_v1`: leitura, SECURITY INVOKER, search_path vazio,
  EXECUTE somente service_role. Não altera tabelas/RLS/Make/envios.
- Banco calcula contagem e valor total filtrados, ordena recebidas prioritárias,
  atividade mais recente e ID como desempate; transfere até 120 cards por etapa.
- Interface mantém uma janela limitada por coluna, substituindo blocos fora da
  região navegada por espaço de rolagem. Ir ao fim não acumula 10.000 elementos.
- Filtros de busca e responsável executados antes de totais e paginação.
- Polling consulta as janelas atuais, preserva âncora de leitura e foco; pausa
  enquanto o usuário opera seletor/botão. Controle de versão e CSRF mantidos.
- Flag `KANBAN_WINDOW_ENABLED=false` por padrão. Sem carregar tickets da lista
  no modo Funil. Sem cache global de dados/permissões.

## Evidência

10.000 oportunidades reais e exclusivas CODEX-ROLAGEM no STAGING, em funil de
teste com as cinco etapas comerciais. Sem disparos, tickets ou outbox associados
à carga. Navegador Edge real, desktop 1440×900 e viewport móvel 390×844.

Primeira rodada: 12 verificações; segunda: 16, incluindo movimento Comercial,
reconciliação de totais e atualização automática. HTML inicial 381.578 bytes,
carregamento observado 2.294 ms na segunda rodada. Esses valores são uma medição
local, não promessa de latência ou de capacidade de usuários simultâneos.

Busca localizou CODEX-ROLAGEM 09999 fora da janela inicial; rolagem até o fim
chegou ao offset 9875 (9995 cards estavam na primeira etapa nessa rodada), com
até 120 cards por coluna; retorno ao início aprovado. O total geral permaneceu
10.000. Nenhum erro JavaScript nessa rodada. Rodada final de acessibilidade:
17 verificações aprovadas, incluindo End até a última janela e foco preservado.
HTML final 384.538 bytes, carregamento observado 2.554 ms; pequenas diferenças
decorrem das movimentações e alterações das próprias fixtures entre rodadas.

Teste transacional `34_VALIDAR_PAGINACAO_TRANSACAO.sql` aprovado e revertido:
totais, limite solicitado, páginas inicial/intermediária/final, prioridade de
entrada, ignorar saída claimed e nota interna, ACL privada. Fixtures da
transação não permanecem. 74 testes Windows relevantes passaram em 0,935 s.

## Limites e operação

Não foi simulada concorrência de milhares de operadores, nem histórico extenso
em todos os 10.000 cards. A consulta agrega/ordena o conjunto no banco; o teste
comprova paginação e limite do DOM, não crescimento ilimitado do banco.
Para volumes maiores, medir plano SQL, CPU e concorrência antes de prometer SLA.

SQL35 remove somente a nova função. Para reverter, desligar primeiro a flag
e restaurar os arquivos do backup seletivo. Nunca pausar cenários originais.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_kanban_window tests.test_opportunity_bulk tests.test_conversation_order tests.test_ticket_attention
```

Comando já executado autonomamente; não é necessário o usuário repetir.

Carga finalizada:10.000 cards, funil de cinco etapas e cliente exclusivos removidos; portal8014 próprio encerrado e flag STAGING false. Auditoria preservada. PDF real e demais clientes intactos.

## Publicação da paginação no original — v1.62 — 19/10/2026

Após a solicitação “continue” em resposta ao fechamento da v1.61 e ao pedido
específico pendente, aplicada a promoção SQL34/paginação no original.
Migration vendra_kanban_window_v1 em znkjibqcikuigfwfsbjb; função de leitura,
SECURITY INVOKER/search_path vazio, anon/authenticated sem EXECUTE, service_role
permitido. SQL35 não executado. Nenhuma tabela/RLS/Make/envio alterado.

Sete arquivos seletivos, backup output/backups/paginacao-10000-original-20261019.
Sete hashes original/release conferidos; env local/main/base preservados.
KANBAN_WINDOW_ENABLED=true no Railway e perfil privado de operação; deploy
3855a9ee-3175-49aa-b3cd-1cdf81b1930a SUCCESS.

13 verificações funcionais reais Edge com perfil Comercial de Silas aprovadas:
login, funil200/paginação ativa, DOM120 por coluna, barras ocultas/altura limitada,
feed paginado, buscas vazia/existente, etapa inválida422, recarga/sessão,
controles móveis, JavaScript sem erro e recepção de mídias ainda habilitada.
Leitura somente, sem fixtures ou alteração de cards originais, zero envios.
Medição709ms com14cards reais; totais9/4/1/0/0 conferidos em consulta independente.
Não representa nova carga10k em produção ou garantia de concorrência/SLA.
Os17 testes de navegador10k e74Windows anteriores não foram repetidos por esta
promoção inalterada. Reversão somente flag+arquivos seletivos; avaliar SQL35
apenas após desativar consumidores. Não pausar cenários originais.

Solicitação de rolagem interna/paginação concluída. Pendências históricas seguem
separadas no mapa: restauração integral isolada, Meta no portal, Auth,
carga ampliada/concorrência e limpeza finalCODEX; não bloqueiam os serviços ativos.
