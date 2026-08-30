# Criteo R1 — Population Construction and Source Model Library Freeze

Frozen: 2026-08-28

## Purpose

Instantiate the already frozen R0/R0.1 population-shift mechanisms and fit the fixed source uplift-model library.

Target treatment/outcomes remain hidden.

## Population construction

For every frozen shift scenario:
- target membership is Bernoulli with the frozen X-only probability P(Target=1|X);
- deterministic row-hash uniform seed: 2026082803;
- the same membership uniform is reused across shift strengths for comparability.

Independent deterministic role seed: 2026082805.

Source roles:
- train 30%
- select 20%
- infer 50%

Target roles:
- adapt 25%
- infer 75%

R1 uses:
- source_train: X,A,visit
- source_select: X,A,visit
- target rows: X only for membership/role counts

R1 MUST NOT use:
- source_infer outcomes
- target treatment
- target visit/conversion/exposure

## Primary outcome

visit

conversion remains secondary and is not used in R1.

## Fixed candidate library

Six algorithms, no hyperparameter tuning:

1. S-Logit
   - logistic regression
   - standardized [X, A, A×X]
   - C=1, lbfgs, max_iter=250

2. T-Logit
   - separate standardized logistic regressions by treatment arm

3. S-HGB
   - HistGradientBoostingClassifier on [X,A]

4. T-HGB
   - separate arm-specific HistGradientBoostingClassifiers

5. TO-HGB
   - HistGradientBoostingRegressor on the randomized transformed outcome

6. DR-HGB
   - HistGradientBoostingRegressor on a DR pseudo-outcome using the T-HGB outcome models fitted on source_train

HGB parameters:
- learning_rate=.05
- max_iter=150
- max_leaf_nodes=31
- min_samples_leaf=200
- l2_regularization=1
- max_bins=255
- early stopping enabled

The candidate learner itself need not be cross-fit because final candidate selection is evaluated on the independent source_select split.

## Source model selection

Budgets:
q = .10, .30, .50

For each candidate:
1. fit on source_train;
2. define source top-q threshold from source_train scores;
3. evaluate the resulting source policy on independent source_select using direct randomized IPW incremental gain:

mean[ pi(X) { A/e Y - (1-A)/(1-e) Y } ]

with known e=.85.

Winner is the candidate with largest source_select IPW gain for each q.

No target data enter winner selection.

## R1 GO criteria

For every scenario:
- realized source→target ESS within .03 of frozen target;
- all five analysis splits exceed 100k rows;
- source_train treatment rate within .005 of .85;
- all six models fit with finite non-degenerate scores;
- all source-selection gains finite;
- target-outcome usage count = 0.

Model diversity and which model wins are reported, not tuned.

If R1 passes, the model library and source winners are frozen before R2 target-X portability inference.
