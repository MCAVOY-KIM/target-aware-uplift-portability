# Target-Aware Portability — Criteo R1F

Place at:

`C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트\Target_Aware_Portability_Criteo_R1F`

Keep all previous Criteo folders unchanged.

## Verify

```powershell
cd "C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트"

Test-Path ".\.venv\Scripts\python.exe"
Test-Path ".\02_data\raw\criteo-research-uplift-v2.1.csv.gz"
Test-Path ".\Target_Aware_Portability_Criteo_R1\05_outputs\criteo_r1\models"
Test-Path ".\Target_Aware_Portability_Criteo_R12\05_outputs\criteo_r12\propensity_models"
Test-Path ".\Target_Aware_Portability_Criteo_R1F\03_src\criteo_r1f_finalization.py"
Test-Path ".\Target_Aware_Portability_Criteo_R1F\scripts\run_criteo_r1f.ps1"
```

All six should be True.

## Run

```powershell
Set-ExecutionPolicy -Scope Process Bypass

.\Target_Aware_Portability_Criteo_R1F\scripts\run_criteo_r1f.ps1
```

R1F does not fit a new uplift model or a new propensity model.

It only materializes the already-defined top-q rule without decimal
serialization and freezes the final source winners.

## Send back

Send:
1. complete console output;
2. ZIP of `05_outputs\criteo_r1f`.

If the technical gate passes, R2 is authorized with Criteo explicitly treated
as a secondary large-scale application/benchmark.
