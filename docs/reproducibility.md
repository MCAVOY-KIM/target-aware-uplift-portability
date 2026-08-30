# Reproducibility protocol

## Principle

The public repository should reproduce the submitted manuscript without changing the scientific decisions that were frozen before held-out target outcomes were accessed.

## Evidence streams

### 1. Exact-truth simulation

The simulation package should expose:

- data-generating processes;
- candidate-policy definitions;
- source/target split roles;
- truth computation;
- primary simultaneous-inference procedure;
- double-robustness stress tests;
- rare-binary finite-sample stress tests;
- scripts that regenerate manuscript simulation tables/figures.

### 2. Criteo application

The Criteo package should preserve the following chronology:

1. outcome-blind shift construction from pretreatment `X` only;
2. population membership and source/target role construction;
3. fixed six-model source library and source-side selection;
4. prespecified source propensity diagnostic (including the retained strict-gate failure);
5. target-outcome-blind portability assessment;
6. freeze of outcome-blind outputs;
7. first target treatment/outcome unlock;
8. held-out target-only benchmark;
9. descriptive evidence synthesis without post-hoc model/tolerance redesign.

## No post-hoc repair rule

A reproducibility rerun may fix a genuine implementation/reproducibility defect, but it must not silently:

- retune the candidate library after target outcomes are seen;
- change treatment budgets or tolerance values to improve results;
- relabel failed prespecified scientific diagnostics as passed;
- omit finite-sample undercoverage or pairwise discrepancies;
- reconstruct target populations using outcome information.

## Freeze checks

The final public package should include hashes for frozen outputs and a chronological manifest of when target outcomes first became available.
