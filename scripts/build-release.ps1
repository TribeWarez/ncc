# Build the NCC Windows release bundle.
#
#   ./scripts/build-release.ps1                 # version from client-py/pyproject.toml
#   ./scripts/build-release.ps1 -Version 0.1.1
#   ./scripts/build-release.ps1 -SkipDaemon     # reuse an existing ncc-daemon.exe
#
# Produces:
#   dist/ncc-<version>-windows-x64/             ncc.exe + ncc-daemon.exe + docs
#   dist/ncc-<version>-windows-x64.zip
#   dist/SHA256SUMS.txt
#
# The daemon is built with the real Nym transport (`--features nym`), so the
# packaged app can talk to the mixnet without a Python environment.

[CmdletBinding()]
param(
    [string]$Version = "",
    [string]$Python = "python",
    [string]$DaemonPath = "",
    [switch]$SkipDaemon
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

if (-not $Version) {
    $pyproject = Get-Content (Join-Path $Root "client-py\pyproject.toml") -Raw
    if ($pyproject -notmatch '(?m)^version = "([^"]+)"') {
        throw "could not read version from client-py/pyproject.toml"
    }
    $Version = $Matches[1]
}
Write-Host "== NCC release $Version ==" -ForegroundColor Cyan

$Daemon = if ($DaemonPath) { $DaemonPath } else { Join-Path $Root "ncc-daemon\target\release\ncc-daemon.exe" }
if (-not $SkipDaemon) {
    Write-Host "== Build ncc-daemon (release, nym) ==" -ForegroundColor Cyan
    Push-Location (Join-Path $Root "ncc-daemon")
    try {
        # Native commands write progress to stderr; do not let that trip Stop.
        $ErrorActionPreference = "Continue"
        cargo build --release --features nym --locked
        $code = $LASTEXITCODE
        $ErrorActionPreference = "Stop"
        if ($code -ne 0) { throw "cargo build failed" }
    }
    finally {
        Pop-Location
    }
}
if (-not (Test-Path $Daemon)) {
    throw "ncc-daemon.exe not found at $Daemon; build it first or drop -SkipDaemon"
}
$env:NCC_DAEMON_BIN = $Daemon

$Dist = Join-Path $Root "dist"
$Name = "ncc-$Version-windows-x64"
$Stage = Join-Path $Dist $Name
$Zip = Join-Path $Dist "$Name.zip"
$Work = Join-Path $env:TEMP "ncc-pyinstaller"

Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $Work -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $Zip -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Dist | Out-Null

Write-Host "== PyInstaller ==" -ForegroundColor Cyan
$ErrorActionPreference = "Continue"
& $Python -m PyInstaller `
    --clean --noconfirm `
    --distpath $Dist `
    --workpath $Work `
    (Join-Path $Root "packaging\ncc.spec")
$code = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($code -ne 0) { throw "PyInstaller failed" }

if (-not (Test-Path (Join-Path $Dist "ncc\ncc.exe"))) {
    throw "PyInstaller did not produce dist/ncc/ncc.exe"
}
Move-Item (Join-Path $Dist "ncc") $Stage
Copy-Item $Daemon (Join-Path $Stage "ncc-daemon.exe")

Copy-Item (Join-Path $Root "LICENSE") $Stage
Copy-Item (Join-Path $Root "README.md") $Stage
Copy-Item (Join-Path $Root "SECURITY.md") $Stage

Write-Host "== Package ==" -ForegroundColor Cyan
Compress-Archive -Path $Stage -DestinationPath $Zip -CompressionLevel Optimal

$Hash = (Get-FileHash $Zip -Algorithm SHA256).Hash.ToLower()
$Sums = Join-Path $Dist "SHA256SUMS.txt"
"$Hash  $(Split-Path $Zip -Leaf)" | Set-Content -Path $Sums -Encoding ascii

$SizeMb = [math]::Round((Get-Item $Zip).Length / 1MB, 1)
Write-Host "release: $Zip ($SizeMb MB)" -ForegroundColor Green
Write-Host "sha256:  $Hash" -ForegroundColor Green
