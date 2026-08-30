# Criteo R3 — Frozen Target-Outcome Benchmark

Frozen after forensic R2 PASS, before examining any target outcome.

Date: 2026-08-29

## R2 freeze

The uploaded R2 artifacts passed forensic checks:
- 45 directed contrasts, 9 regret bounds, 54 target-policy rules;
- no duplicates / NaN / Inf;
- every reported regret bound recomputes exactly from pairwise contrasts;
- maximum target-infer budget deviation = 0.000694 < .005;
- estimated source→target ESS = .999987 / .799098 / .498712;
- estimated-ratio vs oracle-ratio upper regret bounds differ by < 1e-6 at all nine cells;
- every predeclared R2 technical gate passed.

R2 hashes are hard-coded into R3. R3 stops if any frozen R2 artifact changed.

## Purpose

R3 is the FIRST use of target treatment/outcomes.

It does not tune or alter:
- source/target populations;
- candidate uplift models;
- source winners;
- target policy thresholds;
- density-ratio estimator;
- R2 transported estimates;
- R2 regret bounds;
- tolerance grid.

R3 only benchmarks the already-frozen target-outcome-blind R2 results.

## Target benchmark sample split

Already frozen:
- target_adapt = 25% of target population;
- target_infer = 75%.

After R2 freeze, R3 unlocks:

target_adapt:
- X, treatment, visit
- used only to fit target benchmark nuisance functions.

target_infer:
- X, treatment, visit
- used only for held-out target benchmark evaluation.

The target policies themselves remain exactly the R2 X-only policies.

## Frozen target policy reproduction

R3 reads the exact IEEE-754 hexadecimal score and tie cutoffs saved by R2.

For each model and q:
- no threshold is re-estimated;
- the exact R2 policy is reapplied to target_infer;
- the resulting target-infer policy rate must reproduce the R2 rate within 1e-12.

This is a direct check that unlocking target outcomes did not change the decision rule.

## Target benchmark nuisance models

No tuning.

Treatment propensity, trained on target_adapt X,A:
- standardized logistic regression;
- C=1;
- lbfgs;
- max_iter=250.

Outcome nuisances, trained on target_adapt X,A,Y:
- separate treatment/control HistGradientBoostingClassifier;
- same fixed HGB architecture used previously:
  learning_rate=.05,
  max_iter=150,
  max_leaf_nodes=31,
  min_samples_leaf=200,
  l2_regularization=1,
  max_bins=255,
  early stopping enabled.

## Primary target benchmark estimator

For each frozen target policy pi:

AIPW incremental gain on target_infer:

pi(X) [
  mu1_hat(X)-mu0_hat(X)
  + A/e_hat(X){Y-mu1_hat(X)}
  - (1-A)/(1-e_hat(X)){Y-mu0_hat(X)}
].

For each of the 15 frozen competitor-minus-source contrasts, use the direct
paired contrast.

A target-only propensity-adjusted IPW contrast is reported as sensitivity.

## Benchmark inference

- direct 15-dimensional contrast covariance on target_infer;
- 20,000-draw one-sided Gaussian max-t;
- simultaneous target-benchmark contrast intervals.

This benchmark is still estimated, not mathematical truth.

Do NOT call R3 point regret “the true regret.”

Preferred wording:
“held-out target-outcome benchmark estimate.”

## Prespecified R2-vs-R3 comparisons

Descriptive only; none is a tuning gate:

1. 45-contrast R2-vs-target AIPW:
   - MAE
   - RMSE
   - correlation
   - sign agreement

2. For nine scenario×budget cells:
   - target-best model;
   - held-out target benchmark regret of the frozen source winner;
   - R2 transported point-regret estimate;
   - R2 asymptotic upper regret bound;
   - whether benchmark point regret is below the frozen R2 bound.

3. Tolerance grid:
   .0005 / .001 / .002 / .005
   - compare the frozen R2 decision with benchmark point regret.
   - any apparent contradiction is reported, never repaired.

## R3 technical GO gate

Every scenario must satisfy:
- exact reproduction of R2 target-infer policy rates within 1e-12;
- every policy remains within .005 of its nominal q;
- target benchmark propensity p0.1% >= .05 and p99.9% <= .98;
- mean propensity calibration error <= .002;
- max 20-bin propensity calibration gap <= .01;
- max weighted SMD across f0-f11 + PC1 <= .02;
- at least 1,000 visit events in each target-adapt treatment arm;
- all 15 benchmark contrasts finite/nondegenerate;
- benchmark correlation matrix numerically PSD.

Agreement between R2 and R3 is deliberately NOT a technical gate.

## Decision after R3

If technical gate fails:
- do not shop for alternative benchmark nuisances;
- R3 benchmark credibility must be reconsidered.

If technical gate passes:
- freeze R3;
- scientifically evaluate R2-vs-R3 agreement exactly as observed;
- no R2 repair is allowed;
- decide whether the evidence is strong enough for the SCIE manuscript;
- then proceed to a limited R4 robustness/manuscript evidence freeze.
