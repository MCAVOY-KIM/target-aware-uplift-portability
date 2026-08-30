$ErrorActionPreference = "Stop"

$R1FRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $R1FRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Code = Join-Path $R1FRoot "03_src\criteo_r1f_finalization.py"
$Data = Join-Path $ProjectRoot "02_data\raw\criteo-research-uplift-v2.1.csv.gz"
$R0 = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R0\05_outputs\criteo_r0_audit"
$R01 = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R01\05_outputs\criteo_r01_shift_materialization"
$R1Source = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R1\03_src\criteo_r1_population_models.py"
$R12Source = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R12\03_src\criteo_r12_propensity_adjustment.py"
$R1Out = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R1\05_outputs\criteo_r1"
$R12Out = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R12\05_outputs\criteo_r12"
$Out = Join-Path $R1FRoot "05_outputs\criteo_r1f"

foreach ($p in @($Python,$Code,$Data,$R0,$R01,$R1Source,$R12Source,$R1Out,$R12Out)) {
  if (-not (Test-Path $p)) { throw "Required path not found: $p" }
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null

& $Python $Code `
  --data $Data `
  --r0-outdir $R0 `
  --r01-outdir $R01 `
  --r1-source $R1Source `
  --r12-source $R12Source `
  --r1-outdir $R1Out `
  --r12-outdir $R12Out `
  --outdir $Out `
  --chunksize 500000
