Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-PackerEnvironment {
    $config = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'config.json') -Raw | ConvertFrom-Json
    if ($PSVersionTable.PSVersion.Major -lt 7 -or -not (Test-Path -LiteralPath $config.pwsh -PathType Leaf)) {
        throw 'System PowerShell 7 (pwsh) is required; check config.json pwsh path'
    }
    $lock = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'deployment.json') -Raw | ConvertFrom-Json
    foreach ($entry in $lock.files) {
        $path = Join-Path $PSScriptRoot $entry.path
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing deployed dependency: $path" }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $entry.sha256) {
            throw "Deployed dependency hash mismatch: $path"
        }
    }
    foreach ($path in @($config.paks, (Join-Path $config.paks 'global.utoc'), (Join-Path $config.paks 'global.ucas'))) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Missing game input: $path" }
    }
    return $config
}

function Invoke-PackerCommand {
    param([string]$Program, [string[]]$Arguments, [string]$Log)
    & $Program @Arguments *> $Log
    if ($LASTEXITCODE -ne 0) {
        Get-Content -LiteralPath $Log -Tail 15 | Out-Host
        throw "Command failed ($LASTEXITCODE): $Program; log: $Log"
    }
}
