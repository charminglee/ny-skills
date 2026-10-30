[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('inventory','inspect','extract')][string]$Action,
    [Parameter(Mandatory)][string]$WorkDir,
    [string]$AssetsJson,
    [string]$AssetRoot,
    [string]$Paks
)
. (Join-Path $PSScriptRoot 'Common.ps1')
$config = Get-PackerEnvironment
$taskRoot = [IO.Path]::GetFullPath((Join-Path $config.project_root '.tmp')).TrimEnd('\') + '\'
$work = [IO.Path]::GetFullPath($WorkDir)
if (-not $work.StartsWith($taskRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'WorkDir must be inside project .tmp' }
if ($Action -eq 'inventory' -and -not $AssetRoot) { throw 'inventory requires AssetRoot' }
if ($Action -ne 'inventory' -and -not (Test-Path -LiteralPath $AssetsJson -PathType Leaf)) { throw 'AssetsJson is required' }
if (Test-Path -LiteralPath (Join-Path $work 'repack-manifest.json')) { throw 'Existing extraction manifest; choose a fresh WorkDir' }
New-Item -ItemType Directory -Force -Path $work | Out-Null
$lib = Join-Path $PSScriptRoot 'lib/cue'
foreach ($name in @('CUE4Parse.dll','Newtonsoft.Json.dll','Oodle.NET.dll','PbzCueAssets.dll')) {
    [Reflection.Assembly]::LoadFrom((Join-Path $lib $name)) | Out-Null
}
$settings = @{
    action=$Action; paks= if ($Paks) { [IO.Path]::GetFullPath($Paks) } else { $config.paks }
    usmap=(Join-Path $PSScriptRoot $config.usmap); oodle=(Join-Path $PSScriptRoot $config.oodle)
    aes=$config.aes; work=$work; root=$AssetRoot
    assets= if ($AssetsJson) { [IO.Path]::GetFullPath($AssetsJson) } else { $null }
}
$settingsFile = Join-Path $work 'cue-config.json'
$settings | ConvertTo-Json | Set-Content -LiteralPath $settingsFile -Encoding utf8NoBOM
[PbzCueAssets]::Run($settingsFile)
