# Data Access

## CRITEO-UPLIFT v2.1

The raw dataset is not distributed in this repository.

Official dataset page:

`https://ailab.criteo.com/criteo-uplift-prediction-dataset/`

Expected local file:

```text
data/raw/criteo-research-uplift-v2.1.csv.gz
```

Frozen properties used by this study:

- rows: 13,979,592
- pretreatment covariates: `f0` through `f11`
- treatment column: `treatment`
- primary outcome: `visit`
- secondary outcome: `conversion`
- `exposure` is not used as a predictor because it may be post-treatment

Expected SHA-256:

```text
2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc
```

After downloading, run:

```bash
python scripts/verify_raw_data.py
```

The reproduction scripts stop if the expected raw file is missing. Do not commit the raw dataset to Git.
