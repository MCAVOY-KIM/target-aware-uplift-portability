# Criteo R4 — Frozen Evidence Synthesis

Frozen: 2026-08-29

R4 is not a new experiment.

It performs no:
- candidate-model fitting;
- nuisance fitting;
- policy re-estimation;
- tolerance selection;
- confidence-bound recalibration;
- Criteo outcome reanalysis from raw data.

It only reads cryptographically frozen R2 and R3 CSV outputs and produces
manuscript-ready evidence tables, figures, and descriptive summaries.

## Primary interpretation targets

1. Rank agreement is not the portability estimand.
   Report source winner vs point-estimated target-best identity.

2. Practical decision loss.
   Report held-out target benchmark regret and R2 upper regret bound.

3. Abstention behavior.
   On the predeclared epsilon grid, count:
   - portable;
   - uncertain;
   - evidence of non-portability;
   - benchmark regret <= tolerance;
   - false-portable contradictions;
   - conservative abstentions.

4. Pairwise fidelity.
   Report 45-contrast:
   - MAE;
   - RMSE;
   - correlation;
   - sign agreement;
   - number whose target benchmark point lies below the frozen R2 upper contrast bound.

5. Benchmark sensitivity.
   Report AIPW vs IPW agreement and whether all target-IPW regret sensitivities
   remain below the frozen R2 bounds.

## Language constraints

Never call the target benchmark 'truth'.
Use:
- held-out target-outcome benchmark;
- target AIPW benchmark point estimate.

Never claim exact 95% finite-sample certification.

Never claim rank preservation.

Criteo remains secondary application evidence because the R1.2 strict
propensity-balance gate failed narrowly in the two shifted scenarios.

## Stop rule

After R4, no additional Criteo model/nuisance/tolerance tuning is allowed
unless a concrete reproducibility defect is discovered.

The next research decision is manuscript-level evidence assessment:
whether the combined exact-truth simulations + Criteo application are strong
enough for the SCIE submission strategy.
