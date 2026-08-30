# Target-Aware Portability — Criteo R1.1

Place at:

`C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트\Target_Aware_Portability_Criteo_R11`

Keep R0, R0.1 and R1 unchanged.

## Verify

```powershell
cd "C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트"

Test-Path ".\.venv\Scripts\python.exe"
Test-Path ".\02_data\raw\criteo-research-uplift-v2.1.csv.gz"
Test-Path ".\Target_Aware_Portability_Criteo_R1\03_src\criteo_r1_population_models.py"
Test-Path ".\Target_Aware_Portability_Criteo_R1\05_outputs\criteo_r1\models"
Test-Path ".\Target_Aware_Portability_Criteo_R11\03_src\criteo_r11_budget_randomization_audit.py"
Test-Path ".\Target_Aware_Portability_Criteo_R11\scripts\run_criteo_r11.ps1"
```

All six should be True.

## Run

```powershell
Set-ExecutionPolicy -Scope Process Bypass

.\Target_Aware_Portability_Criteo_R11\scripts\run_criteo_r11.ps1
```

R1.1 does NOT retrain the six-model libraries.

It re-scores source_train/source_select using the frozen R1 artifacts, fixes exact top-q tie handling, recomputes source winners, and audits randomization.

No target treatment/outcome or source_infer outcome is read.

## Send back

Send complete console output and ZIP of:

`Target_Aware_Portability_Criteo_R11\05_outputs\criteo_r11`

If PASS, the corrected winners and tie-breaking rule become final inputs to R2.
