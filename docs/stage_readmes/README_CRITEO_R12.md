# Target-Aware Portability — Criteo R1.2

Place at:

`C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트\Target_Aware_Portability_Criteo_R12`

Keep R0, R0.1, R1, and R1.1 unchanged.

## Verify

```powershell
cd "C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트"

Test-Path ".\.venv\Scripts\python.exe"
Test-Path ".\02_data\raw\criteo-research-uplift-v2.1.csv.gz"
Test-Path ".\Target_Aware_Portability_Criteo_R1\05_outputs\criteo_r1\models"
Test-Path ".\Target_Aware_Portability_Criteo_R11\05_outputs\criteo_r11"
Test-Path ".\Target_Aware_Portability_Criteo_R12\03_src\criteo_r12_propensity_adjustment.py"
Test-Path ".\Target_Aware_Portability_Criteo_R12\scripts\run_criteo_r12.ps1"
```

All six should be True.

## Run

```powershell
Set-ExecutionPolicy -Scope Process Bypass

.\Target_Aware_Portability_Criteo_R12\scripts\run_criteo_r12.ps1
```

R1.2:
- does not retrain the 18 candidate uplift models;
- uses source_train X,treatment to fit one frozen logistic propensity nuisance per scenario;
- uses source_select outcomes only for the already-planned source winner evaluation;
- does not use source_infer outcomes;
- does not use target treatment/outcomes.

## Send back

Send complete console output and ZIP of:

`Target_Aware_Portability_Criteo_R12\05_outputs\criteo_r12`

R2 is authorized only if every R1.2 gate passes.
