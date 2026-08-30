from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.decomposition import PCA

EXPECTED_SHA256 = "2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc"
EXPECTED_ROWS = 13_979_592
FEATURES = [f"f{i}" for i in range(12)]
EXPECTED_NONFEATURES = ["treatment", "conversion", "visit", "exposure"]
EXPECTED_COLUMNS = FEATURES + EXPECTED_NONFEATURES

PILOT_HASH_SEED = np.uint64(2026082801)
PILOT_SAMPLE_RATE = 0.020
PILOT_FINAL_N = 250_000
TARGET_SHARE = 0.50
ESS_TARGETS = (0.80, 0.50)


def sha256_file(path: Path, block_size: int = 4 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(block_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def splitmix64_uniform(indices: np.ndarray, seed: np.uint64) -> np.ndarray:
    """Deterministic row-index hashing to U(0,1), vectorized in uint64."""
    with np.errstate(over="ignore"):
        z = indices.astype(np.uint64) + seed + np.uint64(0x9E3779B97F4A7C15)
        z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        z = z ^ (z >> np.uint64(31))
    return (z >> np.uint64(11)).astype(np.float64) * (1.0 / float(1 << 53))


def solve_intercept(z: np.ndarray, beta: float, target_share: float = TARGET_SHARE) -> float:
    lo, hi = -30.0, 30.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        m = float(expit(mid + beta * z).mean())
        if m < target_share:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def source_to_target_ess_ratio(z: np.ndarray, beta: float, intercept: float) -> float:
    """
    Population split: P(T=1|X)=p(X).
    r(X)=f_T/f_S = [p/(1-p)] * [(1-pi_T)/pi_T].
    Estimate ESS/n in the SOURCE distribution using pilot empirical X.
    """
    p = np.clip(expit(intercept + beta * z), 1e-8, 1 - 1e-8)
    pi_t = float(p.mean())
    r = (p / (1.0 - p)) * ((1.0 - pi_t) / pi_t)
    sw = 1.0 - p
    denom = float(sw.sum())
    e1 = float(np.sum(sw * r) / denom)
    e2 = float(np.sum(sw * r * r) / denom)
    return float((e1 * e1) / e2)


def calibrate_beta(z: np.ndarray, target_ess: float) -> Dict[str, float]:
    lo, hi = 0.0, 8.0

    def eval_beta(b: float):
        a = solve_intercept(z, b)
        ess = source_to_target_ess_ratio(z, b, a)
        return a, ess

    a_hi, ess_hi = eval_beta(hi)
    while ess_hi > target_ess and hi < 64:
        hi *= 2
        a_hi, ess_hi = eval_beta(hi)

    if ess_hi > target_ess:
        raise RuntimeError(f"Could not reach ESS target {target_ess}; ESS at beta={hi} is {ess_hi}")

    for _ in range(80):
        mid = 0.5 * (lo + hi)
        a_mid, ess_mid = eval_beta(mid)
        # ESS decreases as beta grows.
        if ess_mid > target_ess:
            lo = mid
        else:
            hi = mid

    beta = 0.5 * (lo + hi)
    intercept, ess = eval_beta(beta)
    p = expit(intercept + beta * z)
    return {
        "target_ess": float(target_ess),
        "beta": float(beta),
        "intercept": float(intercept),
        "pilot_ess_ratio": float(ess),
        "pilot_target_share": float(p.mean()),
        "pilot_p_target_p01": float(np.quantile(p, 0.01)),
        "pilot_p_target_p50": float(np.quantile(p, 0.50)),
        "pilot_p_target_p99": float(np.quantile(p, 0.99)),
    }


def update_binary_counts(store: Dict[str, Dict[str, float]], name: str, arr: np.ndarray):
    good = np.isfinite(arr)
    x = arr[good]
    d = store.setdefault(name, {"n": 0, "sum": 0.0, "other": 0})
    d["n"] += int(len(x))
    d["sum"] += float(x.sum())
    d["other"] += int(np.sum((x != 0) & (x != 1)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--chunksize", type=int, default=500_000)
    args = ap.parse_args()

    data_path = Path(args.data).resolve()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    if not data_path.exists():
        raise FileNotFoundError(data_path)

    print("R0-1 SHA256 verification...")
    sha = sha256_file(data_path)
    sha_match = (sha == EXPECTED_SHA256)
    print("SHA256:", sha)
    print("Expected:", EXPECTED_SHA256)
    print("Hash match:", sha_match)
    if not sha_match:
        raise RuntimeError("Criteo raw-file SHA256 mismatch. Stop before analysis.")

    header = pd.read_csv(data_path, compression="gzip", nrows=0)
    columns = list(header.columns)
    print("Columns:", columns)
    missing_expected = [c for c in EXPECTED_COLUMNS if c not in columns]
    if missing_expected:
        raise RuntimeError(f"Missing expected columns: {missing_expected}")

    n_features = len(FEATURES)
    count = np.zeros(n_features, dtype=np.int64)
    missing = np.zeros(n_features, dtype=np.int64)
    sumx = np.zeros(n_features, dtype=np.float64)
    sumsq = np.zeros(n_features, dtype=np.float64)
    minx = np.full(n_features, np.inf)
    maxx = np.full(n_features, -np.inf)

    binary = {}
    pilot_parts: List[np.ndarray] = []
    pilot_indices: List[np.ndarray] = []
    total_rows = 0

    print("R0-2 Streaming dataset audit...")
    usecols = FEATURES + EXPECTED_NONFEATURES
    for chunk_id, df in enumerate(pd.read_csv(data_path, compression="gzip", usecols=usecols, chunksize=args.chunksize)):
        n = len(df)
        global_idx = np.arange(total_rows, total_rows + n, dtype=np.uint64)

        X = df[FEATURES].to_numpy(dtype=np.float64, copy=False)
        finite = np.isfinite(X)
        count += finite.sum(axis=0)
        missing += (~finite).sum(axis=0)

        X0 = np.where(finite, X, 0.0)
        sumx += X0.sum(axis=0)
        sumsq += (X0 * X0).sum(axis=0)
        for j in range(n_features):
            fj = finite[:, j]
            if np.any(fj):
                minx[j] = min(minx[j], float(X[fj, j].min()))
                maxx[j] = max(maxx[j], float(X[fj, j].max()))

        for c in EXPECTED_NONFEATURES:
            update_binary_counts(binary, c, df[c].to_numpy(dtype=np.float64, copy=False))

        u = splitmix64_uniform(global_idx, PILOT_HASH_SEED)
        sm = u < PILOT_SAMPLE_RATE
        if np.any(sm):
            pilot_parts.append(X[sm].copy())
            pilot_indices.append(global_idx[sm].astype(np.int64))

        total_rows += n
        print(f"  chunk={chunk_id+1} rows={total_rows:,}")

    if total_rows != EXPECTED_ROWS:
        raise RuntimeError(f"Unexpected row count {total_rows:,}; expected {EXPECTED_ROWS:,}")

    mean = sumx / np.maximum(count, 1)
    var = sumsq / np.maximum(count, 1) - mean * mean
    var = np.maximum(var, 0.0)
    std = np.sqrt(var)

    feature_rows = []
    for j, c in enumerate(FEATURES):
        feature_rows.append({
            "feature": c,
            "count": int(count[j]),
            "missing": int(missing[j]),
            "missing_rate": float(missing[j] / total_rows),
            "mean": float(mean[j]),
            "std": float(std[j]),
            "min": float(minx[j]),
            "max": float(maxx[j]),
        })
    feature_df = pd.DataFrame(feature_rows)
    feature_df.to_csv(outdir / "criteo_feature_audit.csv", index=False)

    binary_rows = []
    for c in EXPECTED_NONFEATURES:
        d = binary[c]
        binary_rows.append({
            "column": c,
            "n_finite": int(d["n"]),
            "mean_or_rate": float(d["sum"] / max(d["n"], 1)),
            "non_binary_count": int(d["other"]),
        })
    binary_df = pd.DataFrame(binary_rows)
    binary_df.to_csv(outdir / "criteo_binary_audit.csv", index=False)

    pilot_X = np.vstack(pilot_parts)
    pilot_idx = np.concatenate(pilot_indices)
    # Deterministic final downsample using a second hash so the final pilot size is fixed.
    if len(pilot_X) > PILOT_FINAL_N:
        u2 = splitmix64_uniform(pilot_idx.astype(np.uint64), np.uint64(2026082802))
        keep = np.argsort(u2)[:PILOT_FINAL_N]
        pilot_X = pilot_X[keep]
        pilot_idx = pilot_idx[keep]

    # Median-impute ONLY for the X-only PCA pilot if missing values exist.
    medians = np.nanmedian(pilot_X, axis=0)
    imp = np.where(np.isfinite(pilot_X), pilot_X, medians[None, :])
    safe_std = np.where(std > 1e-12, std, 1.0)
    Xz = (imp - mean[None, :]) / safe_std[None, :]

    print(f"R0-3 X-only PCA pilot n={len(Xz):,}...")
    pca = PCA(n_components=1, svd_solver="randomized", random_state=20260828)
    z = pca.fit_transform(Xz).ravel()
    loading = pca.components_[0].copy()

    # Fix arbitrary PCA sign deterministically: largest absolute loading must be positive.
    anchor = int(np.argmax(np.abs(loading)))
    if loading[anchor] < 0:
        loading *= -1.0
        z *= -1.0

    z_mean = float(z.mean())
    z_std = float(z.std(ddof=0))
    z_std = z_std if z_std > 1e-12 else 1.0
    z_stdized = (z - z_mean) / z_std

    pca_df = pd.DataFrame({
        "feature": FEATURES,
        "global_mean": mean,
        "global_std": std,
        "pilot_impute_median": medians,
        "pc1_loading": loading,
    })
    pca_df.to_csv(outdir / "criteo_xonly_pc1_definition.csv", index=False)

    print("R0-4 Calibrating target-selection mechanisms from X only...")
    shifts = []
    # Null/no shift.
    shifts.append({
        "label": "null_ess1.0",
        "target_ess": 1.0,
        "beta": 0.0,
        "intercept": 0.0,
        "pilot_ess_ratio": 1.0,
        "pilot_target_share": 0.5,
        "pilot_p_target_p01": 0.5,
        "pilot_p_target_p50": 0.5,
        "pilot_p_target_p99": 0.5,
    })
    for ess in ESS_TARGETS:
        d = calibrate_beta(z_stdized, ess)
        d["label"] = f"pc1_ess{ess}"
        shifts.append(d)
    shift_df = pd.DataFrame(shifts)
    shift_df.to_csv(outdir / "criteo_shift_definitions.csv", index=False)

    # RCT balance diagnostics on the X-only pilot, descriptive only.
    # Re-read pilot rows is expensive; instead audit full-data treatment balance via moments already known.
    # Detailed source/target treatment balance will be computed after deterministic membership is instantiated in R1.

    summary = {
        "stage": "Criteo R0 Data and X-only Shift Audit",
        "data_path": str(data_path),
        "sha256": sha,
        "sha256_match": sha_match,
        "rows": int(total_rows),
        "expected_rows": EXPECTED_ROWS,
        "columns": columns,
        "pilot_rows": int(len(Xz)),
        "pilot_sampling": "deterministic splitmix64 row-index hash; outcome/treatment not used",
        "pc1_explained_variance_ratio": float(pca.explained_variance_ratio_[0]),
        "pc1_sign_anchor_feature": FEATURES[anchor],
        "pc1_pilot_score_mean_before_standardization": z_mean,
        "pc1_pilot_score_std_before_standardization": z_std,
        "primary_outcome": "visit",
        "secondary_outcome": "conversion",
        "exposure_policy": "excluded from model features because it may be post-treatment",
        "shift_definition_uses": "f0-f11 only",
        "target_selection_seed_reserved_for_R1": 2026082803,
        "method_blinding_rule": "R1 source/target membership and target-adapt policies are constructed without target outcomes; target A/Y are retained only for held-out benchmark evaluation.",
    }
    (outdir / "criteo_r0_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== CRITEO R0 AUDIT ===")
    print(f"rows={total_rows:,} hash_match={sha_match} pilot_n={len(Xz):,}")
    print(binary_df.to_string(index=False))
    print("\nPC1 explained variance ratio:", summary["pc1_explained_variance_ratio"])
    print("\n=== X-ONLY SHIFT DEFINITIONS ===")
    print(shift_df[[
        "label","target_ess","beta","intercept","pilot_ess_ratio",
        "pilot_target_share","pilot_p_target_p01","pilot_p_target_p50","pilot_p_target_p99"
    ]].to_string(index=False))
    print("\nFinished. Results:", outdir)


if __name__ == "__main__":
    main()
