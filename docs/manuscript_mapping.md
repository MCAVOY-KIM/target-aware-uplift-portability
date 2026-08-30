# Manuscript-to-artifact mapping

This file maps manuscript claims to the code/output locations that should reproduce them. Paths are intentionally stable even before all files are populated.

| Manuscript component | Reproducibility location | Status |
|---|---|---|
| Section III: target-regret estimand | `src/common/` + manuscript | theory / no data artifact |
| Section IV: transported DR and simultaneous inference | `src/common/` | to populate |
| Section V: exact-truth simulation | `src/simulation/`, `configs/simulation/`, `outputs/simulation/` | to populate |
| Table II: simulation operating characteristics | `outputs/tables/` | to populate |
| Figure 2: rare-binary operating boundary | `outputs/figures/` | to populate |
| Section VI-A/B: Criteo data and emulated shift | `src/criteo/`, `configs/criteo/`, `provenance/` | to populate |
| Table III: Criteo shift audit | `outputs/tables/` | to populate |
| Section VI-C/D: source selection and outcome-blind portability | `src/criteo/`, `outputs/criteo/` | to populate |
| Section VI-E/F: held-out target benchmark | `src/criteo/`, `outputs/criteo/` | to populate |
| Table IV: portability vs benchmark | `outputs/tables/` | to populate |
| Figure 3: frozen bound vs benchmark regret | `outputs/figures/` | to populate |
| Supplement: provenance manifest | `provenance/` | initialized |

## Core empirical manuscript facts to preserve

- Candidate library: S-Logit, T-Logit, S-HGB, T-HGB, TO-HGB, DR-HGB.
- Budgets: `q = {0.10, 0.30, 0.50}`.
- Outcome-blind tolerance grid: `epsilon = {0.0005, 0.001, 0.002, 0.005}`.
- Criteo role: secondary large-scale randomized real-data application with emulated covariate shift.
- Target outcomes are unavailable during portability assessment and first unlocked only for the held-out benchmark.
