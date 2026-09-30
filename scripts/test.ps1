[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvScripts = Join-Path $projectRoot ".venv\Scripts"
$python = Join-Path $venvScripts "python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment not found. Run .\scripts\setup.ps1 first."
}

Push-Location $projectRoot
try {
    $env:FCP_DATA_DIR = Join-Path $projectRoot ".tmp\test-runtime"
    & (Join-Path $venvScripts "ruff.exe") format --check .
    if ($LASTEXITCODE -ne 0) { throw "Ruff format check failed." }

    & (Join-Path $venvScripts "ruff.exe") check .
    if ($LASTEXITCODE -ne 0) { throw "Ruff lint failed." }

    & $python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "Pytest failed." }

    $env:QT_QPA_PLATFORM = "offscreen"
    & $python -m facebook_content_publisher --smoke-test
    if ($LASTEXITCODE -ne 0) { throw "Qt smoke test failed." }
}
finally {
    Pop-Location
}
