# Book-level driver for study-transcribe: runs run.py once per page range
# in a visible console so the user can watch progress live.
#
# One-liner usage (opens its own window when launched via Start-Process):
#   powershell -NoExit -ExecutionPolicy Bypass -File transcribe_book.ps1 `
#     -Pdf "<book.pdf>" -Ranges "6-32,33-51,..." [-Prose] [-DoneMarker <file>]
param(
    [Parameter(Mandatory = $true)][string]$Pdf,
    [Parameter(Mandatory = $true)][string]$Ranges,
    [switch]$Prose,
    [string]$DoneMarker
)

$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$runpy = Join-Path $PSScriptRoot "run.py"
if (-not (Test-Path -LiteralPath $py)) {
    throw "Falta el entorno Python: $py. Sigue la instalacion en README.md."
}
$list = $Ranges -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ }
$t0 = Get-Date
$i = 0
$failed = @()

Write-Host ("Libro: {0}" -f $Pdf) -ForegroundColor Yellow
Write-Host ("{0} rangos a transcribir; modo prose: {1}`n" -f $list.Count, [bool]$Prose) -ForegroundColor Yellow

foreach ($r in $list) {
    $i++
    Write-Host ("=== [{0}/{1}] paginas {2} ===" -f $i, $list.Count, $r) -ForegroundColor Cyan
    $argv = @($runpy, $Pdf, "--pages", $r)
    if ($Prose) { $argv += "--prose" }
    & $py @argv
    if ($LASTEXITCODE -ne 0) {
        Write-Host ("FALLO en rango {0} (exit {1})" -f $r, $LASTEXITCODE) -ForegroundColor Red
        $failed += $r
    }
}

$dt = (Get-Date) - $t0
if ($failed.Count) {
    Write-Host ("`nTERMINADO CON FALLOS ({0}) en {1:mm\:ss}: {2}" -f $failed.Count, $dt, ($failed -join ", ")) -ForegroundColor Red
} else {
    Write-Host ("`nLIBRO COMPLETO en {0:mm\:ss}" -f $dt) -ForegroundColor Green
}
if ($DoneMarker) { ($failed -join ",") | Out-File $DoneMarker -Encoding ascii }
