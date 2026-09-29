$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment not found: $python"
}
Write-Host 'Starting Study Transcribe at http://127.0.0.1:5000 ...' -ForegroundColor Cyan
& $python (Join-Path $PSScriptRoot 'webapp\app.py')
