$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host 'First-time setup: installing dependencies...' -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot 'setup.ps1')
}
Write-Host 'Starting Study Transcribe at http://127.0.0.1:5000 ...' -ForegroundColor Cyan
& $python (Join-Path $PSScriptRoot 'webapp\app.py')
