# Target-Aware Portability — Criteo R0

Place this folder at:

`C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트\Target_Aware_Portability_Criteo_R0`

The raw Criteo file should already be at:

`C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트\02_data\raw\criteo-research-uplift-v2.1.csv.gz`

## Verify

```powershell
cd "C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트"

Test-Path ".\.venv\Scripts\python.exe"
Test-Path ".\02_data\raw\criteo-research-uplift-v2.1.csv.gz"
Test-Path ".\Target_Aware_Portability_Criteo_R0\03_src\criteo_r0_audit.py"
Test-Path ".\Target_Aware_Portability_Criteo_R0\scripts\run_criteo_r0_audit.ps1"
```

All four should be `True`.

## Run

```powershell
Set-ExecutionPolicy -Scope Process Bypass

.\Target_Aware_Portability_Criteo_R0\scripts\run_criteo_r0_audit.ps1
```

The script streams the ~14M-row gzip file and may take several minutes.

It does not fit uplift models.

## Send back

Please send:
1. the complete console output;
2. ZIP of `05_outputs\criteo_r0_audit`.

After forensic review, R1 population construction and model-fitting code will be frozen.
