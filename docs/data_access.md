# Data access and integrity

## CRITEO-UPLIFT v2.1

This project uses the public randomized CRITEO-UPLIFT benchmark. The raw data are not redistributed in this repository.

Official dataset information page:

- https://ailab.criteo.com/criteo-uplift-prediction-dataset/

Expected local filename:

```text
criteo-research-uplift-v2.1.csv.gz
```

Expected row count:

```text
13,979,592
```

Expected variables used by the project include pretreatment features `f0`-`f11`, treatment, visit, and conversion. The post-treatment `exposure` variable is not used as a predictor.

Expected SHA-256:

```text
2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc
```

Verify locally:

### PowerShell

```powershell
(Get-FileHash .\data\raw\criteo-research-uplift-v2.1.csv.gz -Algorithm SHA256).Hash.ToLower()
```

### Python

Use:

```bash
python scripts/verify_checksums.py
```

## Non-redistribution rule

Do not commit:

- raw Criteo data;
- derived files that contain row-level source data when redistribution rights are unclear;
- local caches or serialized raw-data subsets.

Public reproducibility should rely on code, configuration, checksums, aggregate/frozen outputs, and documented download instructions.
