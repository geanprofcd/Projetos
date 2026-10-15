# H1-006H — Portal preparado, envio desativado

Código já aplicado e tela carregada no Windows STAGING; nenhuma reinstalação manual necessária nesta sessão. 218 testes passaram em 1,178 s; login Comercial, menu e histórico conferidos no navegador. SQL09/10 NÃO executados e cenário Disparo Inicial original ainda NÃO alterado nesta etapa. Envio pelo formulário ainda NÃO homologado. Autorização específica para SQL09 no STAGING e ajuste Make6561096 solicitada e pendente; não executar por efeito da instalação.

Fonte: https://github.com/geanprofcd/Projetos/commit/e44d0bbdb360270385119edc41108c7375bd44ac
Validação: https://github.com/geanprofcd/Projetos/blob/desenvolvimento/vendra-staging/docs/VALIDACAO_COMANDO_PORTAL_STAGING.md
Tela local: http://127.0.0.1:8011/disparos/envio

Treze arquivos gerenciados, hashes, instalador com backup. Em outra cópia STAGING preparada, extrair em pasta nova e conferir:

```powershell
Get-FileHash -LiteralPath '.\VENDRA_H1_006H_PORTAL_PREPARADO_20261015.zip' -Algorithm SHA256
Expand-Archive -LiteralPath '.\VENDRA_H1_006H_PORTAL_PREPARADO_20261015.zip' -DestinationPath '.\H1_006H_CONFERENCIA'
powershell -NoProfile -ExecutionPolicy Bypass -File '.\H1_006H_CONFERENCIA\tools\aplicar_callbacks_staging.ps1' -Destino 'CAMINHO_DA_COPIA_STAGING'
```

Último comando é dry-run. -Aplicar instala apenas arquivos diferentes, com backup e rollback.json; não altera .env, estado, venv, serviços, SQL ou Make. Rollback restaura somente os arquivos registrados; não restaurar snapshot inteiro nem dados reais. SQL10 é reversão separada, não executada por instalar o pacote.

Para atualizar apenas o clone Git:

```powershell
$repo = 'C:\Users\israe\Downloads\Automações\VENDRA-GIT-STAGING'
git -C $repo fetch origin
if (git -C $repo status --porcelain) { throw 'Revisar alterações locais' }
git -C $repo pull --ff-only
```

Não contém segredos, perfis privados, credenciais CODEX, banco local ou backups Make. Nenhuma promoção ao principal. Detalhes e comandos operacionais seguem abaixo.

# H1-006H — Comando persistente do portal preparado

## Estado em 15/10/2026

Código aplicado somente na cópia Windows. Portal STAGING da porta 8011 carregado com `app.staging_h1_006h`, mesmo perfil e sessões. Nova tela `/disparos/envio` abre para a conta CODEX-Comercial existente, mostra histórico real com telefones mascarados e datas em Brasília; formulário e botão ficam desativados com o transporte desligado. Navegação Disparos aponta para a nova tela; testes antigos continuam em `/disparos`. Perfil `.env.h1_005b2` preservado byte a byte. Senha descartável da conta CODEX-Comercial foi renovada para o teste de login e guardada somente no diretório privado de evidências. Não foi criada outra conta.

218 testes Windows passaram em cópia limpa, incluindo 18 novos testes de serviço, rotas e configuração explícita. Cobrem rejeição por perfil/CSRF, destinatário não autorizado, URL/segredo inválidos, nonce inválido, timeout sem retry automático, pedido já reservado sem nova chamada HTTP, resposta divergente do banco, proteção do status recebido em paralelo, escape HTML e isolamento do `.env` original. Falhas iniciais dos mocks/importação antecipada e limpeza de diretório temporário no Windows foram corrigidas, sem mudar assertions existentes. Isso é evidência offline e de tela/login com transporte desligado, ainda não homologação funcional do envio pelo portal.

## Persistência e transporte

SQL09 preparado cria `vendra_dispatch_request_v1`: valida perfil ativo, telefone e etapa; usa chave UUID do formulário e locks para idempotência; reutiliza cliente/atendimento/oportunidade aberta sem resetar etapa do CRM; cria o conjunto necessário atomicamente, mensagem pending e registro de auditoria sem telefone/corpo. Usa o mesmo lock de telefone da recepção WhatsApp. A função só pode ser executada por service_role. Não cria tabelas/RLS, liga flags ou envia mensagens. SQL09 também alinha a reserva existente ao perfil Gerencial, que já tem acesso ao módulo Disparos. SQL10 remove o comando e restaura a verificação anterior, preservando dados.

O serviço exige transporte explícito habilitado, URL HTTPS de webhook Make permitido, segredo próprio e destinatário autorizado no STAGING. Cria o pedido via RPC; transmite o mesmo ID. Timeout não gera outro pedido nem retry automático. Pedido já reservado não chama transporte novamente; confirmação HTTP não é tratada como entrega do WhatsApp. O status do provedor nunca é sobrescrito pela resposta do portal. O Make continua responsável por reservar e confirmar WAMID pelo contrato H1-006F.

**SQL09/10 ainda não executados. Cenário Disparo Inicial original 6561096 ainda não ajustado nesta etapa. Autorização específica para essas duas ações foi solicitada e está pendente.** O cenário REV9 original permanece com o ajuste autorizado em H1-006G; entrada automática e read por replay continuam validados. Não confundir esses resultados com envio pelo formulário novo.

## Comandos

Executado nesta sessão para validar o perfil, sem iniciar outra instância:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.dispatch_portal_start --config .env.h1_005b2 --check
```

Startup integrado (já iniciado nesta sessão; não repetir enquanto 8011 estiver em uso):

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.dispatch_portal_start --config .env.h1_005b2
```

O starter carrega somente o perfil explícito, limpa configurações herdadas e desabilita fallback ao `.env` original. Valores padrão mantêm transporte desligado. Configuração futura, exclusivamente em perfil privado: `DISPATCH_TRANSPORT_ENABLED`, `DISPATCH_TRANSPORT_URL`, `DISPATCH_TRANSPORT_SECRET`, `DISPATCH_ALLOWED_PHONES`. Não preencher ou ativar por efeito da instalação do pacote.

Regressão reproduzível:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validar_staging.ps1
```

Rollback operacional do portal: encerrar somente a instância 8011 identificada e iniciar o launcher anterior com o mesmo perfil preservado:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.staging_start
```

Rollback de código usa somente arquivos registrados no backup do instalador; SQL e Make têm reversões separadas. Não restaurar snapshot inteiro ou dados de evidência.

## Próximo teste funcional

Após autorização: aplicar SQL09 somente em ljufhqnadzltqbtdaulv, verificar ACL e concorrência real; salvar backup do Disparo Inicial e acrescentar reserva antes do template e vínculo depois. Validar secret/escopo, configurar apenas destinatário de teste já autorizado e executar formulário -> banco -> Make -> template -> WAMID -> status automático. Restaurar bloqueios temporários e registrar evidência. Depois completar recuperação/fluxo IA e preparar hospedagem estável. Não promover banco/pasta principal antes da homologação pertinente.

- [Tela local](http://127.0.0.1:8011/disparos/envio)
- [Recepção validada na etapa anterior](https://github.com/geanprofcd/Projetos/blob/desenvolvimento/vendra-staging/docs/VALIDACAO_EXECUTOR_STAGING.md)
- [Contrato de reserva e confirmação já testado](https://github.com/geanprofcd/Projetos/blob/desenvolvimento/vendra-staging/docs/VALIDACAO_DISPARO_INICIAL_STAGING.md)
