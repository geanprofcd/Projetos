# Mapa de homologação do VENDRA original

Atualizado em 16/10/2026. Este é o quadro de pendências; o histórico detalhado permanece no Documento Mestre e em VALIDACAO_ATUAL.md. Regressão repetida após alteração não conta como nova funcionalidade homologada.

## Onde estamos trabalhando

- Código e dados de desenvolvimento: cópia Windows/STAGING. A prévia8014 usa as telas comerciais existentes, com ajustes de backend e inputs invisíveis de segurança; não substitui o design pelo protótipo8011.
- Pasta e banco do original: preservados, sem promoção nesta sequência. O original será publicado depois da homologação do conjunto necessário.
- Make: REV9 original6534261 e Disparo Inicial original6561096 receberam os ajustes anteriormente autorizados para testar contra STAGING. Nesta rodada, somente os dez endereços de callbacks foram renovados porque o túnel expirou; mapeamentos, conexões e bloqueios de envio preservados. Cenário humano de teste6654745 criado separadamente, sob demanda, e deixado inativo/bloqueado ao finalizar.

## Pendências encerradas, sem repetir salvo mudança relevante

| Comportamento | Evidência funcional | Situação |
|---|---|---|
| Recepção Meta, IA, resposta e status reais | H1-006I, execuções reais de entrada/IA/read | Aprovado no STAGING |
| Template inicial pelo portal e status automático | H1-006I, reserva/vínculo/entrega/read | Aprovado no caminho individual STAGING |
| Controle comercial humano/IA e configuração global | H1-006K/L, botões existentes, perfis e ACL | Aprovado no STAGING |
| Composer: gravação, handoff e anexos privados | H1-006M, HTTP/Storage/checagem de acesso | Aprovado para persistência; transmissão de mídia pendente |
| Histórico comercial de Disparos | H1-006N, registros e Lido reais | Leitura aprovada; criação/importação/lote pendentes |
| Reserva exclusiva e transmissão de texto humano | H1-006O: oito reservas/um vencedor, envio real e delivered, replay sem WhatsApp | Aprovado com acionamento sob demanda no cenário de teste |
| Texto humano atômico e formulário idempotente | H1-006P: nove verificações de banco e oito HTTP comerciais; oito comandos/uma saída | Aprovado para texto sem anexos; acionamento automático pendente |
| Acionamento automático de texto humano pelo formulário | H1-006Q: dois POSTs, duas execuções auto, um Send/uma tentativa/WAMID, delivered automático | Aprovado no STAGING, cenário e perfis novamente bloqueados |

## Quatro frentes restantes, com critério de encerramento

| ID | Pendência | Critério para fechar |
|---|---|---|
| H01 | Completar automação da conversa comercial | Mídia com vínculo e recuperação por item; recuperação de falhas e padrão IA em novos atendimentos coerente com a configuração. Formulário de texto idempotente fechado em P e acionamento automático fechado em Q |
| H02 | Completar Disparos comerciais | Criação individual, importação, revisão e lote usando as telas existentes e persistência real; sem duplicação e com limites/permissões/recuperação comprovados |
| H03 | Preparar promoção e recuperação do original | Conferir diferenças/migrations/configuração, backup e restauração testados; pacote seletivo homologado; preservar design, credenciais e dados; SQL e Make tratados separadamente |
| H04 | Publicar e validar o original | Hospedagem do original finalizado, HTTPS/callbacks estáveis, persistência após reinício e fluxo completo no servidor; só então limpeza definitiva CODEX |

Uma falha material descoberta entra na frente correspondente; não abrir outro ciclo genérico de testes. Relatar qual pendência avançou, qual prova falta e o que foi efetivamente aplicado. Não usar contagem de testes como porcentagem de conclusão.

## Por que parecia um círculo

Parte do trabalho validou primeiro contratos em telas de teste, e outra parte adaptou a persistência às telas comerciais existentes. As duas etapas ficaram pouco distintas nos relatos. Regressões foram repetidas corretamente após alterações, mas não representam novas etapas concluídas. Túnel temporário expirado e falha de protocolo sob concorrência causaram retrabalho técnico. A partir deste quadro, reaproveitar evidências e repetir somente o fluxo afetado por alteração/falha.

O texto humano O fechou uma lacuna concreta: antes havia gravação/outbox sem comprovação de transmissão; agora há envio real e delivered, com uma única tentativa mesmo após replay. Isso não transforma o acionamento manual de teste em automação pronta do produto.
