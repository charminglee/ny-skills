param(
    [Parameter(Mandatory)][string]$WorkDir,
    [string]$ProjectRoot = 'E:\PbzMod'
)

$ErrorActionPreference = 'Stop'
$taskCommit = '885a8dae740cb1ce1e41ff2e74f67f9f0c118237'
$taskWork = [IO.Path]::GetFullPath($WorkDir)
$taskTemp = [IO.Path]::GetFullPath((Join-Path $ProjectRoot '.tmp')).TrimEnd('\') + '\'
if (-not $taskWork.StartsWith($taskTemp, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'WorkDir must be inside ProjectRoot/.tmp/'
}
$taskSource = Join-Path $taskWork 'retoc-upstream'
$taskPacker = Join-Path $taskWork 'packer'
$taskTarget = Join-Path $taskWork 'target'
if (Test-Path -LiteralPath $taskPacker) { throw 'Build directory already prepared; use a fresh WorkDir' }
New-Item -ItemType Directory -Path $taskWork -Force | Out-Null
if (-not (Test-Path -LiteralPath $taskSource)) {
    git clone --no-checkout --filter=blob:none 'https://github.com/trumank/retoc.git' $taskSource | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'retoc clone failed' }
    git -C $taskSource fetch --depth 1 origin $taskCommit | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'retoc commit fetch failed' }
    git -C $taskSource checkout --detach $taskCommit | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'retoc checkout failed' }
}
$taskHead = git -C $taskSource rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $taskHead.Trim() -ne $taskCommit) { throw 'Unexpected retoc commit' }
$taskDirty = git -C $taskSource status --porcelain
if ($LASTEXITCODE -ne 0 -or $taskDirty) { throw 'Upstream source is not clean' }
New-Item -ItemType Directory -Path (Join-Path $taskPacker 'src') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'packer\Cargo.toml') -Destination $taskPacker
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'packer\src\main.rs') -Destination (Join-Path $taskPacker 'src')
Copy-Item -LiteralPath (Join-Path $taskSource 'Cargo.lock') -Destination $taskPacker
cargo build --release --locked -p retoc_cli --manifest-path (Join-Path $taskSource 'Cargo.toml') `
    --target-dir $taskTarget *> (Join-Path $taskWork 'retoc-build.log')
if ($LASTEXITCODE -ne 0) {
    Get-Content -LiteralPath (Join-Path $taskWork 'retoc-build.log') -Tail 25 | Out-Host
    throw 'retoc build failed'
}
cargo build --release --manifest-path (Join-Path $taskPacker 'Cargo.toml') `
    --target-dir $taskTarget *> (Join-Path $taskWork 'packer-build.log')
if ($LASTEXITCODE -ne 0) {
    Get-Content -LiteralPath (Join-Path $taskWork 'packer-build.log') -Tail 25 | Out-Host
    throw 'packer build failed'
}
[PSCustomObject]@{
    Packer = Join-Path $taskTarget 'release\pbz_iostore_pack.exe'
    Retoc = Join-Path $taskTarget 'release\retoc.exe'
    UpstreamCommit = $taskCommit
}
