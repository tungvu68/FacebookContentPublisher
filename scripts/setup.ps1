[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$toolsDir = Join-Path $projectRoot ".tools"
$uvDir = Join-Path $toolsDir "uv"
$uvExe = Join-Path $uvDir "uv.exe"
$venvDir = Join-Path $projectRoot ".venv"

New-Item -ItemType Directory -Force -Path $uvDir | Out-Null

if (-not (Test-Path -LiteralPath $uvExe)) {
    $archive = Join-Path $toolsDir "uv.zip"
    $uvUrl = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
    Write-Host "Downloading project-local uv..."
    Invoke-WebRequest -Uri $uvUrl -OutFile $archive
    Expand-Archive -LiteralPath $archive -DestinationPath $uvDir -Force
    Remove-Item -LiteralPath $archive
}

$env:UV_PYTHON_INSTALL_DIR = Join-Path $toolsDir "python"
$env:UV_CACHE_DIR = Join-Path $toolsDir "uv-cache"

Push-Location $projectRoot
try {
    & $uvExe python install 3.12
    if (-not (Test-Path -LiteralPath (Join-Path $venvDir "Scripts\python.exe"))) {
        & $uvExe venv --python 3.12 $venvDir
    }
    & $uvExe pip install --python (Join-Path $venvDir "Scripts\python.exe") -e ".[dev]"
    & (Join-Path $venvDir "Scripts\python.exe") --version
    Write-Host "Setup complete. Run .\scripts\run.ps1"
}
finally {
    Pop-Location
}
