[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $launcher) {
        throw 'Python 3.11 or later is required. Install it from https://www.python.org/downloads/ and run this script again.'
    }

    Write-Host 'Creating the local Python environment...' -ForegroundColor Cyan
    & py -3.11 -m venv .venv
}

Write-Host 'Installing Study Transcribe dependencies...' -ForegroundColor Cyan
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt

Write-Host ''
Write-Host 'Setup complete. Start the app with .\start-web.ps1 or double-click start-web.cmd.' -ForegroundColor Green
