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
