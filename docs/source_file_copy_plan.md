# Source-file copy plan

The repository should publish **the exact frozen files that generated the manuscript evidence**, not rewritten equivalents.

## Phase 1 — copy immediately

From the local SCIE project, copy:

- `p1c_rare_binary_simulation.py` -> `src/simulation/`
- `p1c1_inferential_diagnostic.py` -> `src/simulation/`
- the P1-B.1 executable simulation source -> `src/simulation/`
- R2 `scripts/run_criteo_r2.ps1` and all Python files it invokes -> `src/criteo/r2/`
- R3 `scripts/run_criteo_r3.ps1` and all Python files it invokes -> `src/criteo/r3/`

Then add R0/R0.1/R1/R1.2/R1F/R4 stage scripts after confirming they match the frozen provenance used by R2/R3.

## Phase 2 — checksum contract

For every copied source file:

```powershell
Get-FileHash <FILE> -Algorithm SHA256
```

Record the lowercase SHA-256 in `provenance/checksums/frozen_artifacts.csv` or a dedicated source manifest.

## Do not do this

- Do not reconstruct missing source from manuscript prose.
- Do not rewrite frozen code after seeing target benchmark outcomes.
- Do not upload CRITEO raw data.
- Do not publish exploratory scripts as if they generated the frozen manuscript results.
