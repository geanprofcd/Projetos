param(
    [Parameter(Mandatory=$true)][string]$Destino,
    [switch]$Aplicar
)
$ErrorActionPreference = 'Stop'
$pkgRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $pkgRoot 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Manifesto do pacote ausente.' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$targetRoot = (Resolve-Path -LiteralPath $Destino).Path.TrimEnd('\')
$stageConfig = Join-Path $targetRoot '.env.h1_005b2'
if (-not (Test-Path -LiteralPath (Join-Path $targetRoot 'app\staging_h1_005b9.py')) -or
    -not (Test-Path -LiteralPath $stageConfig)) { throw 'Destino nao identificado como copia STAGING preparada.' }
$stageText = Get-Content -LiteralPath $stageConfig -Raw -Encoding UTF8
if ($stageText -notmatch '(?m)^APP_ENV\s*=\s*staging\s*$' -or
    $stageText -notmatch '(?m)^SUPABASE_URL\s*=\s*https://ljufhqnadzltqbtdaulv\.supabase\.co/?\s*$') {
    throw 'Perfil STAGING esperado nao confere. Nao aplicar no original.'
}
$pending = @()
foreach ($entry in $manifest.files) {
    $rel = [string]$entry.path
    if ([IO.Path]::IsPathRooted($rel) -or $rel.Split('/') -contains '..' -or
        $rel -match '(^|/)(\.env[^/]*|\.vendra-data|runtime|\.venv|\.git)(/|$)' -or
        $rel -notmatch '^(app|tools|tests|sql|docs)/') { throw "Caminho nao permitido: $rel" }
    $src = [IO.Path]::GetFullPath((Join-Path $pkgRoot $rel))
    $dst = [IO.Path]::GetFullPath((Join-Path $targetRoot $rel))
    if (-not $src.StartsWith($pkgRoot.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase) -or
        -not $dst.StartsWith($targetRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Caminho fora do destino.' }
    if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
        throw "Hash divergente: $rel"
    }
    $exists = Test-Path -LiteralPath $dst
    if ($exists -and ((Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant() -eq $entry.sha256)) { continue }
    $pending += [pscustomobject]@{path=$rel;source=$src;destination=$dst;existed=$exists}
}
Write-Output "Arquivos diferentes: $($pending.Count). Conferencia SHA-256 aprovada."
if (-not $Aplicar) { Write-Output 'Conferencia somente leitura. Use -Aplicar para instalar na copia STAGING.'; exit 0 }
if (-not $pending.Count) { Write-Output 'Arquivos ja correspondem ao pacote. Nenhuma alteracao.'; exit 0 }
$backupRoot = Join-Path $targetRoot ('callback_backup_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
New-Item -ItemType Directory -Path $backupRoot | Out-Null
$pending | Select-Object path,existed | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $backupRoot 'rollback.json') -Encoding UTF8
foreach ($entry in $pending) {
    if ($entry.existed) {
        $backupFile = Join-Path $backupRoot $entry.path
        New-Item -ItemType Directory -Path (Split-Path -Parent $backupFile) -Force | Out-Null
        Copy-Item -LiteralPath $entry.destination -Destination $backupFile
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $entry.destination) -Force | Out-Null
    Copy-Item -LiteralPath $entry.source -Destination $entry.destination -Force
    $expected = ($manifest.files | Where-Object path -eq $entry.path).sha256
    if ((Get-FileHash -LiteralPath $entry.destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
        throw "Falha apos copiar $($entry.path); backup preservado em $backupRoot"
    }
}
Write-Output "Delta aplicado somente no STAGING. Backup: $backupRoot"
Write-Output 'Nao executou SQL, iniciou servicos/tunel, alterou Make ou enviou mensagens.'
Write-Output 'Validar: .\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_whatsapp_callbacks -v'
