param([switch]$Nym)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$core = Join-Path $root "core"
if (-not (Test-Path $core)) {
    $core = Join-Path (Split-Path -Parent $root) "Nysiris-Core"
}
$python = Join-Path $root "client-py\.venv\Scripts\python.exe"

Write-Host "== Nysiris-Core ==" -ForegroundColor Cyan
Push-Location $core
try {
    cargo fmt --check
    if ($LASTEXITCODE -ne 0) { throw "cargo fmt failed" }
    cargo clippy --workspace --all-targets -- -D warnings
    if ($LASTEXITCODE -ne 0) { throw "cargo clippy failed" }
    cargo test --workspace
    if ($LASTEXITCODE -ne 0) { throw "cargo test failed" }
} finally {
    Pop-Location
}

Write-Host "== ncc-daemon ==" -ForegroundColor Cyan
Push-Location (Join-Path $root "ncc-daemon")
try {
    cargo fmt --check
    if ($LASTEXITCODE -ne 0) { throw "cargo fmt failed" }
    cargo clippy --all-targets -- -D warnings
    if ($LASTEXITCODE -ne 0) { throw "cargo clippy failed" }
    cargo test
    if ($LASTEXITCODE -ne 0) { throw "cargo test failed" }
    if ($Nym) {
        cargo check --features nym
        if ($LASTEXITCODE -ne 0) { throw "cargo check --features nym failed" }
    }
} finally {
    Pop-Location
}

Write-Host "== client-py ==" -ForegroundColor Cyan
if (-not (Test-Path $python)) {
    throw "client-py venv missing. Run: cd client-py; py -3.13 -m venv .venv; .\.venv\Scripts\python -m pip install -e '.[dev]'"
}
Push-Location (Join-Path $root "client-py")
try {
    & $python -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw "ruff failed" }
    & $python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
} finally {
    Pop-Location
}

Write-Host "All checks passed." -ForegroundColor Green
