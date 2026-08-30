# Criteo R1F — Technical Finalization

Frozen: 2026-08-28

## Status inherited from R1.2

R1.2 strict propensity gate remains FAIL.

This status is NOT changed by R1F.

Forensic interpretation:
- propensity overlap/calibration/weighted-SMD diagnostics were strong;
- the PC1-decile gate exceeded .010 in one decile for ESS=.8 (.010121)
  and one decile for ESS=.5 (.010553);
- therefore Criteo is demoted from primary causal validation to a
  secondary large-scale real-data application/benchmark.

No new propensity learner is allowed.

## Why R1F exists

R1.2 source-selection policies were reconstructed from decimal CSV fields
`score_cut` and `tie_u_cut` and then used exact floating equality.

For tree models with large threshold ties, this destroyed R1.1 tie-breaking.
Forensic comparison showed R1.2 policy rates essentially reverted to the original
invalid R1 policy rates.

This is a serialization/reproducibility defect, not a statistical repair.

## Frozen inputs

R1 source SHA256:
1c7fe26cebf45f9215c7ec8de54f06ec2e72eb8e72744b3fb2a8d392ae0f3e0e

R1.2 source SHA256:
99453d9155046977d73a5687ec1a6ff62103d9e9bee80d1cbf205c2a6fc472ce

Unchanged:
- R0/R0.1 shifts;
- R1 membership/splits;
- 18 fitted uplift-model artifacts;
- R1.1 tie seed 2026082806;
- R1.2 fitted logistic propensity models;
- budgets .10/.30/.50;
- target-outcome blinding;
- source-infer blinding.

## R1F operation

For each frozen model:
1. score source_train and source_select;
2. construct exact top-q lexicographic rule in memory;
3. apply the rule to source_select before any float serialization;
4. evaluate using the already fitted R1.2 propensity model;
5. select final source winner for each scenario×budget.

Human-readable rule artifacts additionally store exact IEEE-754 hexadecimal
representations of cutoffs. They are provenance, not re-read during R1F.

## Technical GO gate

- exact q on every source_train model-budget policy;
- all source_select policy rates within .005 of q;
- all gains finite;
- nine winners defined;
- R1.2 propensity models reused;
- no candidate retraining;
- no source_infer outcome;
- no target treatment/outcome.

PASS authorizes R2 as a secondary real-data application only.
