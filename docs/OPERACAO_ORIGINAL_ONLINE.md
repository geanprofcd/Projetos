# VENDRA original online - integração e operação

Atualizado em 16/10/2026. Portal: https://vendra-original-production.up.railway.app/login

## Situação efetiva

O portal comercial, o banco original e os callbacks WhatsApp estão hospedados. O fluxo de conversas funciona com Railway, Supabase, Make e Meta, sem depender do Windows ou de túnel temporário. Os arquivos SQL antigos não são carregados na execução: as funções aplicadas ficam no banco. A máquina local continua sendo um local de desenvolvimento e backup.

Após autorização específica do usuário, IA e respostas humanas foram liberadas para clientes reais. `ai_automation` e `make_outbox` estão habilitados no original. O modo humano de atendimentos existentes permanece preservado. Disparos, importação e lote não foram incluídos nessa autorização.

## Evidências reaproveitadas e migração

- SQL21 aplicado exclusivamente no original após autorização: 12 funções homologadas, EXECUTE somente service_role, sem copiar dados STAGING. SQL22 de reversão preparado, não executado.
- Dez callbacks dos cenários originais Make foram migrados para HTTPS no Railway com segredo próprio. Cenários: REV9 6534261 e Disparo Inicial 6561096. Saída humana hospedada: 6659974.
- IA real hospedada: execução `07e22a12e2c042068f85cf5ff5f67330`; uma tentativa, WAMID e status READ no banco original.
- Texto humano real pelo formulário: execução `b1e46f9308ae4362a04e0851103a906d`; um envio, uma tentativa, WAMID e READ no banco original. Evidências reais preservadas.
- Login, permissões Comercial, gravação e persistência após reinício já validados na primeira publicação. Não é necessário repetir esses blocos sem alteração relevante.
- Escopo de destinatários foi liberado explicitamente para conversas de produção. Segredo, conta Meta, telefone válido, reservas e políticas de envio permanecem obrigatórios. Quinze testes distintos dos controles de destinatário/wake passaram após a alteração.

O design comercial permanece preservado. Alterações em formulários são campos ocultos de segurança/idempotência e controles de funções indisponíveis; não houve substituição de layouts pelo protótipo STAGING. Nenhum snapshot integral, credencial ou dado de simulação foi promovido.

## Disparo individual: próximo bloco

Adaptador do formulário comercial preparado a partir do contrato já homologado no STAGING. Vinte e três testes relevantes de contrato/histórico passaram; uma conferência HTTP da tela original confirmou o nonce oculto e bloqueio antes de RPC/transporte quando o canal está desligado. Isso não equivale a envio funcional hospedado.

Release privada `fbbfb26f-0f6e-4e70-b893-ea3412a3bd41` enviada ao Railway. Transporte tem segredo próprio e destinatário de teste restrito. Configurações `dispatch_bridge`/`dispatches` permanecem desligadas e o template Make permanece bloqueado. Autorização específica de um único teste temporário foi solicitada, separadamente da liberação de conversas. Não anunciar Disparo homologado no original antes de WAMID/entrega real pelo portal.

## O que falta

1. Conferir o deploy do adaptador e, com autorização específica, executar um disparo individual pelo portal, conferir vínculo/status e bloquear novamente ao concluir.
2. Consolidar promoção seletiva na pasta original local, backup, hashes e pacote de continuidade. Não expor os arquivos privados do produto no GitHub público.
3. Registrar recuperação mínima e acompanhar prazo/saldo do trial Railway. Nenhum plano pago ou domínio próprio contratado.
4. Encerrar as contas CODEX somente quando o escopo de homologação acordado estiver concluído; preservar administrador e Comercial reais.

Mídia, importação, lote, SMTP/convites e melhorias ficam para uma fase posterior, conforme prioridade do usuário. Não são critérios novos para impedir a operação das conversas já liberadas.

## Comandos de acompanhamento

Não há comando necessário para usar o portal. Manutenção requer token privado já carregado, sem incluí-lo em arquivos públicos:

```powershell
Invoke-RestMethod https://vendra-original-production.up.railway.app/health
Invoke-RestMethod https://vendra-original-production.up.railway.app/callbacks/health
railway deployment list --project caad2a82-373d-441c-8403-f3a7903a264f --environment production --service vendra-original --limit 1 --json
railway logs --project caad2a82-373d-441c-8403-f3a7903a264f --environment production --service vendra-original --lines 30
```

Para publicar, usar somente o caminho absoluto da release privada limpa e conferida, com `--path-as-root`; nunca subir a pasta STAGING ou arquivos `.env`, estado e runtime. SQL e ativação Make são operações separadas da entrega de arquivos. Python Windows deve usar `-X utf8`.

## Disparo individual original concluído - 16/10/2026
Autorização específica recebida; um POST real do formulário original retornou303/sent. Make6561096 execução8ae8ba54b8e5478a8d1fcbed9e04ce31, cinco módulos uma vez, um template enviado. Banco original: dispatch5eb1de1d-7e9c-4da1-bd3a-577e9e2cf6d8, WAMID presente, status delivered, tentativa1, transporte200, vínculos cliente/atendimento/mensagem/oportunidade completos, etapa Novo Lead. Canal dispatch_bridge/dispatches desligado e filtro Make novamente constantefalse ao concluir. IA e make_outbox continuam true conforme liberação regular. Sem lote/importação. Próximo: consolidar promoção seletiva/pacote e recuperação mínima; não repetir o template nem solicitar novo teste para a mesma migração.


## Consolidação final desta entrega
Pasta original Windows atualizada seletivamente:15arquivos, backup output/backups/conversas-original-20261016-125956. Main/base/.env preservados por hash. Extração de recuperação conferiu19arquivos do pacote; isso não é restauração de banco nem reversão de provedor. Histórico Git privado da release:32ae7b1ac4cbcdd892e2f28be48db29c713d2658, sem remoto. Fonte pública sincronizada em desenvolvimento/vendra-staging, checkout permanente atualizado. Pacote SHA256:5dbcd9e781e29e9156e540bab1a0142c8e81634999ffd0b4b3f50aa14dba6195. Mestre152:224p/222históricas, cópias Downloads e Downloads/Automações iguais. Continuidade: manter os segredos privados, preservar banco original e evidências reais, acompanhar trialRailway. A reversão de aplicação deve usar deployment anterior ou backup seletivo; não executar SQL22 automaticamente. Não declarar recuperação integral de banco testada. CODEX permanece até encerramento do escopo acordado.
Entrega: https://github.com/geanprofcd/Projetos/blob/b35e2eb667f1ca6047129a28b7ea4365992f1431/deliveries/20261016/CONVERSAS_ORIGINAL/INSTRUCOES.md
Download: https://raw.githubusercontent.com/geanprofcd/Projetos/b35e2eb667f1ca6047129a28b7ea4365992f1431/deliveries/20261016/CONVERSAS_ORIGINAL/VENDRA_CONVERSAS_ORIGINAL_20261016.zip


## Listas, quantidade e custos - 16/10/2026
Disparo individual regular liberado após autorização específica. SQL23/listas aplicado STAGING e original mediante autorização específica; duas tabelas/quatro funções, RLS/ACLbackend. STAGING:36 testes relevantes, SQL transacional/revertido incluindo retomada,14HTTP reais com transporte suprimido/fixtures limpas, mais rodada real automática de uma mensagem pelo Make6661208 execução de9b565ab0fa4aa8870b9e2687e50b0b/WAMID/sent. Não alegar delivered/read nessa rodada. CopyMake inativa/filtrofalse, flagsSTAGING restauradas, túnel temporário desta rodada encerrado. Original:deploy8bd7be32-dcf6-48dc-969d-a65c0ee24562SUCCESS, importação/quantidade0rejeitada/progresso/JS conferidos sem novos envios; fixturelista própria limpa. Individual+listas+IA+humano ativos, filaoriginal vazia até usuário iniciar; logs observados sem erro de worker. Pastaoriginal atualizada seletivamente8arquivos/backup listas-original-20261016; main/base/.env preservados. Pacote16arquivos/hash2cf603e9d073ba8671b75f339d7cae7834809b6ea430caef2ec12e79991f246f, ainda em publicação. Mestre153225p/223históricas. Senha admin alterada a pedido e login validado, valor omitido. Custos mensais documentados com câmbio hipotético5,50, MetaBRL, Make reservado, Railway10USD eSupabasePro25USD; não são contratos/fatura/carga20mil homologada. Ler docs/VALIDACAO_LISTAS_ORIGINAL_20261016.md e docs/CUSTOS_VENDRA_20261016.md. CODEX/evidências reais preservados; mídia/SMTP/melhorias futuras posteriores.

# Atualizacao comercial de 16/10/2026

Funil original completo e regras de primeira resposta/Calendly/ordenacao aplicadas. Deploy final797c35cf-6a1b-4237-ad3b-f4035bb36b99. Ler docs/VALIDACAO_FUNIS_COMERCIAL_20261016.md; checkpoint vigente sobrepoe pendencias historicas abaixo. SQL25/26 ja executados; SQL27 apenas reversao. Nao reaplicar por copiar o pacote. Comercial preserva controle humano e movimentos manuais; nenhuma campanha iniciada nesta entrega.

