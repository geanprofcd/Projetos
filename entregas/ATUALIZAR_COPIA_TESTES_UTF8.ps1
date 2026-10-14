param(
    [string]$Destino = 'C:\Users\israe\Downloads\Automações\VENDRA_v0.0.4_Windows_Source\VENDRA_v0.0.4_Windows - Copia\vendra_starter',
    [switch]$Aplicar
)

$ErrorActionPreference = 'Stop'
$pacote = $PSScriptRoot
$manifesto = Get-Content -LiteralPath (Join-Path $pacote 'MANIFEST.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $Destino -PathType Container)) { throw 'A pasta de testes nao existe.' }
$destinoReal = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Destino).Path).TrimEnd('\')
$pastaPai = [IO.Path]::GetFileName([IO.Path]::GetDirectoryName($destinoReal))
if ([IO.Path]::GetFileName($destinoReal) -ne 'vendra_starter' -or $pastaPai -ne 'VENDRA_v0.0.4_Windows - Copia') {
    throw 'Destino bloqueado: este pacote aceita somente a copia de testes, nunca o principal.'
}

function Caminho-Filho([string]$Raiz, [string]$Relativo) {
    if ([IO.Path]::IsPathRooted($Relativo) -or $Relativo -match '(^|[\\/])\.\.([\\/]|$)') { throw 'Caminho inseguro no manifesto.' }
    $raizReal = [IO.Path]::GetFullPath($Raiz).TrimEnd('\')
    $resultado = [IO.Path]::GetFullPath((Join-Path $raizReal $Relativo.Replace('/', '\')))
    if (-not $resultado.StartsWith($raizReal + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Caminho fora da raiz.' }
    $checagem = $resultado
    while ($checagem.Length -ge $raizReal.Length) {
        if (Test-Path -LiteralPath $checagem) {
            $item = Get-Item -LiteralPath $checagem -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Link/junction no caminho: comparar o destino real antes de aplicar.' }
        }
        if ($checagem -eq $raizReal) { break }
        $checagem = Split-Path -Parent $checagem
    }
    return $resultado
}

foreach ($base in $manifesto.compatibility) {
    $arquivo = Caminho-Filho $destinoReal $base.path
    if (-not (Test-Path -LiteralPath $arquivo -PathType Leaf)) { throw ('Base nao reconhecida: ' + $base.path) }
    if ((Get-FileHash -LiteralPath $arquivo -Algorithm SHA256).Hash.ToLowerInvariant() -ne $base.sha256) {
        throw ('Base diferente em ' + $base.path + '. Preservar as mudancas locais e comparar antes de aplicar.')
    }
}

$diferentes = @()
foreach ($entrada in $manifesto.files) {
    if ($entrada.path -match '(^|[\\/])(\.git|\.env[^\\/]*|\.venv|\.vendra-data|runtime|updates)([\\/]|$)') {
        throw 'O manifesto inclui um caminho reservado.'
    }
    $origem = Caminho-Filho (Join-Path $pacote 'payload') $entrada.path
    $alvo = Caminho-Filho $destinoReal $entrada.path
    if (-not (Test-Path -LiteralPath $origem -PathType Leaf)) { throw ('Arquivo ausente no pacote: ' + $entrada.path) }
    if ((Get-FileHash -LiteralPath $origem -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entrada.sha256) {
        throw ('Integridade incorreta: ' + $entrada.path)
    }
    $igual = (Test-Path -LiteralPath $alvo -PathType Leaf) -and ((Get-FileHash -LiteralPath $alvo -Algorithm SHA256).Hash.ToLowerInvariant() -eq $entrada.sha256)
    if (-not $igual) { $diferentes += $entrada }
}
Write-Host ('Pacote: ' + $manifesto.package_id)
Write-Host ('Arquivos que precisam de atualizacao: ' + $diferentes.Count)
foreach ($entrada in $diferentes) { Write-Host ('  ' + $entrada.path) }
if (-not $Aplicar) {
    Write-Host 'Apenas conferencia; nenhum arquivo alterado. Use -Aplicar para atualizar a copia de testes.'
    exit 0
}

if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
    $servidor = Get-NetTCPConnection -LocalPort 8011 -State Listen -ErrorAction SilentlyContinue
    if ($servidor) { throw 'Pare somente o servidor STAGING 8011 antes de atualizar. O principal nao sera encerrado.' }
}
$python = Caminho-Filho $destinoReal '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Python .venv da copia de testes nao localizado.' }
$backup = Join-Path ([IO.Path]::GetDirectoryName($destinoReal)) ('vendra_starter_backup_cloud_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $backup | Out-Null
$registro = [ordered]@{package_id=$manifesto.package_id; destination=$destinoReal; status='APLICACAO_INICIADA'; files=@()}
try {
    foreach ($entrada in $diferentes) {
        $alvo = Caminho-Filho $destinoReal $entrada.path
        $existia = Test-Path -LiteralPath $alvo -PathType Leaf
        if ($existia) {
            $copia = Caminho-Filho $backup $entrada.path
            New-Item -ItemType Directory -Path (Split-Path -Parent $copia) -Force | Out-Null
            Copy-Item -LiteralPath $alvo -Destination $copia
            if ((Get-FileHash -LiteralPath $alvo -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $copia -Algorithm SHA256).Hash) { throw 'Backup nao confirmado.' }
        }
        $registro.files += [ordered]@{path=$entrada.path; existed_before=$existia; installed_sha256=$entrada.sha256}
    }
    foreach ($entrada in $diferentes) {
        $alvo = Caminho-Filho $destinoReal $entrada.path
        New-Item -ItemType Directory -Path (Split-Path -Parent $alvo) -Force | Out-Null
        Copy-Item -LiteralPath (Caminho-Filho (Join-Path $pacote 'payload') $entrada.path) -Destination $alvo -Force
        if ((Get-FileHash -LiteralPath $alvo -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entrada.sha256) { throw 'Copia nao confirmada.' }
    }
    $runtime = Join-Path $destinoReal 'runtime\codex-cloud'
    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
    $constraint = Join-Path $runtime 'constraints.txt'
    if (Test-Path -LiteralPath $constraint -PathType Leaf) { Copy-Item -LiteralPath $constraint -Destination (Join-Path $backup 'constraints.previous.txt') }
    Copy-Item -LiteralPath (Join-Path $pacote 'cloud-constraints.txt') -Destination $constraint -Force
    Push-Location $destinoReal
    try {
        & $python -X utf8 -m pip install -r requirements.txt -c $constraint
        if ($LASTEXITCODE -ne 0) { throw 'Instalacao de dependencias falhou; nao homologar nem promover.' }
        & $python -X utf8 -m pip check
        if ($LASTEXITCODE -ne 0) { throw 'Dependencias inconsistentes; nao homologar nem promover.' }
        # Testar uma copia identica dos arquivos entregues, sem dados/credenciais
        # nem .venv sob a raiz: B1 percorre recursivamente os arquivos Python.
        $verificacao = Join-Path $backup 'verificacao'
        foreach ($entrada in $manifesto.files) {
            $fonteTeste = Caminho-Filho $destinoReal $entrada.path
            $alvoTeste = Caminho-Filho $verificacao $entrada.path
            New-Item -ItemType Directory -Path (Split-Path -Parent $alvoTeste) -Force | Out-Null
            Copy-Item -LiteralPath $fonteTeste -Destination $alvoTeste
            if ((Get-FileHash -LiteralPath $alvoTeste -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entrada.sha256) { throw 'Copia de verificacao divergente.' }
        }
        $modulos = @($manifesto.test_modules)
        Push-Location $verificacao
        try {
            & $python -X utf8 -m unittest -v @modulos
            if ($LASTEXITCODE -ne 0) { throw 'Testes falharam; nao homologar nem promover.' }
        } finally { Pop-Location }
    } finally { Pop-Location }
    $registro.status = 'TESTES_LOCAIS_OK_HOMOLOGACAO_FUNCIONAL_PENDENTE'
    Write-Host 'Copia de testes atualizada. Testes locais OK; homologacao funcional ainda necessaria.'
    Write-Host 'Nenhum SQL foi executado e o principal nao foi alterado.'
} catch {
    $registro.status = 'FALHA_REQUER_DIAGNOSTICO_SEM_PROMOCAO'
    Write-Host ('Falha. Backup e lista de arquivos em: ' + $backup)
    throw
} finally {
    $registro | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $backup 'REGISTRO_APLICACAO.json') -Encoding UTF8
    Write-Host ('Registro e backup: ' + $backup)
}
