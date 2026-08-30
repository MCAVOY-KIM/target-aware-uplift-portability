# P1-C Decision Log — 2026-08-27

## Starting state

P1-B.1 is frozen after the Full Gate.

Its strict nominal-window gate had mild overcoverage in strong-shift near-tie cells, but:
- no core undercoverage;
- strong portability-bound safety;
- strong high-information informativeness;
- expected one-nuisance double-robust behavior.

No P1-B.2 tuning will be performed.

## P1-C purpose

P1-C is a stress test of the frozen method under:
- binary outcome;
- approximately 4.68% source event prevalence;
- treatment probability 0.85;
- only 15% controls;
- target population shift;
- nuisance misspecification.

## Important correction carried forward

The theoretical safety object is familywise simultaneous coverage / probability of any false certificate across budgets.

`P(false | certificate)` is retained only as a descriptive quantity and is not used as a formal 5% error guarantee.

## Exact-truth choice

A probit binary DGP is selected because top-q linear policies under Gaussian X admit bivariate-normal integration for exact target value.

This avoids judging nominal coverage against a noisy simulation oracle.

## Gate philosophy

Because P1-C is intentionally a rare-event robustness stress test, severe undercoverage is a primary failure, while overcoverage is interpreted as conservatism and reported separately.

P1-B.1 remains the main method-validity experiment.
