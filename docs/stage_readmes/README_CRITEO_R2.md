# Target-Aware Portability — Criteo R2

Place at:

`C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트\Target_Aware_Portability_Criteo_R2`

Keep all prior Criteo folders unchanged.

## Verify

```powershell
cd "C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트"

Test-Path ".\.venv\Scripts\python.exe"
Test-Path ".\02_data\raw\criteo-research-uplift-v2.1.csv.gz"
Test-Path ".\Target_Aware_Portability_Criteo_R1\05_outputs\criteo_r1\models"
Test-Path ".\Target_Aware_Portability_Criteo_R12\05_outputs\criteo_r12\propensity_models"
Test-Path ".\Target_Aware_Portability_Criteo_R1F\05_outputs\criteo_r1f\criteo_r1f_source_winners.csv"
Test-Path ".\Target_Aware_Portability_Criteo_R2\03_src\criteo_r2_portability.py"
Test-Path ".\Target_Aware_Portability_Criteo_R2\scripts\run_criteo_r2.ps1"
```

All seven should be True.

## Run

```powershell
Set-ExecutionPolicy -Scope Process Bypass

.\Target_Aware_Portability_Criteo_R2\scripts\run_criteo_r2.ps1
```

R2 is computationally heavy:
- it rebuilds the three source/target scenarios;
- scores all six frozen models;
- fits three X-only source-vs-target density-ratio models;
- streams source_infer and target_infer;
- computes 15 transported contrasts per scenario.

Target treatment/outcomes remain unused.

## Send back

Send:
1. complete console output;
2. ZIP of `05_outputs\criteo_r2`.

Do NOT unlock target outcomes yourself after R2. R3 will be frozen only after
the R2 outputs have been forensically reviewed.
