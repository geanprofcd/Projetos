# Mapa de homologação do VENDRA original

## Desenvolvimento v1.60 - 19/10/2026 (somente STAGING)

Recepção de mídia implementada e validada com52 testes Windows,18 verificações funcionais e quatro arquivos próprios pela cópia Make. Ainda falta evento real do WhatsApp e promoção/SQL autorizados para o original. Produção permanece na v1.59, envio de mídias/texto/IA/disparos preservados; os três cenários originais não foram pausados. Ler [VALIDACAO_RECEPCAO_MIDIA_20261019.md](VALIDACAO_RECEPCAO_MIDIA_20261019.md). Não contar upload/download de arquivo próprio como recepção real de lead.


## Estado vigente v1.59 - 18/10/2026

Envio de mídias liberado para clientes reais após autorização específica. PNG/PDF/MP3/MP4 aceitos em teste real STAGING; PDF delivered pelo portal original. Quatro arquivos backend e SQL30 promovidos seletivamente. Deploy abca256d-5fbc-4d3a-8fa0-a158f45ede37. Os três cenários originais Make permanecem ativos: não pausar para desenvolvimento/testes. Recebimento de mídias e gestão Meta pelo portal continuam pendentes. Evidência, limites, segurança e reversão: [VALIDACAO_MIDIA_WHATSAPP_20261016.md](VALIDACAO_MIDIA_WHATSAPP_20261016.md). Seções anteriores a este checkpoint são históricas; pendência antiga de envio de mídia está encerrada.


## Quadro vigente após levantamento de paridade - 16/10/2026

A matriz atual está em [PARIDADE_ORIGINAL_ONLINE_20261016.md](PARIDADE_ORIGINAL_ONLINE_20261016.md). Código original Windows/release:130 arquivos app iguais/nenhum faltante;104 rotas nativas catalogadas/15 páginas administrativas200. Hospedagem, conversas/IA/humano, disparos individuais/listas, funil completo, Calendly e alertas já integrados. Anexos privados e convite por link sem SMTP integrados nesta rodada, com testes reais STAGING e original. Pendente funcional: transmissão de mídia WhatsApp com vínculo/status por arquivo e gestão Meta no portal com token apropriado. Não contar exemplos demo como cadastros reais a importar, nem leituraHTTP200 como homologação de todas as ações. Recuperação integral/carga ampliada permanecem sem comprovação. Checkpoints abaixo são históricos; não reabrir blocos já encerrados sem alteração relevante.

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

## Integração original hospedada e conversas liberadas - 16/10/2026
SQL21 original autorizado/aplicado, dez callbacks Make migrados para Railway; IA e texto humano reais concluíram com WAMID, tentativa única e READ. Após autorização explícita, IA e respostas humanas estão ligadas para clientes reais. Não dependem de túnel/Windows. Disparo individual preparado, envio ainda bloqueado, autorização de teste temporário solicitada. Importação/lote/mídia ficam posteriores. Ler docs/OPERACAO_ORIGINAL_ONLINE.md para evidências, limites, comandos e pendências atuais; checkpoints anteriores descrevem o estado histórico, não o atual.


## Disparo individual original concluído - 16/10/2026
Autorização específica recebida; um POST real do formulário original retornou303/sent. Make6561096 execução8ae8ba54b8e5478a8d1fcbed9e04ce31, cinco módulos uma vez, um template enviado. Banco original: dispatch5eb1de1d-7e9c-4da1-bd3a-577e9e2cf6d8, WAMID presente, status delivered, tentativa1, transporte200, vínculos cliente/atendimento/mensagem/oportunidade completos, etapa Novo Lead. Canal dispatch_bridge/dispatches desligado e filtro Make novamente constantefalse ao concluir. IA e make_outbox continuam true conforme liberação regular. Sem lote/importação. Próximo: consolidar promoção seletiva/pacote e recuperação mínima; não repetir o template nem solicitar novo teste para a mesma migração.


## Listas, quantidade e custos - 16/10/2026
Disparo individual regular liberado após autorização específica. SQL23/listas aplicado STAGING e original mediante autorização específica; duas tabelas/quatro funções, RLS/ACLbackend. STAGING:36 testes relevantes, SQL transacional/revertido incluindo retomada,14HTTP reais com transporte suprimido/fixtures limpas, mais rodada real automática de uma mensagem pelo Make6661208 execução de9b565ab0fa4aa8870b9e2687e50b0b/WAMID/sent. Não alegar delivered/read nessa rodada. CopyMake inativa/filtrofalse, flagsSTAGING restauradas, túnel temporário desta rodada encerrado. Original:deploy8bd7be32-dcf6-48dc-969d-a65c0ee24562SUCCESS, importação/quantidade0rejeitada/progresso/JS conferidos sem novos envios; fixturelista própria limpa. Individual+listas+IA+humano ativos, filaoriginal vazia até usuário iniciar; logs observados sem erro de worker. Pastaoriginal atualizada seletivamente8arquivos/backup listas-original-20261016; main/base/.env preservados. Pacote16arquivos/hash2cf603e9d073ba8671b75f339d7cae7834809b6ea430caef2ec12e79991f246f, ainda em publicação. Mestre153225p/223históricas. Senha admin alterada a pedido e login validado, valor omitido. Custos mensais documentados com câmbio hipotético5,50, MetaBRL, Make reservado, Railway10USD eSupabasePro25USD; não são contratos/fatura/carga20mil homologada. Ler docs/VALIDACAO_LISTAS_ORIGINAL_20261016.md e docs/CUSTOS_VENDRA_20261016.md. CODEX/evidências reais preservados; mídia/SMTP/melhorias futuras posteriores.


## Atualização19/10 — v1.61
Recepção de mídia: SQL32 original autorizado/aplicado, backend e ramo85/86+handlers87/88 ativos no Railway/REV9, healthinboundtrue. Teste automático de novo arquivo solicitado/pendente. Scroll interno sem barra vertical publicado. Evolução10.000cards aprovadaSTAGING (17verificações/74Windows), SQL34somenteSTAGING; promoçãoSQL34originalaguardaautorizaçãoespecífica. Não pausar cenários originais. Ver VALIDACAO_ROLAGEM_FUNIS_20261019.md e VALIDACAO_RECEPCAO_MIDIA_20261019.md.

### Recepção automática original concluída — estado mais recente19/10/2026
Run be3add398da242f18a94b5033408e40b, iniciado00:08:11.930Z20/10 (=21:08Brasília19/10), AUTO, sucesso4,603s/3operações/3créditos. Módulos71/85/86, uma invocação cada, zero erros; nenhum módulo de envio. Callback202accepted/media_storedtrue/duplicatefalse. Nove verificações reais no original: remetente/conta, WAMID gravado, vínculo único, hashMeta, loginadministrativo hospedado, chat, feed, download privado e arquivo completoSHA256. Evidência real preservada. Recepção automática hospedada homologada; solicitação de arquivo final atendida. Pendência separada permaneceSQL34original/paginação10k, não autorizada ainda.
