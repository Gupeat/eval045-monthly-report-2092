Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python run_all.py @args
exit $LASTEXITCODE
