[CmdletBinding(DefaultParameterSetName='Pack')]
param(
    [Parameter(Mandatory,ParameterSetName='Pack')][string]$Manifest,
    [Parameter(Mandatory,ParameterSetName='Pack')][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_-]*$')][string]$Name,
    [Parameter(ParameterSetName='Pack')][string]$OutputDirectory,
    [Parameter(Mandatory,ParameterSetName='Check')][switch]$CheckEnvironment
)
. (Join-Path $PSScriptRoot 'Common.ps1')
$config = Get-PackerEnvironment
if ($CheckEnvironment) { Write-Output 'Deployed toolchain verified; no build or download required.'; return }
if ($Name -eq 'global') { throw 'The name global is reserved' }
$manifestFile = Get-Item -LiteralPath $Manifest -ErrorAction Stop
$plan = Get-Content -LiteralPath $manifestFile.FullName -Raw | ConvertFrom-Json
if ($plan.toc_version -ne 'ReplaceIoChunkHashWithIoHash' -or $plan.header_version -ne 'SoftPackageReferencesOffset') {
    throw 'Unsupported container versions; this deployment is verified for PBZ UE5.7.4'
}
if ($plan.mount_point -ne '../../../' -or @($plan.packages).Count -eq 0) { throw 'Invalid mount point or empty package whitelist' }
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($chunk in $plan.chunks) {
    if ($chunk.id -notmatch '^[a-fA-F0-9]{24}$' -or -not $seen.Add($chunk.id)) { throw 'Invalid or duplicate chunk ID' }
    if ($chunk.sha256 -notmatch '^[a-fA-F0-9]{64}$' -or $chunk.size -lt 0) { throw 'Each chunk requires size and SHA-256' }
}
$packageIds = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($package in $plan.packages) {
    if (-not $packageIds.Add($package.chunk_id) -or -not $seen.Contains($package.chunk_id)) { throw 'Invalid package chunk whitelist' }
    if ($package.path -notmatch '^ProjectPBZ/.+\.uasset$' -or $package.path -match '(^|/)\.\.(/|$)|\\') { throw 'Invalid physical package path' }
    $entry = @($plan.chunks | Where-Object id -eq $package.chunk_id)
    if ($entry.Count -ne 1 -or $entry[0].path -cne $package.path) { throw 'Package path does not match its data chunk' }
}
$output = if ($OutputDirectory) { [IO.Path]::GetFullPath($OutputDirectory) } else { Join-Path $config.project_root "Backups/$Name" }
if (Test-Path -LiteralPath $output) { throw "Output already exists; nothing overwritten: $output" }
$work = Join-Path $config.project_root ('.tmp/packer-' + $Name + '-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $work 'input/raw-chunks'),(Join-Path $work 'candidate'),(Join-Path $work 'mount') -Force | Out-Null
Write-Host "WorkDir: $work"

# 冻结输入，并先检查摘要，防止误装旧文件或处理期间资源被修改。
foreach ($chunk in $plan.chunks) {
    $source = Join-Path $manifestFile.DirectoryName ('raw-chunks/' + $chunk.id + '.bin')
    $target = Join-Path $work ('input/raw-chunks/' + $chunk.id + '.bin')
    Copy-Item -LiteralPath $source -Destination $target
    if ((Get-Item -LiteralPath $target).Length -ne $chunk.size -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $chunk.sha256) {
        throw "Input chunk length or hash mismatch: $($chunk.id)"
    }
}
$frozenManifest = Join-Path $work 'input/repack-manifest.json'
$plan | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $frozenManifest -Encoding utf8NoBOM
$utoc = Join-Path $work "candidate/$Name.utoc"
Invoke-PackerCommand (Join-Path $PSScriptRoot 'bin/pbz_iostore_pack.exe') @($frozenManifest,$utoc) (Join-Path $work 'pack.log')
Invoke-PackerCommand (Join-Path $PSScriptRoot 'bin/retoc.exe') @('info',$utoc) (Join-Path $work 'info.log')
Invoke-PackerCommand (Join-Path $PSScriptRoot 'bin/retoc.exe') @('verify',$utoc) (Join-Path $work 'verify.log')

# 挂载目录只含新包和必要 global 数据，不允许回退读取原游戏的目标资产。
Get-ChildItem -LiteralPath (Join-Path $work 'candidate') -File | Copy-Item -Destination (Join-Path $work 'mount')
foreach ($globalFile in @('global.utoc','global.ucas')) {
    Copy-Item -LiteralPath (Join-Path $config.paks $globalFile) -Destination (Join-Path $work 'mount')
}
$assets = @($plan.packages | ForEach-Object path)
$assetsFile = Join-Path $work 'assets.json'
ConvertTo-Json -InputObject $assets | Set-Content -LiteralPath $assetsFile -Encoding utf8NoBOM
Invoke-PackerCommand $config.pwsh @('-NoProfile','-File',(Join-Path $PSScriptRoot 'Invoke-Cue.ps1'),'-Action','extract','-WorkDir',(Join-Path $work 'readback'),'-AssetsJson',$assetsFile,'-Paks',(Join-Path $work 'mount')) (Join-Path $work 'readback.log')
$readback = Get-Content -LiteralPath (Join-Path $work 'readback/repack-manifest.json') -Raw | ConvertFrom-Json
if (@($readback.packages).Count -ne @($plan.packages).Count -or @($readback.chunks).Count -ne @($plan.chunks).Count) { throw 'Readback whitelist differs' }
foreach ($chunk in $plan.chunks) {
    $actual = @($readback.chunks | Where-Object id -eq $chunk.id)
    if ($actual.Count -ne 1 -or $actual[0].size -ne $chunk.size -or $actual[0].sha256 -ne $chunk.sha256) { throw "Readback mismatch: $($chunk.id)" }
}

# 所有检查通过后交付三件套；报告和完整诊断只保存到 .tmp。
$copied = @()
try {
    New-Item -ItemType Directory -Path $output | Out-Null
    foreach ($file in Get-ChildItem -LiteralPath (Join-Path $work 'candidate') -File) {
        $target = Join-Path $output $file.Name
        Copy-Item -LiteralPath $file.FullName -Destination $target
        $copied += $target
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash) { throw 'Delivery hash mismatch' }
    }
    if ($copied.Count -ne 3) { throw 'Expected exactly three output files' }
} catch {
    foreach ($path in $copied) { Remove-Item -LiteralPath $path -Force }
    if ((Test-Path -LiteralPath $output) -and @(Get-ChildItem -LiteralPath $output -Force).Count -eq 0) { [IO.Directory]::Delete($output) }
    throw
}
$result = [ordered]@{ output=$output; work_dir=$work; packages=$assets; chunk_count=@($plan.chunks).Count; retoc_verified=$true; readback_hashes_verified=$true; installed=$false; runtime_tested=$false; files=@($copied | ForEach-Object { @{path=$_;sha256=(Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash} }) }
$result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $work 'result.json') -Encoding utf8NoBOM
[pscustomobject]@{OutputDirectory=$output;Files=$copied;Report=(Join-Path $work 'result.json')}
