# Manuscript-to-Repository Mapping

| Manuscript component | Repository evidence |
|---|---|
| Problem formulation / methodology | `src/`, manuscript equations |
| Simulation study | `src/simulation/`, `outputs/simulation/` |
| Rare-binary finite-sample limitations | P1-C source and full-gate outputs |
| Criteo population shift | `src/criteo/criteo_r0_audit.py`, `criteo_r01_shift_materialization.py` |
| Fixed model library / source selection | R1/R11/R12/R1F sources and outputs |
| Outcome-blind portability assessment | R2 source and `outputs/criteo/r2/` |
| Held-out target benchmark | R3 source and `outputs/criteo/r3/` |
| Evidence synthesis | R4 source and `outputs/criteo/r4/` |
| Outcome-unlock provenance | `provenance/freeze_logs/`, `docs/criteo_execution_chain.md` |
| Environment | `environment/` |
| Manuscript-facing assets | compact outputs plus `scripts/reproduce_manuscript_assets.py` |
