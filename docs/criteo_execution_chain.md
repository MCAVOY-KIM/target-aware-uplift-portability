# Criteo Frozen Execution Chain

| Stage | Purpose | Target A/Y available? |
|---|---|---:|
| R0 | X-only audit and shift calibration | No |
| R0.1 | Full-X shift materialization | No |
| R1 | Population roles and fixed model library | No |
| R1.1 | Budget/randomization audit | No |
| R1.2 | Propensity-adjusted source selection | No |
| R1F | Exact policy materialization | No |
| R2 | Portability assessment | **No** |
| R3 | Held-out target benchmark | **Yes, first unlock** |
| R4 | Frozen evidence synthesis | Already unlocked; no new fitting |

R1.1/R1.2 failures remain visible in the repository and manuscript supplement.

The R11 source hash required by R1.2 is:

`fa011f1d63e0394174e73e48989ad4b80882827c1c6c990b61fe4bbd29e3176e`

The imported R11 source matches this value.

R3 additionally verifies exact frozen R2 artifact hashes before the first target-outcome unlock.
