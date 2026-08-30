# Criteo R0 Protocol — Data and X-Only Shift Construction

Frozen: 2026-08-28

## Purpose

Before real-data model fitting, freeze:
1. raw-data provenance and schema;
2. outcome/treatment prevalence;
3. feature quality;
4. an outcome-blind target-population shift construction.

No uplift model is trained in R0.

## Raw data

Expected file:
`02_data/raw/criteo-research-uplift-v2.1.csv.gz`

Expected SHA256:
`2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc`

Expected rows:
13,979,592

Expected features:
f0-f11

Treatment/outcomes:
treatment, visit, conversion

`visit` is primary.
`conversion` is secondary.
`exposure` is explicitly excluded from predictors because it can be post-treatment.

## Outcome-blind shift direction

Use only f0-f11.

1. Stream the full file to estimate global feature means/SDs.
2. Construct a deterministic X-only pilot sample using row-index hashing.
3. Standardize using full-data X moments.
4. Fit PCA on the pilot X only.
5. Use PC1 as the primary population-shift direction.
6. Fix PCA sign deterministically.

Treatment, visit, conversion, and exposure do NOT enter PCA or shift calibration.

## Target/source assignment mechanism for R1

For standardized PC1 score z,

P(Target=1 | X) = expit(a + beta z).

The intercept is calibrated to 50% expected target share.

Beta is calibrated on the X-only pilot so that the implied source-to-target density-ratio ESS is approximately:
- 1.00 null/no-shift
- 0.80 moderate shift
- 0.50 stronger shift

R0 only freezes these parameters. Membership is instantiated in R1 with a separate reserved deterministic random seed.

## Why this design

Criteo does not contain a natural source-vs-target population identifier suitable for a clean external-validity analysis.

Therefore the real-data study is an **emulated target population shift on genuine randomized trial data**, not natural external validation.

This must be stated explicitly in the manuscript.

The advantage is that:
- source/target selection uses only pretreatment X;
- randomization is preserved within populations;
- target treatment/outcomes can be hidden from the method and retained for held-out benchmark evaluation;
- the true selection mechanism is known by design for sensitivity analysis.

## R0 GO criteria

- exact raw-file SHA match;
- exact expected row count;
- expected schema present;
- treatment/outcome columns binary;
- primary visit rate consistent with the rare-outcome benchmark scale;
- no degenerate feature standard deviation after handling missingness;
- PC1 successfully estimated;
- ESS=.8 and .5 logistic selection parameters successfully calibrated;
- no treatment/outcome information used in shift construction.

Only after R0 forensic review is R1 model fitting authorized.
