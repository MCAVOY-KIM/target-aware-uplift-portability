$ErrorActionPreference = "Stop"

$R1Root = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $R1Root

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Code = Join-Path $R1Root "03_src\criteo_r1_population_models.py"
$Data = Join-Path $ProjectRoot "02_data\raw\criteo-research-uplift-v2.1.csv.gz"
$R0 = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R0\05_outputs\criteo_r0_audit"
$R01 = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R01\05_outputs\criteo_r01_shift_materialization"
$Out = Join-Path $R1Root "05_outputs\criteo_r1"

foreach ($p in @($Python,$Code,$Data,$R0,$R01)) {
  if (-not (Test-Path $p)) { throw "Required path not found: $p" }
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null

& $Python $Code `
  --data $Data `
  --r0-outdir $R0 `
  --r01-outdir $R01 `
  --outdir $Out `
  --chunksize 500000
