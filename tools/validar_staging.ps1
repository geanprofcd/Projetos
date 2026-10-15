param(
    [string]$Python = '',
    [string]$Saida = '',
    [ValidateRange(10,3600)][int]$TimeoutSegundos = 120
)
$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
if (-not $Python) { $Python = Join-Path $sourceRoot '.venv\Scripts\python.exe' }
$pythonPath = (Resolve-Path -LiteralPath $Python).Path
if (-not $Saida) { $Saida = Join-Path ([IO.Path]::GetTempPath()) 'VENDRA-validacoes' }
$outputRoot = [IO.Path]::GetFullPath($Saida)
foreach ($dir in @('app','tools','tests','sql')) {
    $excludedRoot = [IO.Path]::GetFullPath((Join-Path $sourceRoot $dir)).TrimEnd('\')
    if ($outputRoot.TrimEnd('\').Equals($excludedRoot,[StringComparison]::OrdinalIgnoreCase) -or
        $outputRoot.StartsWith($excludedRoot+'\',[StringComparison]::OrdinalIgnoreCase)) {
        throw 'Saida deve ficar fora dos diretorios de fonte copiados.'
    }
}
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$runRoot = Join-Path $outputRoot ('staging_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'_'+[guid]::NewGuid().ToString('N').Substring(0,8))
$snapshot = Join-Path $runRoot 'fonte'
New-Item -ItemType Directory -Path $snapshot -Force | Out-Null
$manifest = @()
# Only source directories: never copy credentials, state or virtual environments.
foreach ($dir in @('app','tools','tests','sql')) {
    $base = Join-Path $sourceRoot $dir
    foreach ($file in Get-ChildItem -LiteralPath $base -File -Recurse) {
        $rel = $file.FullName.Substring($sourceRoot.Length+1).Replace('\','/')
        if ($rel -match '(^|/)(__pycache__|\.git|\.venv|runtime|\.vendra-data)(/|$)' -or
            $file.Name -match '^\.env' -or $file.Extension -in @('.pyc','.pyo')) { continue }
        if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Link nao permitido: $rel" }
        $dst = Join-Path $snapshot $rel
        New-Item -ItemType Directory -Path (Split-Path -Parent $dst) -Force | Out-Null
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        Copy-Item -LiteralPath $file.FullName -Destination $dst
        if ((Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hash) {
            throw "Fonte mudou durante a copia: $rel"
        }
        $manifest += [pscustomobject]@{path=$rel;sha256=$hash}
    }
}
foreach ($name in @('requirements.txt','VERSION','.env.example')) {
    $file = Join-Path $sourceRoot $name
    if (Test-Path -LiteralPath $file -PathType Leaf) {
        Copy-Item -LiteralPath $file -Destination (Join-Path $snapshot $name)
        $manifest += [pscustomobject]@{path=$name;sha256=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()}
    }
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runRoot 'manifest.json') -Encoding UTF8
$started = [DateTimeOffset]::UtcNow
$log = Join-Path $runRoot 'unittest.log'
$exitCode = -1
$stdout = Join-Path $runRoot 'stdout.log'
$stderr = Join-Path $runRoot 'stderr.log'
$timedOut = $false
$testProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-X','utf8','-m','unittest','discover','-s','tests','-q') -WorkingDirectory $snapshot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$null = $testProcess.Handle
try {
    if ($testProcess.WaitForExit($TimeoutSegundos*1000)) {
        $testProcess.WaitForExit()
        $exitCode = $testProcess.ExitCode
        if ($null -eq $exitCode) { throw 'Windows nao retornou o codigo de saida; nao considerar aprovado apenas pelo log.' }
    } else {
        $timedOut = $true
        # Terminate only the process tree started by this invocation (venv may spawn Python).
        & taskkill.exe /PID $testProcess.Id /T /F | Out-Null
        $exitCode = 124
    }
} finally {
    $combinedLog = [IO.File]::ReadAllText($stdout)+[Environment]::NewLine+[IO.File]::ReadAllText($stderr)
    [IO.File]::WriteAllText($log,$combinedLog,[Text.UTF8Encoding]::new($false))
}
$result = [ordered]@{
    scope='STAGING_SOURCE_UNIT_TESTS';started_utc=$started.ToString('o')
    finished_utc=[DateTimeOffset]::UtcNow.ToString('o');exit_code=$exitCode
    files=$manifest.Count;snapshot=$snapshot;log=$log
    timed_out=$timedOut;timeout_seconds=$TimeoutSegundos
    functional_homologation=$false
}
$report = Join-Path $runRoot 'resultado.json'
$result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $report -Encoding UTF8
Get-Content -LiteralPath $log -Encoding UTF8
Write-Output "Relatorio: $report"
if ($exitCode -ne 0) { throw "Suite falhou com codigo $exitCode; copia e log preservados." }
Write-Output 'Suite aprovada. Homologacao funcional exige evidencias separadas de integracao.'
