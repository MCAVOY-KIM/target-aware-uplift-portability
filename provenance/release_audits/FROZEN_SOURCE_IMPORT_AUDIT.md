# Frozen Source Import Audit — Batch 1

This package was assembled directly from the user's frozen project folders.
No analysis source code was reconstructed from the manuscript.

## Included
- P1-B1 final/full simulation source and final full-gate outputs.
- P1-C rare-binary final/full simulation source and final full-gate outputs.
- Criteo R0, R0.1, R1, R1.2, R1F, R2, R3 and R4_FIXED source.
- Final textual/CSV/JSON/PNG evidence outputs for those Criteo stages.
- Stage protocols, decision/freeze logs and PowerShell execution scripts.
- SHA-256 manifests computed from the uploaded frozen files.

## Intentionally excluded
- `__pycache__` / `.pyc`.
- Smoke and calibration/core-only duplicate simulation outputs.
- Per-scenario `partial/` files because full replication tables are retained.
- `.joblib` serialized models/nuisances in this public-oriented package.
  They can be regenerated from the frozen source when the exact environment is available.
- Raw CRITEO-UPLIFT data.
- Intermediate archive ZIPs.

## Important missing dependency: Criteo R11
`criteo_r12_propensity_adjustment.py` explicitly verifies and imports the frozen R11 source
and reads the R11 corrected-selection outputs. Therefore a full clean rerun of the Criteo
chain cannot start from R0 and pass through R12 until `Target_Aware_Portability_Criteo_R11`
is imported.

The R12 source expects the frozen R11 source SHA-256:
`fa011f1d63e0394174e73e48989ad4b80882827c1c6c990b61fe4bbd29e3176e`.

## Cross-stage integrity check
The R4_FIXED source hard-codes SHA-256 checks for ten primary R2/R3 artifacts.
All ten hashes match the files in the uploaded batch.
