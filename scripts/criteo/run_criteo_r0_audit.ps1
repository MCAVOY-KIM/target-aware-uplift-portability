$ErrorActionPreference = "Stop"

$R0Root = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $R0Root

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Code = Join-Path $R0Root "03_src\criteo_r0_audit.py"
$Data = Join-Path $ProjectRoot "02_data\raw\criteo-research-uplift-v2.1.csv.gz"
$Out = Join-Path $R0Root "05_outputs\criteo_r0_audit"

foreach ($p in @($Python,$Code,$Data)) {
  if (-not (Test-Path $p)) { throw "Required file not found: $p" }
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null

& $Python $Code `
  --data $Data `
  --outdir $Out `
  --chunksize 500000
