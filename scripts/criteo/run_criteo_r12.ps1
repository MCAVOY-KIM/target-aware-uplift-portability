$ErrorActionPreference = "Stop"

$R12Root = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $R12Root

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Code = Join-Path $R12Root "03_src\criteo_r12_propensity_adjustment.py"
$Data = Join-Path $ProjectRoot "02_data\raw\criteo-research-uplift-v2.1.csv.gz"
$R0 = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R0\05_outputs\criteo_r0_audit"
$R01 = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R01\05_outputs\criteo_r01_shift_materialization"
$R1Source = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R1\03_src\criteo_r1_population_models.py"
$R11Source = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R11\03_src\criteo_r11_budget_randomization_audit.py"
$R1Out = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R1\05_outputs\criteo_r1"
$R11Out = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R11\05_outputs\criteo_r11"
$Out = Join-Path $R12Root "05_outputs\criteo_r12"

foreach ($p in @($Python,$Code,$Data,$R0,$R01,$R1Source,$R11Source,$R1Out,$R11Out)) {
  if (-not (Test-Path $p)) { throw "Required path not found: $p" }
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null

& $Python $Code `
  --data $Data `
  --r0-outdir $R0 `
  --r01-outdir $R01 `
  --r1-source $R1Source `
  --r11-source $R11Source `
  --r1-outdir $R1Out `
  --r11-outdir $R11Out `
  --outdir $Out `
  --chunksize 500000
