# H1-006G — Validação Windows e recepção Meta

Aplicado no Windows STAGING: executor de regressão em cópia limpa, com SHA-256, logs, relatório e timeout. 200 testes passaram em 1,071 s; fixtures comprovaram propagação de falha e timeout. Não inicia serviços, executa SQL ou chama Make. Arquivos já aplicados nesta sessão; nenhuma reinstalação manual necessária.

Código: https://github.com/geanprofcd/Projetos/commit/4772d6e0b9ca0854a702840a7cf91ae51ac48a20
Evidências: https://github.com/geanprofcd/Projetos/blob/desenvolvimento/vendra-staging/docs/VALIDACAO_EXECUTOR_STAGING.md

Com autorização específica, callbacks 64/83 do Make original REV9 passaram a usar ponte STAGING; controle de IA antes do módulo8 e envios77/75/76 bloqueados. Backup privado/reversão preparados. Banco e pasta originais preservados. Um envio autorizado gerou status reais; configuração HTTP parcial inicialmente falhou, corrigida preservando mapper completo. Replay read persistiu mesmo WAMID nas três entidades. Entrada nova Teste VENDRA final recebida automaticamente, HTTP202, uma gravação e parada em modo humano. Sem novas saídas no atendimento, flags temporárias ausentes. Não confundir replay de status com evento novo após correção. Portal/CRM real e homologação final/hospedagem pendentes.

Aplicativo Meta de teste VENDRA-STAGING-CODEX criado (1632601681609213), mas não conectado ao WABA. Usuário priorizou caminho direto com receptor existente, sem novas cópias desnecessárias.

Na raiz do runtime preparado:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validar_staging.ps1
```

Opcional: -Saida 'PASTA_DE_RELATORIOS' -TimeoutSegundos 120. Usa .venv\Scripts\python.exe -X utf8; fonte/manifesto/logs/resultado.json preservados no TEMP padrão. Relatórios com caminhos locais não devem ser publicados automaticamente.

Em outra cópia STAGING preparada, extrair em pasta nova e conferir:

```powershell
Get-FileHash -LiteralPath '.\VENDRA_H1_006G_VALIDACAO_STAGING_20261015.zip' -Algorithm SHA256
Expand-Archive -LiteralPath '.\VENDRA_H1_006G_VALIDACAO_STAGING_20261015.zip' -DestinationPath '.\H1_006G_CONFERENCIA'
powershell -NoProfile -ExecutionPolicy Bypass -File '.\H1_006G_CONFERENCIA\tools\aplicar_callbacks_staging.ps1' -Destino 'CAMINHO_DA_COPIA_STAGING'
```

Último comando é dry-run. -Aplicar instala apenas o delta com backup/rollback.json; não toca .env, estado ou venv. Restaurar somente arquivos registrados no backup em caso de rollback, sem reverter banco/Make por efeito colateral. Pacote contém três arquivos gerenciados e manifesto. Não contém segredos, perfis privados, dados reais ou backups Make. Não promove ao principal.

Para atualizar o checkout Git separado (não instala automaticamente no runtime):

```powershell
$repo = 'C:\Users\israe\Downloads\Automações\VENDRA-GIT-STAGING'
git -C $repo fetch origin
if (git -C $repo status --porcelain) { throw 'Revisar alterações locais' }
git -C $repo pull --ff-only
```
