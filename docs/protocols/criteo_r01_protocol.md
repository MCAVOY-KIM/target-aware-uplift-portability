# Criteo R0.1 Shift Materialization Audit

Frozen: 2026-08-28

R0 scientifically passed, but its artifact stored PC1 loadings without sklearn PCA's pilot-centering vector (`pca.mean_`), which is required to score new/full-data rows exactly.

R0.1 is a technical reproducibility amendment. It MUST NOT:
- change PC1 direction;
- change the frozen beta/intercept;
- use treatment or outcomes;
- recalibrate ESS after seeing full-data results.

It reconstructs the exact deterministic X-only pilot and requires exact agreement (tolerance 1e-10) with R0 loading, score SD, and explained variance.

Then it applies the already frozen shift definitions to the full 13,979,592-row X distribution and audits:
- expected target share;
- expected source-to-target ESS;
- target-selection probability tails;
- density-ratio tails.

GO criteria:
- PCA reconstruction exact;
- expected target share within ±0.02 of .50 for every shift;
- full-X ESS within ±0.03 of the frozen R0 target for every shift.

Overlap-tail quantities are review diagnostics, not post-result tuning criteria.

Only after R0.1 PASS may target/source membership be instantiated in R1.
