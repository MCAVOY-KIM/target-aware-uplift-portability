# Cross-Platform Reproducibility Fix

Fresh-clone testing on Windows revealed two repository-engineering issues.

## 1. R11 source SHA mismatch

Observed Windows checkout hash:

`e5c4920a6491972a2080042d78fd099245542aa6fa6c02e2cfc8bf5386cbfb97`

Original frozen LF hash:

`fa011f1d63e0394174e73e48989ad4b80882827c1c6c990b61fe4bbd29e3176e`

The observed hash is exactly the SHA-256 obtained when the original R11 file is converted from LF to CRLF. No source-code content discrepancy was identified.

Fix:
- source hashes use canonical LF;
- a complete 11-file canonical-LF manifest is committed;
- `.gitattributes` specifies deterministic line endings.

## 2. Manuscript asset script dirtied the working tree

The earlier script wrote regenerated assets over tracked frozen outputs.

Fix:
- regenerated assets now go to `reproduction_runs/manuscript_assets/`;
- frozen `outputs/` are read-only inputs;
- Table IV is semantically compared against the frozen table;
- figures are regenerated without requiring PNG byte identity across rendering platforms.

These are repository portability fixes and do not change the scientific results.
