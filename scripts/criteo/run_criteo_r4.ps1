$ErrorActionPreference = "Stop"

$R4Root = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $R4Root

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Code = Join-Path $R4Root "03_src\criteo_r4_evidence_freeze.py"
$R2 = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R2\05_outputs\criteo_r2"
$R3 = Join-Path $ProjectRoot "Target_Aware_Portability_Criteo_R3\05_outputs\criteo_r3"
$Out = Join-Path $R4Root "05_outputs\criteo_r4"

foreach ($p in @($Python,$Code,$R2,$R3)) {
  if (-not (Test-Path $p)) { throw "Required path not found: $p" }
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null

& $Python $Code `
  --r2-outdir $R2 `
  --r3-outdir $R3 `
  --outdir $Out
