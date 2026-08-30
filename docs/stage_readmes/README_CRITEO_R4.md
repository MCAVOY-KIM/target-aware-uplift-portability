> **Public-release note:** This is an archival stage note. Author-specific local paths were replaced with `<PROJECT_ROOT>`; use the repository-root reproduction commands in `docs/reproducibility.md` for current execution.

# Target-Aware Portability — Criteo R4

Place at:

`<PROJECT_ROOT>\Target_Aware_Portability_Criteo_R4`

R4 uses only the already completed R2/R3 output folders. It does not read the raw Criteo data.

## Verify

```powershell
cd "<PROJECT_ROOT>"

Test-Path ".\.venv\Scripts\python.exe"
Test-Path ".\Target_Aware_Portability_Criteo_R2\05_outputs\criteo_r2"
Test-Path ".\Target_Aware_Portability_Criteo_R3\05_outputs\criteo_r3"
Test-Path ".\Target_Aware_Portability_Criteo_R4\03_src\criteo_r4_evidence_freeze.py"
Test-Path ".\Target_Aware_Portability_Criteo_R4\scripts\run_criteo_r4.ps1"
```

All five should be True.

## Run

```powershell
Set-ExecutionPolicy -Scope Process Bypass

.\Target_Aware_Portability_Criteo_R4\scripts\run_criteo_r4.ps1
```

This should be fast because it only summarizes existing CSV outputs.

Send the console output and ZIP of:

`Target_Aware_Portability_Criteo_R4\05_outputs\criteo_r4`
