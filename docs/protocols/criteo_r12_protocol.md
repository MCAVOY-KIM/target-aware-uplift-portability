# Criteo R1.2 — Residual Propensity Adjustment Gate

Frozen: 2026-08-28

## Trigger

R1.1 successfully fixed top-q budget fidelity, but its predeclared exact-randomization gates failed even in the null population:
- null max raw SMD = .0474;
- null PC1-decile treatment-rate deviation = .0131;
- null treatment-prediction AUC = .5114.

The ESS=.8/.5 emulated source populations showed AUC .5152/.5164.

The public Criteo v2 benchmark originates from randomized incrementality tests, but the released/rebalanced sample exhibits small residual treatment-X predictability. Therefore the exact constant propensity assumption e(X)=.85 is not retained for real-data evaluation.

## What is frozen

Unchanged:
- R0/R0.1 population shifts;
- source/target membership;
- R1 source/target splits;
- all 18 fitted candidate model artifacts;
- R1.1 exact budget/tie rule;
- model library;
- q=.10/.30/.50;
- target-outcome blinding;
- source-infer blinding.

Candidate models are NOT retrained in R1.2.

## Propensity nuisance

For each source scenario separately:

Fit on source_train only:
- standardized logistic regression;
- treatment A as label;
- f0-f11 only;
- C=1;
- lbfgs;
- max_iter=250.

No visit/conversion/exposure enters propensity fitting.

Apply the frozen propensity model to source_select.

## Source winner re-evaluation

Use the already frozen R1.1 top-q policy rules.

Evaluate each source_select policy using:

mean[ pi(X){A/e_hat(X)Y - (1-A)/(1-e_hat(X))Y} ].

No model/hyperparameter selection is performed.

The resulting budget-specific winners supersede the constant-propensity R1.1 winners only if the entire R1.2 gate passes.

## Predeclared GO gates

Every scenario must satisfy:
- e_hat p0.1% >= .05;
- e_hat p99.9% <= .98;
- inverse-weight p99.9% <= 25;
- |mean predicted treatment - observed treatment| <= .002;
- maximum 20-bin calibration gap <= .01;
- maximum weighted SMD across f0-f11 plus PC1 <= .02;
- maximum weighted treated-share deviation from .5 across PC1 deciles <= .01;
- all source_select policy rates remain within .005 of q;
- target treatment/outcomes unused;
- source_infer outcomes unused.

## Decision

PASS:
- freeze estimated source propensity strategy;
- freeze propensity-adjusted source winners;
- move to R2.

FAIL:
- do not try a sequence of propensity learners until one passes.
- pause Criteo causal-use strategy and decide whether the public benchmark can support the paper's primary real-data validation under the required standard.

This is the sole predeclared propensity repair.
