> **Public-release note:** This is an archival stage note. Author-specific local paths were replaced with `<PROJECT_ROOT>`; use the repository-root reproduction commands in `docs/reproducibility.md` for current execution.

# Criteo R0.1

Place at:

`<PROJECT_ROOT>\Target_Aware_Portability_Criteo_R01`

Keep the completed R0 folder unchanged.

## Verify

```powershell
cd "<PROJECT_ROOT>"

Test-Path ".\.venv\Scripts\python.exe"
Test-Path ".\02_data\raw\criteo-research-uplift-v2.1.csv.gz"
Test-Path ".\Target_Aware_Portability_Criteo_R0\05_outputs\criteo_r0_audit"
Test-Path ".\Target_Aware_Portability_Criteo_R01\03_src\criteo_r01_shift_materialization.py"
Test-Path ".\Target_Aware_Portability_Criteo_R01\scripts\run_criteo_r01.ps1"
```

All five should be True.

## Run

```powershell
Set-ExecutionPolicy -Scope Process Bypass

.\Target_Aware_Portability_Criteo_R01\scripts\run_criteo_r01.ps1
```

This reads X only. It never reads treatment, visit, conversion, or exposure.

Send the full console output and ZIP of:

`Target_Aware_Portability_Criteo_R01\05_outputs\criteo_r01_shift_materialization`

After PASS, R1 population membership and source-model library will be frozen.
