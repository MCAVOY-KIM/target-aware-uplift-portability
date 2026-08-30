# P1-B.1 Protocol Amendment — Source-Specific Portability Certification

Frozen after forensic audit of the original 250-rep Core calibration and before any P1-B.1 run.

## Why an amendment is needed
The original Core calibration passed simultaneous validity and safety but the global Target Model Confidence Set had a 67.73% singleton rate in the predeclared `n=20k, ESS=.5, clear` positive-control cell, below the 70% criterion.

The original Core results are therefore retained as method-development/calibration evidence only and are not reused as confirmatory evidence for P1-B.1.

## What is NOT changed
- alpha = .05
- epsilon = .005
- source/target sample sizes
- ESS levels
- near/clear regimes
- DGP
- target-adaptive thresholds
- transported DR estimator
- global 45-pair two-sided simultaneous confidence system
- 70% informativeness threshold
- false-certification threshold <=5%

## Key statistical clarification
A naive switch from two-sided global intervals to one-sided intervals for the entire model-confidence-set family does not materially solve the issue. Because all pairwise directions are implicitly needed to eliminate arbitrary candidate models, the ordered one-sided maximum is effectively the same as the original maximum absolute statistic.

## P1-B.1 primary decision object
The primary deployment question is narrower:

`Can the model selected on an independent source-selection split be certified as epsilon-near-optimal in the target population across treatment budgets?`

For each budget q, the source-selected model m_S(q) is fixed before target inference.

Therefore the required family contains only:
- five competitor-minus-source-model contrasts per budget;
- three budgets;
- at most 15 directed contrasts total.

A one-sided Gaussian max-t critical value is computed for this 15-contrast family.

The resulting upper bounds provide simultaneous 95% control for:
`G_T(j,q) - G_T(m_S(q),q)` for every competitor j and budget q.

The source-specific portability regret bound is:
`B_T^S(q) = max(0, max_j U[j,m_S(q),q])`.

Certificate:
`B_T^S(q) <= epsilon`.

## Secondary output
The original global 45-pair two-sided confidence system and Target Model Confidence Set remain reported as secondary inferential outputs. They are not altered to force a singleton.

## Fresh validation
P1-B.1 uses a new seed base. The previous 3,000 Core replications are not counted toward P1-B.1 validation.

### Core Gate (250 reps × 12 cells)
- global pairwise simultaneous coverage: 90%–99% (secondary validity)
- source-specific directed simultaneous upper coverage: 90%–99%
- source-specific portability-bound all-budget coverage: >=90%
- conditional false source-specific certification: <=5%
- clear, n=20k, ESS=.8 and .5: source-specific certificate rate >=70%

### Full Gate
- global pairwise simultaneous coverage: 93%–97%
- source-specific directed simultaneous upper coverage: 93%–97%
- source-specific portability-bound all-budget coverage: >=93%
- conditional false source-specific certification: <=5%
- same clear positive-control certificate-rate criterion >=70%

No gate threshold is relaxed relative to the original method-development stage; the informativeness criterion is moved to the deployment object that is now explicitly primary.
