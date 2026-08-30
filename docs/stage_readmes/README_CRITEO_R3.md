# Target-Aware Portability — Criteo R3

Place at:

`C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트\Target_Aware_Portability_Criteo_R3`

Do not modify any previous R2 output.

## Verify

```powershell
cd "C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트"

Test-Path ".\.venv\Scripts\python.exe"
Test-Path ".\02_data\raw\criteo-research-uplift-v2.1.csv.gz"
Test-Path ".\Target_Aware_Portability_Criteo_R1\05_outputs\criteo_r1\models"
Test-Path ".\Target_Aware_Portability_Criteo_R2\05_outputs\criteo_r2\criteo_r2_portability_bounds.csv"
Test-Path ".\Target_Aware_Portability_Criteo_R3\03_src\criteo_r3_target_benchmark.py"
Test-Path ".\Target_Aware_Portability_Criteo_R3\scripts\run_criteo_r3.ps1"
```

All six should be True.

## Run

```powershell
Set-ExecutionPolicy -Scope Process Bypass

.\Target_Aware_Portability_Criteo_R3\scripts\run_criteo_r3.ps1
```

This is the first stage that intentionally uses target treatment and visit.

R3 first verifies cryptographic hashes of the frozen R2 outputs. If R2 has
changed, it stops before benchmarking.

R3 is computationally heavy because it fits target benchmark nuisances and
scores the frozen six-model library on target_infer for all three scenarios.

## Send back

Send:
1. the complete console output;
2. ZIP of `05_outputs\criteo_r3`.

Do not interpret or rerun based on whether R2 looks good or bad against R3.
The first observed benchmark is the result we keep.
