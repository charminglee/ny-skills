[CmdletBinding()]
param(
    [string]$Destination='E:/PbzMod/Packer',
    [string]$ProjectRoot='E:/PbzMod',
    [Parameter(Mandatory)][string]$PackerBinary,
    [Parameter(Mandatory)][string]$RetocBinary,
    [Parameter(Mandatory)][string]$CueLib,
    [Parameter(Mandatory)][string]$Usmap,
    [Parameter(Mandatory)][string]$Oodle,
    [Parameter(Mandatory)][string]$Paks,
    [Parameter(Mandatory)][string]$AesKey,
    [string]$PowerShell=(Get-Command pwsh -CommandType Application | Select-Object -First 1).Source
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if ((Test-Path -LiteralPath $Destination) -and @(Get-ChildItem -LiteralPath $Destination -Force).Count -gt 0) {
    throw 'Deployment target is not empty. This script never replaces an existing toolchain.'
}
foreach ($path in @($PackerBinary,$RetocBinary,$CueLib,$Usmap,$Oodle,$PowerShell,$Paks)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing deployment input: $path" }
}
$root=[IO.Path]::GetFullPath($Destination)
foreach ($dir in @('bin','lib/cue','mappings')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $root $dir) | Out-Null
}
Copy-Item -LiteralPath $PackerBinary -Destination (Join-Path $root 'bin/pbz_iostore_pack.exe')
Copy-Item -LiteralPath $RetocBinary -Destination (Join-Path $root 'bin/retoc.exe')
Copy-Item -LiteralPath $Oodle -Destination (Join-Path $root 'bin/oo2core_9_win64.dll')
Copy-Item -LiteralPath $Usmap -Destination (Join-Path $root 'mappings/PBZ.usmap')
Get-ChildItem -LiteralPath $CueLib -File | Copy-Item -Destination (Join-Path $root 'lib/cue')
Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot '../assets/packer') -File | Copy-Item -Destination $root

# 部署时预编译本技能的 CUE 助手；日常打包仅加载这个 DLL。
$names=@('CUE4Parse.dll','Newtonsoft.Json.dll','Oodle.NET.dll')
foreach ($name in $names) { [Reflection.Assembly]::LoadFrom((Join-Path $root "lib/cue/$name")) | Out-Null }
$references=@((Get-ChildItem -LiteralPath (Join-Path $PSHOME 'ref') -Filter '*.dll').FullName)
$references+=$names | ForEach-Object {Join-Path $root "lib/cue/$_"}
Add-Type -Path (Join-Path $PSScriptRoot 'cue_assets.cs') -ReferencedAssemblies $references -OutputAssembly (Join-Path $root 'lib/cue/PbzCueAssets.dll') -OutputType Library -IgnoreWarnings -CompilerOptions '/nowarn:1701'
$config=[ordered]@{
    project_root=[IO.Path]::GetFullPath($ProjectRoot)
    pwsh=[IO.Path]::GetFullPath($PowerShell)
    paks=[IO.Path]::GetFullPath($Paks)
    aes=$AesKey
    usmap='mappings/PBZ.usmap'
    oodle='bin/oo2core_9_win64.dll'
}
$config|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $root 'config.json') -Encoding utf8NoBOM
$files=@(Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object {$_.FullName -notlike '*config.json'} | ForEach-Object {
    @{path=[IO.Path]::GetRelativePath($root,$_.FullName).Replace('\','/');sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash}
})
@{deployed_utc=[DateTime]::UtcNow.ToString('o');retoc_upstream_commit='885a8dae740cb1ce1e41ff2e74f67f9f0c118237';powershell_version=$PSVersionTable.PSVersion.ToString();files=$files}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $root 'deployment.json') -Encoding utf8NoBOM
& $PowerShell -NoProfile -File (Join-Path $root 'Pack.ps1') -CheckEnvironment
if ($LASTEXITCODE -ne 0) {throw 'Deployed environment check failed'}
Write-Output "DEPLOYED $root"
