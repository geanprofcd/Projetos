# Comandos de operacao e autorizacao permanente

Em 14/10/2026 o usuario solicitou documentar os comandos para consulta posterior e autorizou sua execucao autonoma sempre que necessaria, sem depender de execucao manual por ele. Aplicar essa autorizacao ao escopo de desenvolvimento/validacao e sincronizacao ja combinado. Manter STAGING, principal e dados separados e cumprir os criterios existentes de homologacao/promocao.

## Sincronizar o checkout de desenvolvimento

O clone abaixo ja existe; nao executar novo clone sobre ele. Conferir a branch e preservar alteracoes locais. Se houver divergencia, revisar e conciliar antes de continuar.

```powershell
$repo = 'C:\Users\israe\Downloads\Automações\VENDRA-GIT-STAGING'
git -C $repo branch --show-current
git -C $repo fetch origin
if (git -C $repo status --porcelain) { throw 'Preservar e revisar alteracoes locais antes de sincronizar' }
git -C $repo pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Sincronizacao Git nao concluida' }
git -C $repo log -1 --oneline
```

Branch esperada: desenvolvimento/vendra-staging. Git sincroniza fontes; aplicacao no runtime e validacao sao registradas separadamente. Nao usar reset --hard ou clean para descartar divergencias.

## Testar o contrato da ponte no Windows

Executar na copia Windows de STAGING com venv preparado:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_whatsapp_callbacks tests.test_whatsapp_control_bridge -v
```

Para a regressao completa no checkout Git, usar o Python do venv preparado, sem copiar esse venv para o Git:

```powershell
$runtime = 'C:\Users\israe\Downloads\Automações\VENDRA_v0.0.4_Windows_Source\VENDRA_v0.0.4_Windows - Copia\vendra_starter'
$repo = 'C:\Users\israe\Downloads\Automações\VENDRA-GIT-STAGING'
$python = Join-Path $runtime '.venv\Scripts\python.exe'
Push-Location -LiteralPath $repo
try {
    & $python -X utf8 -m unittest discover -s tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Regressao falhou' }
} finally { Pop-Location }
```

A raiz da copia de execucao contem .venv e nao deve ser usada na regressao que varre todos os fontes Python. Os testes focados acima podem rodar nela. Testes offline nao substituem homologacao funcional do fluxo alterado.

## Verificar a ponte

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8012/health'
```

Registrar os gates informados no retorno. Healthcheck confirma disponibilidade, nao entrega de mensagem nem homologacao. O hostname do tunel temporario pode mudar: consultar o registro privado vigente antes de usar HTTPS.

Inicializacao, somente com perfil exclusivo e porta conferidos (na pasta runtime):

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.whatsapp_callbacks_start --config 'CAMINHO_DO_PERFIL_EXCLUSIVO' --port 8012
```

O perfil contem credenciais e fica fora do Git/documentos publicos. Ao reiniciar autonomamente em segundo plano, identificar o PID da porta 8012 e conferir comando/servico antes de parar; usar Start-Process -WindowStyle Hidden e logs privados. Preservar os processos 8010/8011. Nao mudar flags de IA/envio como efeito de reinicio ou sincronizacao.

## Conferir uma entrega

```powershell
Get-FileHash -LiteralPath 'CAMINHO_DO_PACOTE.zip' -Algorithm SHA256
```

Comparar com o hash publicado. Instalacao de delta exige manifesto, destino STAGING, backup e verificacao posterior conforme instrucoes da entrega exata. SQL/Make/worker/envio continuam operacoes separadas; usar as autorizacoes especificas e os limites ja registrados, incluindo destinatario de teste e promocao condicionada a homologacao.

## Registro apos execucao

Informar de forma breve: acao/comando, data/hora Brasilia, destino/ambiente, commit/hash, backup quando houve substituicao, verificacao executada, resultado e proxima etapa. Nao registrar senhas, tokens ou corpo de configuracoes privadas. Atualizar o Documento Mestre cumulativo e o checkpoint do projeto quando houver avancos. O usuario recebe os comandos como referencia; nao precisa roda-los novamente se a execucao ja foi realizada e validada.

Esta entrega apenas registra o procedimento e a autorizacao. Nao houve nova execucao de testes, alteracao SQL/Make, reinicio, ativacao de IA ou envio de mensagens para registrar esta preferencia.
