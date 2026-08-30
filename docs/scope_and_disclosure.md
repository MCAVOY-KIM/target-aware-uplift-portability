# Scope and disclosure notes

## Scope of claims

This repository supports a manuscript about **pre-deployment portability assessment of an already source-selected uplift model** under population shift.

The repository should not be described as evidence for:

- a new generic doubly robust transport estimator;
- a new target-optimal policy-learning algorithm;
- exact finite-sample 95% certification;
- natural external validation using Criteo;
- universal superiority of any uplift learner;
- exact model-rank preservation.

## Known limitations preserved in the public record

- Gaussian simultaneous bounds are asymptotic and exhibited finite-sample undercoverage in selected difficult simulation regimes.
- The strict source-propensity PC1-decile diagnostic remained failed in the shifted Criteo populations and must not be reclassified after downstream results.
- Criteo uses outcome-blind **emulated** covariate shift, not a natural source-target population pair.
- Portability is relative to the fixed six-model library and prespecified budgets.
- Pairwise transported-vs-held-out agreement is imperfect; the manuscript's primary target is source-selected-model regret, not exact pairwise rank reproduction.

## AI disclosure

The submitted manuscript includes an IEEE-compliant acknowledgment disclosure for the use of OpenAI ChatGPT in drafting/editing, methodological exposition, and code/document preparation. All analyses, references, numerical results, and conclusions remain subject to author verification.
