$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    & python .\scripts\vega.py
    exit $LASTEXITCODE
}

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
    & py .\scripts\vega.py
    exit $LASTEXITCODE
}

Write-Host "Python was not found. Install Python or check PATH."
exit 1
