# Mapa de homologação do VENDRA original

Atualizado em 16/10/2026. Este é o quadro de pendências; o histórico detalhado permanece no Documento Mestre e em VALIDACAO_ATUAL.md. Regressão repetida após alteração não conta como nova funcionalidade homologada.

Prioridade atual determinada pelo usuário: publicar o original com o design preservado e validar somente o indispensável para colocá-lo online. Mídia, lote, melhorias e homologação ampliada ficam para depois; não são bloqueios automáticos da primeira publicação. Primeira release usa a base comercial original, não promove automaticamente o snapshot STAGING. Critérios imediatos: configuração real e isolada, primeiro administrador, build/start, login/permissões, persistência básica e reinício no servidor. GitHub é público; oito arquivos do original ainda não publicados devem seguir por upload privado ao Railway.

## Onde estamos trabalhando

- Código e dados de desenvolvimento: cópia Windows/STAGING. A prévia8014 usa as telas comerciais existentes, com ajustes de backend e inputs invisíveis de segurança; não substitui o design pelo protótipo8011.
- Original publicado no Railway com base comercial e design preservados. Cinco arquivos de hosting adicionados; SQL19 de compatibilidade autorizado/aplicado, administrador e Comercial reais criados. Aplicação não recebeu snapshot STAGING. Login, persistência e reinício hospedados aprovados; integrações ainda STAGING.
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
| Texto humano atômico e formulário idempotente | H1-006P: nove verificações de banco e oito HTTP comerciais; oito comandos/uma saída | Aprovado texto; automático fechado Q |
| Acionamento automático de texto humano pelo formulário | H1-006Q: dois POSTs, duas execuções auto, um Send/uma tentativa/WAMID, delivered automático | Aprovado no STAGING, cenário e perfis novamente bloqueados |
| Padrão inicial de novo atendimento | H1-006R: quatro configurações, handoff/replay preservados, transação revertida/fixtures0 | Aprovado STAGING; SQL17 aplicado/SQL18 não executado |

## Quatro frentes restantes, com critério de encerramento

| ID | Pendência | Critério para fechar |
|---|---|---|
| H01 | Melhorias da conversa após primeira publicação | Mídia com vínculo/status por item e recuperação de falhas. Texto idempotente P, automático Q e padrão inicial R fechados no STAGING; promoção de integração separada da publicação da base original |
| H02 | Melhorias de Disparos após primeira publicação | Criação individual, importação, revisão e lote comerciais pendentes; escopo ampliado posterior conforme prioridade do usuário |
| H03 | Preparar promoção e recuperação do original | Conferir diferenças/migrations/configuração, backup e restauração testados; pacote seletivo homologado; preservar design, credenciais e dados; SQL e Make tratados separadamente |
| H04 | Publicar e validar o original | Hospedagem do original finalizado, HTTPS/callbacks estáveis, persistência após reinício e fluxo completo no servidor; só então limpeza definitiva CODEX |

Uma falha material descoberta entra na frente correspondente; não abrir outro ciclo genérico de testes. Relatar qual pendência avançou, qual prova falta e o que foi efetivamente aplicado. Não usar contagem de testes como porcentagem de conclusão.

## Por que parecia um círculo

Parte do trabalho validou primeiro contratos em telas de teste, e outra parte adaptou a persistência às telas comerciais existentes. As duas etapas ficaram pouco distintas nos relatos. Regressões foram repetidas corretamente após alterações, mas não representam novas etapas concluídas. Túnel temporário expirado e falha de protocolo sob concorrência causaram retrabalho técnico. A partir deste quadro, reaproveitar evidências e repetir somente o fluxo afetado por alteração/falha.

O texto humano O fechou uma lacuna concreta: antes havia gravação/outbox sem comprovação de transmissão; agora há envio real e delivered, com uma única tentativa mesmo após replay. Isso não transforma o acionamento manual de teste em automação pronta do produto.

## Checkpoint de publicação
Base comercial online: https://vendra-original-production.up.railway.app/login. Login/logout, páginas, gravação e persistência após reinício aprovados; Silas Comercial com bloqueios de áreas administrativas validado. H04 hospedagem básica fechada; callbacks/fluxo WhatsApp de produção continuam pendentes. Ler PUBLICACAO_ORIGINAL_RAILWAY.md. Domínio Railway mantido por decisão do usuário.
