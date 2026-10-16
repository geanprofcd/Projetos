# VENDRA: continuidade por Git

Leia docs/VALIDACAO_GIT_STAGING.md para o checkpoint vigente. docs/VALIDACAO_ATUAL.md e outros documentos historicos do payload registram sessoes anteriores e nao comprovam o estado atual.

- Documento Mestre e a referencia de requisitos/decisoes; Git registra codigo e evidencias.
- Desenvolver e validar STAGING antes de promover seletivamente ao principal. Publicar codigo/pacotes nao equivale a homologar ou instalar.
- Preservar .env, .env.h1_005b2, runtime, .vendra-data, sessoes e venv; nao publicar segredos/dados locais.
- SQL, Make, worker e envio sao operacoes separadas. Nao habilitar IA como efeito de instalar codigo.
- Windows: usar Python -X utf8 em testes e startup. Nao mudar assertions para contornar encoding.
- Atualizar Documento Mestre cumulativo nas pastas autorizadas, com links/comandos, evidencias e limites. Nao pausar a cada atualizacao documental.
- Registrar commit aplicado, destino e validacao. Promover somente conjunto homologado com backup, sem mover configuracoes/dados STAGING ao principal.
- Contas CODEX permanecem ate homologacao total; limpar apenas contas de teste identificadas no ledger autorizado.
- Nao criar worktree sem necessidade/autorizacao aplicavel. Este checkout e separado do runtime Windows.

- Autorizacao permanente de 14/10/2026: documentar comandos e executa-los autonomamente quando necessarios no escopo autorizado, sem depender de execucao manual pelo usuario. Registrar acao, destino, revisao, validacao e resultado. Ver docs/COMANDOS_OPERACAO.md.

- Regra explicita de 14/10/2026: tuneis/cenarios do original pertencem a ambiente testado; para STAGING copiar e trabalhar isoladamente, nunca substituir/redirecionar o original. Copia sob demanda Make 6639761 sem webhook Meta e com envio bloqueado; nao reverter historico autorizado automaticamente.

## Continuidade H1-006I (15/10/2026)
Ler docs/VALIDACAO_INTEGRADA_H1_006I.md e ultimo checkpoint docs/VALIDACAO_ATUAL.md. SQL09 e Make Inicial autorizados/aplicados; formulario real ate read automatico aprovado. Seis callbacks IA REV9 originais autorizados/aplicados, resposta operacional unica read automatico; duas reservas bloqueadas canceladas. Handoff backend e oito respostas tardias suprimidas. 33 verificacoes funcionais portal/CRM/permissoes/reinicio aprovadas; fixtures e sessoes proprias limpas. Transporte/filtros/worker desligados e flags removidas. Aplicacao e44d0bb inalterada/218testes anteriores; nao repetir sem mudanca. Proximo: UI operacional WhatsApp e controle humano/IA (portal STAGING atual tem apenas atendimento interno), composicao seletiva producao/migrations, backup/restauracao banco e hosting/HTTPS. Sem promocao principal; nao limpar contasCODEX antes do fim. Fonte/documento em consolidacao H1-006I, Mestre v1.45 previsto; conferir final do checkpoint para hashes/links efetivamente publicados.

## Preservacao obrigatoria do produto original (15/10/2026)
Usuario determinou que o VENDRA original possui UX/UI e design comercial proprios e sua estrutura nao deve ser alterada. Telas, menus, CSS e factories STAGING sao instrumentos de homologacao e NAO devem ser promovidos ao original. Promover backend aprovado integrando-o aos controles/telas/rotas comerciais ja existentes, sem redesenhar ou substituir estrutura/navegacao. STAGING online somente se teste indispensavel exigir; Railway apenas conta autenticada e projeto VENDRA vazio reservado para original depois da homologacao, sem servicos/banco/credenciais. Nao hospedar STAGING por conveniencia.

## H1-006J
Interface /conversas homologada somente no STAGING;235testesWindows e14 verificacoes funcionais reais aprovados. Conta CODEX administrativa especificamente autorizada, depois inativada/sessoes revogadas. Nao promover telas/menus/factories STAGING ao original. Backend original automation_service ainda bloqueiaSupabaseReal; adaptar aos controles Desconectar/Reconectar existentes sem mudar templates/design. Ler docs/VALIDACAO_CONVERSAS_STAGING_H1_006J.md.

## H1-006K em validacao comercial
Ler docs/VALIDACAO_BACKEND_COMERCIAL_H1_006K.md. Backend persistente sob flagdefaultfalse, preview LOCAL8014/copiaSTAGING. Main/router/template/componente comercial semalteracoes; originalfisico intocado. 248testesWindows e6funcionaisreais nosbotoescomerciais, autoriaIA/read/versao/semoutboxnovo. Contaadminnovamenteinativa/sessoesrevogadas/flagremovida. SQL11/rollback12 separados preparados NAO executados; autorizacao especifica equipe/global solicitada pendente. Nao aplicarDDL nemampliarrolesporinstalar. PublicacaoK nao e promocaooriginal; prototipoUIJ nao promover. RailwaysoProjetovazioVENDRAproduction. Originaldisparo/import/lote ainda bloqueiaSupabaseReal; composer/anexos/configglobal devemhomologar antesdehosting. UIoriginalpreservar.

## H1-006L validado
SQL11 aplicado com autorizacao especifica somente STAGING, migration vendra_whatsapp_team_global_control_v1. Adm/Com/Ger ativos, fallbackglobal ai_automation, override explicito prevalece. 249testesWindows e17funcionais reais aprovados, ACLservice_role/SECURITYINVOKER/search_pathvazio. Backendcopia alinhado, originaldesign/main/router/template intactos. Contaadmininativa/Gerencialtemporariorestaurado/sessoesrevogadas/flagsremovidas/ticketencerradohumano, zerooutboxnova/zeroenvios. Ler docs/VALIDACAO_EQUIPE_GLOBAL_H1_006L.md. SQL12rollbacknaoexecutado. Nao promoverdados/templates/factoriesSTAGING. Composer/anexos/padraonovosatendimentos/disparoscomercial/backup/hostingpendentes. Railwaysemdeploy.

## H1-006M validado
Ler docs/VALIDACAO_COMPOSER_ANEXOS_H1_006M.md. ComposerCSRFinputoculto/semredesenho, handofffalhafechadaantespersistir, metadatahumanwhatsappsobflag. 258testesWindows e22funcionaisreais aprovados. BucketprivadoSTAGINGticket-attachments50MiB/publicfalse criado; todasfixtures/anexos/outbox/sessoesproprias limpos. Originalintocado. Naoafirmarenviohumanoprovedor/midia/idempotenciaduploclique/atomicidadetotal/visualnovo. BrowserCDPtimeout. ContinuarMakehumanoutbox/comercialDisparos/import/lote/padraonovosleads/backup/promocaoseletiva/hostingoriginal. SQL11LjaaplicadoSTAGING; semSQLadicionalM. Railwaysemdeploy.

## H1-006N validado
Ler docs/VALIDACAO_HISTORICO_COMERCIAL_H1_006N.md. HistoricoComercialDBrealsobflag, reenvioexplicitobloqueado. 263testesWindows e8funcionaisreaisaprovados,nenhumdisparoalterado/envio/SQL/Make/worker. M22funcionais composer/anexosprivadospassaram,fixtureslimpas. Previewlocal8014PID6428, originaldesign/pasta/banco intactos. MakeVENDRA7cenarios2ativos,REV2Outboxinativo eentradaMeta/IA/enviodiretoantigaconexao;nao e workerhumanohomologado. Proximo contratooutboxhumana/idempotencia+comercialDisparos/import/lote+padraonovosleads+backup/promocaoseletiva/hostingoriginal. Nao parar por documento. Railwaysemdeploy.

M/N entregue: ler checkpoint final em docs/VALIDACAO_ATUAL.md. Fonte85c76ba/pacote1a98808/Mestre148220p,299hashes,263testesWindows,47funcionaisL/M/Ndistintas. Proximo contratooutboxhumana atomico/idempotente; reserve_whatsapp_outbox legado read-then-update/claimed nao e exclusao segura entreworkers(inspecao,naotesteconcorrente). Original/Make/Railwaypreservadosnestaentrega.

## H1-006O reserva/texto humano encerrado
Ler docs/MAPA_HOMOLOGACAO_ORIGINAL.md e docs/VALIDACAO_SAIDA_HUMANA_H1_006O.md. Pasta/bancooriginalpreservados; UIcomercialoriginaltestadaemcopiaSTAGING. SQL13autorizadoaplicado/migrationshuman_reservation_v1+human_text_limit_v1/ACLservice_role;SQL14rollbacknaoexecutado. 18funcionaisreservasinteticas/limpas;8HTTPumvencedor7supressoesaposHTTP1corrigirRemoteProtocolError. Fluxohumanorealcomposer->Make6654745->Meta->delivered fd2aeee1a2844892b0cb11d7d741963f/callbackc4bf4dc8c62d4b18a291a3a48fc56420;replay638055adcf594956972751220c37cf51somentemod1/2/3zeroSend/banco1tentativa. 273testesWindows1,569s. Make6654745inativo/send4false,bridgehumanflagoff/PID29316,exclusivoticketcanceladohumano. OriginalMake10hostsrenovadossomenteaposTunel8013expirar,backupprivado;filtrosSendoriginaisintactos. ProximoH01formidempotente+acionamentoautomatico/media/defaultnovolead,H02Disparoscomerciais,H03backup/promocao,H04hosting. Nao contarregressoescomonovahomologacao,nemenviosobdemandacomoautomacaoportal. Railwaysemdeploy.

## H1-006P
SQL15 autorizado/aplicado somente STAGING. Ler docs/VALIDACAO_COMANDO_HUMANO_H1_006P.md. Texto sem anexos atomico/idempotente:9 banco+8 HTTP reais,280 testesWindows. Fixtures limpas/sessao revogada. Original fisico intacto; Make callbacks STAGING autorizados/filtros bloqueados. Proximo H01 automatico/midia/defaultnovolead. SQL16 nao executado. Mestre149/pacote em consolidacao.

Entrega P publicada f17a868; fonte codigo3c274fc. Mestre149(221p/219historicas) copias verificadas. ZIP30arquivos/103242bytes/downloadHTTP200hashconferido; dryrunzero. Form idempotente fechado; proximo automatico/midia/defaultIA. Ler VALIDACAO_ATUAL/mapa. Original fisico intacto.

## H1-006Q
Automatico humano pelo formulario fechado STAGING:99a4fe8576d14263abb13f25418cd9d3 auto1..6/umSend,116d91286d21487399070e686af6c804 auto1/2/3/zeroSend,delivered370c1d32fe3f42e180fc457adb0f2c6b. Banco1tentativa/WAMIDreal. 287testsWindows2,951s. Make6655228 inativo/filter4false,perfisprivadosrestaurados/bridge30412preview9020 startup; healthfinalnaoexecutado revisaoautomaticaquotas. Original fisico intacto. Ler docs/VALIDACAO_WAKE_AUTOMATICO_H1_006Q.md/mapa. Proximo midia/recuperacao/defaultIA; SQL17/18 preparados NAOaplicados/autorizacaopendente. Fonte/pacote/Mestre150 em consolidacao.
