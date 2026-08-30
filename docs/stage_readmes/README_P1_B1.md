# Target-Aware Portability P1-B.1

Place this whole folder under:

`C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트\Target_Aware_Portability_P1_B1`

It uses the parent project's `.venv`.

## 1. Verify
```powershell
cd "C:\Users\dykim\OneDrive\바탕 화면\SCIE 논문 프로젝트"

Test-Path ".\.venv\Scripts\python.exe"
Test-Path ".\Target_Aware_Portability_P1_B1\03_src\p1_portability_simulation_b1.py"
Test-Path ".\Target_Aware_Portability_P1_B1\scripts\run_p1b1_smoke.ps1"
Test-Path ".\Target_Aware_Portability_P1_B1\scripts\run_p1b1_core_gate.ps1"
Test-Path ".\Target_Aware_Portability_P1_B1\scripts\run_p1b1_full_gate.ps1"
```

## 2. Run Smoke only
```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Target_Aware_Portability_P1_B1\scripts\run_p1b1_smoke.ps1
```

Do not run Core or Full until the Smoke output is reviewed.

## Important
The old `Target_Aware_Portability_P1\05_outputs\p1_core_gate` folder should remain untouched as the calibration/audit trail.
