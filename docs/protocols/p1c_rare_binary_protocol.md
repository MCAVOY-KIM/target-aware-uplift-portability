# P1-C Rare-Binary Robustness Gate — Frozen Protocol

Frozen: 2026-08-27

## 1. Purpose

P1-B.1 established method feasibility under an exact-truth continuous Gaussian DGP.

P1-C does **not** modify the P1-B.1 statistical method. It stress-tests that frozen method under a Criteo-like rare binary outcome and treatment imbalance before any real-data application.

Primary question:

> Does source-specific target portability certification remain safe and usable when outcomes are rare and the randomized treatment allocation is strongly imbalanced?

## 2. Criteo-like source environment

Source treatment probability:
- P(A=1) = 0.85
- P(A=0) = 0.15

Source marginal binary outcome rates are calibrated to:
- Control: 4.0%
- Treated: 4.8%
- Mixture: 4.68%

This closely matches the approximately 4.7% `visit` prevalence previously observed in the Criteo uplift data.

## 3. Outcome DGP

Binary outcomes use a probit model:

P(Y(a)=1 | X) = Phi(alpha_a + beta_a'X).

The treated arm contains heterogeneous treatment response along X1, X2, and X3.

The source intercepts are analytically calibrated so that the source marginal event rates remain fixed at 4.0% and 4.8%.

## 4. Exact target truth

The treatment policies are top-q threshold rules based on linear pretrained model scores.

For Gaussian target X and a probit outcome model,

E[ Phi(alpha + beta'X) 1{w'X >= c} ]

can be written as a bivariate Gaussian tail probability.

Therefore target policy gains are evaluated by numerical bivariate-normal integration, **not by a noisy Monte Carlo oracle**.

The truth is conditional on the empirical target-adaptation threshold, preserving the P1-B principle that coverage should be judged against an essentially exact target quantity.

## 5. Frozen P1-B.1 method

Unchanged:
- independent source model training/selection/inference roles;
- independent target-adapt and target-inference samples;
- target-adaptive top-q threshold policies;
- transported doubly robust estimator;
- source-selected-model directed contrast family;
- one-sided simultaneous Gaussian max-t upper bounds;
- portability regret bound;
- epsilon = 0.005 for simulation certification diagnostics;
- global all-pair confidence system remains secondary.

No P1-B.1 parameter will be retuned using P1-C results.

## 6. Nuisance estimation

Outcome nuisance:
- correctly specified arm-specific probit regression in primary cells;
- misspecified outcome stress omits the true effect-modifier covariates.

Density-ratio nuisance:
- correct Gaussian mean-shift density-ratio family in primary cells;
- misspecified stress shrinks the estimated shift vector by 50%.

Treatment propensity is known at 0.85, consistent with randomized source assignment.

## 7. Sample splitting

Source:
- 30% nuisance training
- 20% source model selection
- 50% inference

Target:
- 25% target threshold adaptation
- 75% inference

## 8. Core design

12 cells:

- sample size: 20,000 and 80,000 per population;
- target ESS: 0.80, 0.50, 0.30;
- candidate separation: near and clear;
- shift: effect-relevant;
- nuisances: both correctly specified.

The 20k cells deliberately yield few source-training control events and are a finite-sample stress condition.
The 80k cells test whether the method recovers with more rare-event information.

## 9. Stress design

At n_source=n_target=80,000 and ESS=0.50:

1. effect-irrelevant population shift;
2. outcome nuisance misspecified, ratio correct;
3. ratio misspecified, outcome correct;
4. both nuisances misspecified.

## 10. Staging

### Smoke
- 3 scenarios × 20 repetitions.
- Technical validation only.

### Core Gate
- 12 cells × 200 repetitions = 2,400 replications.
- Do not interpret as final publication evidence.

### Full Gate
- 12 core cells × 500 = 6,000.
- 4 stress cells × 300 = 1,200.
- Total = 7,200 replications.

Full is run only after Core review.

## 11. Primary safety metrics

### A. Directed simultaneous upper coverage

This is the source-winner-vs-competitors family used for portability certification.

P1-C treats **anti-conservatism** as the primary failure mode.

Core calibration floor:
- >= 88% in every core cell.

Full floors:
- n=20k: >= 90%;
- n=80k: >= 92%.

Overcoverage is reported as conservatism rather than automatically treated as a safety failure.

### B. Portability-bound all-budget coverage

Core:
- >= 90%.

Full:
- n=20k: >= 90%;
- n=80k: >= 93%.

### C. Familywise false certification

For each Monte Carlo replication define an error if **any budget** receives a portability certificate while true regret exceeds epsilon.

Required:
- <= 5%.

This replaces the earlier conditional `false | certified` diagnostic, which is not the theoretical familywise guarantee.

### D. Outcome nuisance fit stability

Successful probit fits:
- >= 98%.

## 12. Minimal stress informativeness checks

P1-B.1 already established the main informativeness result.
P1-C only requires that rare outcomes do not make the method effectively unusable at high sample size.

For n=80k, clear separation:
- ESS=0.80: source-specific certificate rate >= 50%;
- ESS=0.50: source-specific certificate rate >= 30%.

No hard informativeness threshold is imposed at ESS=0.30.

These are stress-usability thresholds, not manuscript claims about an optimal certificate rate.

## 13. Double-robustness stress

For each one-nuisance-misspecified stress cell:
- source-specific directed upper coverage >= 92%.

The both-misspecified cell has no pass requirement and is expected to deteriorate.

## 14. Decision rule

GO to Criteo application if:
- no severe anti-conservative coverage failure;
- familywise false certification remains controlled;
- outcome fitting is stable;
- both one-nuisance-misspecified scenarios retain acceptable coverage;
- the minimal n=80k usability checks pass.

If the rare binary environment produces severe undercoverage or unstable nuisance fitting, stop before Criteo and diagnose the inferential implementation.

Do not alter P1-B.1 critical values or multiplicity family to rescue P1-C.
