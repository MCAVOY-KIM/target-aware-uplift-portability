# Criteo R2 — Target-Outcome-Blind Portability Assessment

Frozen: 2026-08-28

## R1F forensic amendment

R1F console reported `all_source_train_budgets_exact=False`.

This was a gate-definition bug, not a policy failure.

R1F defines exact discrete top-q as:
`k = round(q*n)` selected observations.

For all 54 source-train policies, the saved policy rate equals `k/n`
to within 7e-17. Since k/n need not equal the real number q exactly in
a finite sample, checking `|k/n-q| <= 1e-12` was logically incorrect.

Maximum nominal deviation was only 2.39e-7.

All 54 source-select policy rates were within .005 of q; maximum
deviation was 0.001104.

Therefore:
- R1F Technical Finalization = PASS after forensic correction.
- The nine R1F source winners are frozen.
- R1.2 strict propensity gate remains FAIL permanently.

## Role of Criteo

Criteo is a secondary large-scale real-data application/benchmark,
not primary nominal-validity/causal-validation evidence.

## R2 objective

Estimate whether each frozen source-selected model remains competitive in
its emulated target population without using target treatment or outcomes.

Allowed data:
- source_train X: population-ratio nuisance fit
- target_adapt X: population-ratio nuisance fit and target top-q thresholds
- source_infer X,A,visit: transported residual inference
- target_infer X only: target standardization

Forbidden:
- target treatment
- target visit
- target conversion
- target exposure

## Fixed target-adaptive policies

For every model and q=.10/.30/.50:
- score target_adapt;
- select exactly round(q*n) via score-descending + frozen tie hash;
- tie seed 2026082806;
- apply the exact in-memory rule to source_infer and target_infer;
- save IEEE-754 hexadecimal cutoffs for R3 reproduction.

## Population-ratio nuisance

Primary ratio is estimated using X only.

For every scenario:
- deterministic equal-size sample of up to 1,000,000 source_train X
  and 1,000,000 target_adapt X;
- standardized logistic domain classifier;
- C=1, lbfgs, max_iter=250;
- balanced source/target training prior;
- density ratio = P_hat(Target|X)/P_hat(Source|X).

Because the emulated membership mechanism is known, the oracle design ratio
is computed in parallel as an outcome-blind sensitivity diagnostic.

The estimated-ratio analysis is primary.

## Treatment propensity nuisance

Reuse the frozen R1.2 scenario-specific logistic propensity models.

No new propensity learner is fit in R2.

## Outcome nuisance

Reuse the R1 source-trained T-HGB arm-specific outcome models.

These are independent of source_infer and target_infer.

## Estimator

For directed contrast h(X)=pi_j^T(X)-pi_mS^T(X):

Delta_hat =
 mean_target_infer[ h(X){mu1_hat(X)-mu0_hat(X)} ]
 +
 mean_source_infer[
   r_hat(X) h(X) {
     A/e_hat(X)(Y-mu1_hat(X))
     -(1-A)/(1-e_hat(X))(Y-mu0_hat(X))
   }
 ].

There are 5 competitor-minus-source contrasts × 3 budgets = 15.

## Inference

Primary:
- two-sample influence-function covariance;
- all 15 directed contrasts jointly;
- 20,000-draw one-sided Gaussian max-t critical value;
- asymptotic 95% upper family.

For each q:
B_U(q) = max(0, max_j U_jmq).

Directional lower bounds are also reported but do not turn Criteo into a
finite-sample certification study.

## Practical tolerance

The primary application object is the bound itself:
`minimum tolerance required for portability = B_U(q)`.

To avoid selecting one epsilon after seeing target results, report the full
predeclared absolute tolerance grid:

- .0005
- .0010
- .0020
- .0050

No epsilon is selected or tuned after R2.

## Technical GO gate

Every scenario:
- exact discrete target-adapt top-q;
- all target-infer policy rates within .005 of q;
- estimated density-ratio ESS within .05 of the emulated design ESS;
- estimated ratio p99.9 <= 6;
- inherited source propensity p0.1%>=.05 and p99.9%<=.98 on source_infer;
- all 15 contrasts finite/nondegenerate;
- covariance correlation numerical minimum eigenvalue >= -1e-8;
- target treatment/outcomes unused.

## Next stage

If R2 technically passes, freeze every R2 output BEFORE R3.

R3 then unlocks target treatment/outcomes only to benchmark:
- actual target randomized/propensity-adjusted policy gains;
- actual target best model at each q;
- realized regret of the frozen source winner;
- whether the target-outcome-blind R2 bounds contained that benchmark regret.

R3 is evaluation, not model/method tuning.
