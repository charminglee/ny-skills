param(
    [Parameter(Mandatory)][ValidateSet('inventory','inspect','extract')][string]$Action,
    [Parameter(Mandatory)][string]$CueLib,
    [Parameter(Mandatory)][string]$Paks,
    [Parameter(Mandatory)][string]$Usmap,
    [Parameter(Mandatory)][string]$Oodle,
    [Parameter(Mandatory)][string]$AesKey,
    [Parameter(Mandatory)][string]$WorkDir,
    [string]$ProjectRoot = 'E:\PbzMod',
    [string]$AssetRoot,
    [string]$AssetsJson
)

$ErrorActionPreference = 'Stop'
$taskWork = [IO.Path]::GetFullPath($WorkDir)
$taskTemp = [IO.Path]::GetFullPath((Join-Path $ProjectRoot '.tmp')).TrimEnd('\') + '\'
if (-not $taskWork.StartsWith($taskTemp, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'WorkDir must be inside ProjectRoot/.tmp/'
}
foreach ($taskInput in @($CueLib, $Paks, $Usmap, $Oodle)) {
    if (-not (Test-Path -LiteralPath $taskInput)) { throw "Missing input: $taskInput" }
}
if ($Action -eq 'inventory' -and -not $AssetRoot) { throw 'inventory requires AssetRoot' }
if ($Action -ne 'inventory' -and -not (Test-Path -LiteralPath $AssetsJson)) {
    throw 'inspect/extract requires AssetsJson containing an explicit package path array'
}
if ($Action -eq 'extract' -and (Test-Path -LiteralPath (Join-Path $taskWork 'repack-manifest.json'))) {
    throw 'Existing extraction manifest; choose a fresh WorkDir'
}
New-Item -ItemType Directory -Path $taskWork -Force | Out-Null
$taskConfig = @{
    action = $Action; paks = [IO.Path]::GetFullPath($Paks)
    usmap = [IO.Path]::GetFullPath($Usmap); oodle = [IO.Path]::GetFullPath($Oodle)
    aes = $AesKey; work = $taskWork; root = $AssetRoot
    assets = if ($AssetsJson) { [IO.Path]::GetFullPath($AssetsJson) } else { $null }
}
$taskConfigPath = Join-Path $taskWork 'cue-config.json'
$taskConfig | ConvertTo-Json | Set-Content -LiteralPath $taskConfigPath -Encoding utf8
$taskLibraries = @('CUE4Parse.dll', 'Newtonsoft.Json.dll', 'Oodle.NET.dll')
foreach ($taskLibrary in $taskLibraries) {
    [Reflection.Assembly]::LoadFrom((Join-Path $CueLib $taskLibrary)) | Out-Null
}
$taskReferences = @((Get-ChildItem -LiteralPath (Join-Path $PSHOME 'ref') -Filter '*.dll').FullName)
$taskReferences += $taskLibraries | ForEach-Object { Join-Path $CueLib $_ }
Add-Type -Path (Join-Path $PSScriptRoot 'cue_assets.cs') -ReferencedAssemblies $taskReferences `
    -IgnoreWarnings -CompilerOptions '/nowarn:1701'
[PbzCueAssets]::Run($taskConfigPath)
