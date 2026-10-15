# H1-006C | Ponte e codigo Git

Aplicado na copia Windows STAGING e processo 8012 reiniciado com IA desligada. Nenhum SQL/Make alterado ou envio realizado. 186 testes Windows, 29 focados e sete verificacoes HTTP/SDK Supabase reais aprovados. Clone Git separado tambem passou em 186 testes e 260 hashes. Nao equivale a homologacao IA integral ou promocao ao principal.

Codigo: https://github.com/geanprofcd/Projetos/tree/desenvolvimento/vendra-staging
Commit: https://github.com/geanprofcd/Projetos/commit/0537d77e51302ec51fd476cd5ea7ed1fc0c416dd
Levantamento e sincronizacao: https://github.com/geanprofcd/Projetos/blob/desenvolvimento/vendra-staging/docs/VALIDACAO_GIT_STAGING.md

Clone separado ja criado em C:\Users\israe\Downloads\Automações\VENDRA-GIT-STAGING. Nao inclui venv, perfis ou estado. Sincronizar os fontes nesse checkout (PowerShell):

```powershell
$gitPath = 'C:\Users\israe\Downloads\Automações\VENDRA-GIT-STAGING'
git -C $gitPath fetch origin
git -C $gitPath status --short
git -C $gitPath pull --ff-only
git -C $gitPath log -1 --oneline
```

Executar pull somente com checkout limpo; preservar e revisar mudancas locais. Nao usar reset --hard ou clean. Essa operacao nao instala codigo no runtime Windows, transfere credenciais ou aplica SQL/Make. Para hospedagem futura, clonar essa branch e aplicar uma revisao exata com configuracao propria.

Delta Windows: ja aplicado na copia desta sessao; nao precisa reaplicar ou reiniciar agora. Para outra copia STAGING preparada, extrair em pasta nova e conferir antes de aplicar:

```powershell
Get-FileHash -LiteralPath '.\VENDRA_H1_006C_PONTE_GIT_STAGING_20261014.zip' -Algorithm SHA256
Expand-Archive -LiteralPath '.\VENDRA_H1_006C_PONTE_GIT_STAGING_20261014.zip' -DestinationPath '.\H1_006C_CONFERENCIA'
powershell -NoProfile -ExecutionPolicy Bypass -File '.\H1_006C_CONFERENCIA\tools\aplicar_callbacks_staging.ps1' -Destino 'CAMINHO_DA_COPIA_STAGING'
```

Somente depois da conferencia, repetir o ultimo comando com -Aplicar. Instalador confere SHA-256/perfil STAGING, preserva configuracoes e faz backup de arquivos substituidos; novos arquivos registrados no rollback.json. Nao executa SQL, inicia servico/tunel ou altera Make. Rollback de codigo e manual a partir do backup; nao reverte dados/migrations. Perfil IA deve continuar desligado ate testes e homologacao do fluxo de saida.

Teste direcionado na copia de execucao com venv preparado:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_whatsapp_callbacks tests.test_whatsapp_control_bridge -v
```

Concorrencia independente da preparacao, adaptacao Make de saida e passagem para humano em fluxo real continuam pendentes. Codigo Go do launcher/updater e migration local 003 nao incorporados na base Git inicial; precisam de levantamento proprio. Principal preservado, sem ambiente permanente de nuvem identificado.
