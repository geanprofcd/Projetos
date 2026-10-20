# Funis com rolagem interna e 10.000 cards — 19/10/2026

## Estado vigente

Implementado na cópia STAGING, com desenho comercial preservado: cinco colunas,
cabeçalhos fixos, rolagem por mouse/toque/teclado e barras verticais ocultas.
O scroll simples com 80 cards foi validado e publicado no original; a evolução
para janelas de 120 cards depende de SQL34 e flag próprios no destino.
SQL34 autorizado e aplicado **somente STAGING**. Promoção desse SQL ao original
solicitada separadamente; não presumir aplicação pela presença do arquivo.

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
