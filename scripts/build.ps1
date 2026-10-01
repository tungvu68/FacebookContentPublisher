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
    & (Join-Path $PSScriptRoot "test.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Pre-build checks failed." }

    & (Join-Path $venvScripts "pyinstaller.exe") --noconfirm --clean --windowed --onedir `
        --name FacebookContentPublisher `
        --paths src `
        --hidden-import logging.config `
        --collect-all openai `
        --collect-all keyring `
        --collect-all certifi `
        --add-data "alembic.ini;." `
        --add-data "migrations;migrations" `
        src\facebook_content_publisher\main.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

    $executable = Join-Path $projectRoot "dist\FacebookContentPublisher\FacebookContentPublisher.exe"
    if (-not (Test-Path -LiteralPath $executable)) {
        throw "Expected executable was not created: $executable"
    }
    Write-Host "Build complete: $executable"
}
finally {
    Pop-Location
}
