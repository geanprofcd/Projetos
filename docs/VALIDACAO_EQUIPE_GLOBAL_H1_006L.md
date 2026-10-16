# H1-006L - Controle da equipe e configuração global

Validado em 15/10/2026, somente na cópia Windows e no projeto VENDRA-STAGING `ljufhqnadzltqbtdaulv`. Original, seu banco e design preservados. Esta entrega consolida o backend comercial H1-006K e o alinhamento SQL11.

## Aplicado e verificado

Após autorização específica do usuário, foi aplicada a migration `vendra_whatsapp_team_global_control_v1`, correspondente a `sql/11_ALINHAR_CONTROLE_EQUIPE_STAGING.sql`. Altera somente as funções existentes de leitura e troca de modo. Administrativo, Comercial e Gerencial ativos podem controlar humano/IA com sua própria identidade; Comum e inativos são rejeitados. A configuração `ai_automation.enabled` passa a valer quando não há `whatsapp_bridge.ai_enabled` explícito; um override false continua prevalecendo.

As duas RPCs permanecem SECURITY INVOKER, search_path vazio, EXECUTE somente service_role. Conferência real: anon e authenticated sem EXECUTE; service_role com EXECUTE; definições contêm os alinhamentos esperados. Nenhuma tabela, RLS, worker, lote, envio ou configuração do principal foi alterado. SQL12 de reversão está preparado e não foi executado.

O backend da cópia foi alinhado à mesma política. A prévia local 8014 foi reiniciada para carregar esse código, preservando os demais processos. `app.main`, router comercial de Atendimentos e template comercial de detalhe continuam idênticos byte a byte aos arquivos da pasta original. Não houve edição de HTML/CSS/JS nesta etapa; protótipos e factories STAGING não devem ser promovidos ao original.

## Evidências

- **249 testes Windows passaram em 2,418 s**, em snapshot limpo e UTF8. Relatório privado: `VENDRA-validacoes/staging_20261015_224144_925_0d946757/resultado.json`. Inclui regras de perfis ativos/inativos e preservação da identidade do ator.
- **17 verificações funcionais reais HTTP/RPC/banco/UI e limpeza**, além da conferência SQL de ACL: configuração ausente desligada; formulário comercial liga/desliga a configuração global; Comercial reconecta, Gerencial desconecta e Administrativo reconecta pelos endpoints comerciais; identidade persistida é a do operador real; CSRF inválido e Comum não escrevem; RPC rejeita Comum, Gerencial inativo e versão antiga PT409; reconexão bloqueada com global desligada; overrides false/true prevalecem; nenhuma nova outbox; clique Comercial no navegador confirmou humano no banco; estado final restaurado.
- O navegador mostrou a conta Comercial, os controles originais, resposta IA real com status Lido e janela de WhatsApp aberta. O clique Desconectar persistiu e foi confirmado por consulta. A captura posterior não foi concluída devido a timeout da conexão com a aba; não alegar screenshot novo dessa etapa. A prova visual anterior K continua como registro histórico.
- Conta CODEX administrativa existente reativada apenas para teste; conta CODEX-SESSOES temporariamente Gerencial. Ao finalizar, os perfis anteriores foram restaurados, administrador inativo e sessões temporárias revogadas. Atendimento exclusivo encerrado em humano; configurações globais/override criadas no teste removidas. Contas e mensagens reais não foram excluídas.

Uma tentativa inicial de aplicar SQL11 foi rejeitada pela revisão automática por falta de confirmação específica. Após confirmação textual explícita, a migração foi aplicada com sucesso. Duas consultas transacionais complexas de teste retornaram requestState expirado e não foram usadas como evidência; os testes funcionais acima foram executados e conferidos por HTTP/RPC/SDK real. Não contar a tentativa como teste aprovado.

## Limites e próxima etapa

O padrão de IA para novos atendimentos recebidos ainda precisa ser reconciliado: a recepção atual cria atendimento humano. Esta entrega valida configuração global e controle de atendimentos existentes, sem afirmar padrão automático de novos leads homologado.

Continuam pendentes os caminhos comerciais de Disparos/importação/lote (ainda bloqueados para Supabase real), envio humano pelo composer e anexos, além de backup/restauração, promoção seletiva e validação do original hospedado. A inspeção do composer identificou tratamento silencioso de falha de handoff e ausência de token CSRF no formulário de mensagem; precisam ser analisados e corrigidos preservando o layout antes da homologação desse fluxo. Nenhuma dessas pendências é encerrada por esta entrega.

Railway permanece sem aplicação publicada. STAGING online somente se um teste indispensável exigir. Não promover snapshot inteiro, dados, credenciais, sessões, migrations de teste ou templates STAGING. A autorização de promoção vale somente para o conjunto efetivamente homologado, com backup e rastreabilidade.

## Comandos e reversão

Código já aplicado na cópia local; não é necessário reinstalar nesta sessão. Conferência sem iniciar outro servidor:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.commercial_preview_start --config .env.h1_005b2 --check
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validar_staging.ps1
```

O perfil padrão mantém `WHATSAPP_PERSISTENT_CONTROL_ENABLED=false`; a prévia desta sessão usa perfil privado explícito, com essa flag true e transporte false. Não copiar esse perfil para o Git ou principal. Para iniciar outra prévia após verificar que 8014 está livre, usar o mesmo comando sem `--check` com perfil STAGING próprio. Não duplicar o processo atual.

Rollback de banco: revisar e aplicar separadamente SQL12 somente no mesmo STAGING, se necessário; restaura a política administrativa e a configuração anterior. Instalador de arquivos não executa SQL nem Make. Não executar rollback de banco como parte de simples atualização de arquivos. Não foi promovido nenhum arquivo ao original.
