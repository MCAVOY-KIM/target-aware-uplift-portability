$ErrorActionPreference = "Stop"

$R01Root = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $R01Root

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Code = Join-Path $R01Root "03_src\criteo_r01_shift_materialization.py"
$Data = Join-Path $ProjectRoot "02_data\raw\criteo-research-uplift-v2.1.csv.gz"
$R0 = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R0\05_outputs\criteo_r0_audit"
$Out = Join-Path $R01Root "05_outputs\criteo_r01_shift_materialization"

foreach ($p in @($Python,$Code,$Data,$R0)) {
  if (-not (Test-Path $p)) { throw "Required path not found: $p" }
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null

& $Python $Code `
  --data $Data `
  --r0-outdir $R0 `
  --outdir $Out `
  --chunksize 500000
