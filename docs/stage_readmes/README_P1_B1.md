> **Public-release note:** This is an archival stage note. Author-specific local paths were replaced with `<PROJECT_ROOT>`; use the repository-root reproduction commands in `docs/reproducibility.md` for current execution.

# Target-Aware Portability P1-B.1

Place this whole folder under:

`<PROJECT_ROOT>\Target_Aware_Portability_P1_B1`

It uses the parent project's `.venv`.

## 1. Verify
```powershell
cd "<PROJECT_ROOT>"

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
