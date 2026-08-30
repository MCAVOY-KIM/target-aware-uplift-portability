# Criteo R1.1 — Budget Fidelity + Randomization Audit

Frozen: 2026-08-28

## Why R1.1 is required

R1 correctly constructed populations and fit all 18 model artifacts, but its top-q implementation used:

`score >= empirical quantile`.

Tree-based learners produced exact score ties at some thresholds, causing large budget violations. The largest observed violation was:

- null_ess1.0
- TO-HGB
- q=.50
- realized source_select treatment rate=.9560

Therefore the R1 winner table is NOT accepted as a valid budget-constrained comparison.

This issue was discovered before any target treatment/outcome was used.

## What remains frozen

- R0/R0.1 shift definitions
- R1 population membership seeds
- R1 source/target role seeds
- all 18 fitted R1 model artifacts
- model library and hyperparameters
- q={.10,.30,.50}
- primary visit outcome
- target-outcome blinding

No model is retrained in R1.1.

## Correct top-q rule

For every model and q, rank by:

1. model score descending;
2. among exact score ties only, a predeclared independent deterministic row-hash U ascending.

Tie seed:
2026082806

The calibration source_train policy contains exactly round(q*n) rows.

The same frozen `(score cutoff, tie-U cutoff)` rule is applied to source_select.

This is equivalent to randomized tie-breaking at equal predicted uplift, using exogenous outcome-independent randomness.

## Source randomization audit

Criteo v2 was constructed from randomized incrementality tests and rebalanced to a global treatment ratio of .85. Nevertheless, our emulated source selection depends on X, so R1.1 verifies that treatment assignment remains practically independent of X.

For every source scenario:
- overall treatment rate reported;
- max treated-vs-control feature SMD <= .02;
- max treatment-rate deviation across source-train PC1 deciles <= .005;
- logistic treatment-prediction AUC on independent source_select <= .51.

These are design-integrity checks, not model-selection criteria.

## GO criteria

For all scenarios:
- source_train top-q rates exact;
- source_select treatment rates within .005 of q for all 18 model-budget policies;
- all model artifacts load;
- all corrected source-selection gains finite;
- all randomization checks pass;
- target outcomes used = false;
- source_infer outcomes used = false.

If PASS:
- corrected source winners replace the invalid original R1 winner table;
- the lexicographic tie rule is frozen for R2 target-adaptive policies.
