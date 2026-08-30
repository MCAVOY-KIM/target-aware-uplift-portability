# Decision Log — Reframing and Criteo R0 — 2026-08-28

## Synthetic phase closure

The synthetic method-development branch is closed after P1-C.4.

The exact finite-sample "95% certification" claim is not retained.

The research topic is retained as target-aware portability assessment using transported target regret and asymptotic simultaneous bounds.

No additional bootstrap correction or larger synthetic rescue run will be performed before real-data work.

## Real-data strategy

Criteo is used because it supplies a very large randomized uplift benchmark.

However, it lacks a natural deployment-population identifier. Therefore source-to-target population shift will be emulated using a predeclared X-only selection mechanism.

Target outcomes remain hidden from the method and are used only for later benchmark/audit evaluation.

## Stage discipline

R0 = provenance, schema, X-only shift construction.
R1 = deterministic population construction + source model training/selection.
R2 = target-aware portability inference with target outcomes hidden.
R3 = unlock held-out target outcomes for benchmark comparison.
R4 = robustness and manuscript tables.

Do not skip R0.
