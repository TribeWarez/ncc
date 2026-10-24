$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "client-py\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "client-py venv missing. Create it and install .[dev] first."
}
Push-Location (Join-Path $root "client-py")
try {
    & $python -m ncc --demo @args
} finally {
    Pop-Location
}
