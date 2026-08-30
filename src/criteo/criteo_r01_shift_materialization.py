from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.decomposition import PCA

EXPECTED_RAW_SHA256 = "2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc"
EXPECTED_ROWS = 13_979_592
FEATURES = [f"f{i}" for i in range(12)]
PILOT_HASH_SEED = np.uint64(2026082801)
PILOT_SAMPLE_RATE = 0.020
PILOT_FINAL_N = 250_000
QUANTILE_SAMPLE_SEED = np.uint64(2026082804)
QUANTILE_SAMPLE_RATE = 0.08  # ~1.1M rows, X-only diagnostics


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
    with np.errstate(over="ignore"):
        z = indices.astype(np.uint64) + seed + np.uint64(0x9E3779B97F4A7C15)
        z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        z = z ^ (z >> np.uint64(31))
    return (z >> np.uint64(11)).astype(np.float64) * (1.0 / float(1 << 53))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--r0-outdir", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--chunksize", type=int, default=500_000)
    args = ap.parse_args()

    data_path = Path(args.data).resolve()
    r0 = Path(args.r0_outdir).resolve()
    out = Path(args.outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    print("R0.1-1 Verify frozen inputs...")
    sha = sha256_file(data_path)
    if sha != EXPECTED_RAW_SHA256:
        raise RuntimeError(f"Raw Criteo SHA mismatch: {sha}")

    feature_def = pd.read_csv(r0 / "criteo_xonly_pc1_definition.csv")
    shift_def = pd.read_csv(r0 / "criteo_shift_definitions.csv")
    r0_summary = json.loads((r0 / "criteo_r0_summary.json").read_text(encoding="utf-8"))

    if list(feature_def["feature"]) != FEATURES:
        raise RuntimeError("R0 feature definition order mismatch.")
    if int(r0_summary["rows"]) != EXPECTED_ROWS:
        raise RuntimeError("R0 row-count provenance mismatch.")

    gmean = feature_def["global_mean"].to_numpy(float)
    gstd = feature_def["global_std"].to_numpy(float)
    medians = feature_def["pilot_impute_median"].to_numpy(float)
    old_loading = feature_def["pc1_loading"].to_numpy(float)
    safe_std = np.where(gstd > 1e-12, gstd, 1.0)

    # Rebuild the exact deterministic pilot.
    print("R0.1-2 Reconstruct deterministic X-only PCA pilot...")
    pilot_parts, pilot_indices = [], []
    total = 0
    for df in pd.read_csv(data_path, compression="gzip", usecols=FEATURES, chunksize=args.chunksize):
        n = len(df)
        idx = np.arange(total, total+n, dtype=np.uint64)
        u = splitmix64_uniform(idx, PILOT_HASH_SEED)
        keep = u < PILOT_SAMPLE_RATE
        if np.any(keep):
            pilot_parts.append(df[FEATURES].to_numpy(float, copy=False)[keep].copy())
            pilot_indices.append(idx[keep].astype(np.int64))
        total += n

    if total != EXPECTED_ROWS:
        raise RuntimeError(f"Row count mismatch: {total}")

    pilot_X = np.vstack(pilot_parts)
    pilot_idx = np.concatenate(pilot_indices)
    if len(pilot_X) > PILOT_FINAL_N:
        u2 = splitmix64_uniform(pilot_idx.astype(np.uint64), np.uint64(2026082802))
        keep = np.argsort(u2)[:PILOT_FINAL_N]
        pilot_X = pilot_X[keep]
        pilot_idx = pilot_idx[keep]

    imp = np.where(np.isfinite(pilot_X), pilot_X, medians[None, :])
    Xz = (imp - gmean[None, :]) / safe_std[None, :]
    pca = PCA(n_components=1, svd_solver="randomized", random_state=20260828)
    score = pca.fit_transform(Xz).ravel()
    loading = pca.components_[0].copy()

    anchor = int(np.argmax(np.abs(loading)))
    if loading[anchor] < 0:
        loading *= -1.0
        score *= -1.0

    pilot_n_saved = int(len(Xz))
    score_mean = float(score.mean())
    score_std = float(score.std(ddof=0))
    loading_diff = float(np.max(np.abs(loading - old_loading)))
    score_std_diff = abs(score_std - float(r0_summary["pc1_pilot_score_std_before_standardization"]))
    explained_diff = abs(float(pca.explained_variance_ratio_[0]) - float(r0_summary["pc1_explained_variance_ratio"]))

    print(f"pilot_n={len(Xz):,}")
    print("max_abs_loading_diff:", loading_diff)
    print("score_std_diff:", score_std_diff)
    print("explained_variance_ratio_diff:", explained_diff)

    if loading_diff > 1e-10 or score_std_diff > 1e-10 or explained_diff > 1e-10:
        raise RuntimeError("R0 PCA could not be exactly reconstructed. Stop before R1.")

    materialized = feature_def.copy()
    materialized["pca_pilot_center_standardized_x"] = pca.mean_
    materialized["pc1_loading_reconstructed"] = loading
    materialized.to_csv(out / "criteo_pc1_materialized_definition.csv", index=False)

    # Full-X expected selection diagnostics with frozen beta/intercept.
    print("R0.1-3 Audit frozen shift definitions on all X...")
    defs = shift_def.to_dict("records")
    accum = {}
    qsamples = {d["label"]: [] for d in defs}
    total = 0

    for df in pd.read_csv(data_path, compression="gzip", usecols=FEATURES, chunksize=args.chunksize):
        n = len(df)
        idx = np.arange(total, total+n, dtype=np.uint64)
        X = df[FEATURES].to_numpy(float, copy=False)
        X = np.where(np.isfinite(X), X, medians[None, :])
        Xz = (X - gmean[None, :]) / safe_std[None, :]
        raw_score = (Xz - pca.mean_[None, :]) @ loading
        z = (raw_score - score_mean) / score_std

        qkeep = splitmix64_uniform(idx, QUANTILE_SAMPLE_SEED) < QUANTILE_SAMPLE_RATE

        for d in defs:
            label = d["label"]
            beta = float(d["beta"])
            intercept = float(d["intercept"])
            p = np.clip(expit(intercept + beta*z), 1e-12, 1-1e-12)
            pi_t_target = 0.5  # frozen R0 calibration target
            r = (p/(1-p))*((1-pi_t_target)/pi_t_target)
            sw = 1-p

            a = accum.setdefault(label, {
                "n":0, "sum_p":0.0, "sum_sw":0.0, "sum_sw_r":0.0, "sum_sw_r2":0.0,
                "max_p":0.0, "min_p":1.0, "max_r":0.0
            })
            a["n"] += n
            a["sum_p"] += float(p.sum())
            a["sum_sw"] += float(sw.sum())
            a["sum_sw_r"] += float(np.sum(sw*r))
            a["sum_sw_r2"] += float(np.sum(sw*r*r))
            a["max_p"] = max(a["max_p"], float(p.max()))
            a["min_p"] = min(a["min_p"], float(p.min()))
            a["max_r"] = max(a["max_r"], float(r.max()))

            if np.any(qkeep):
                qsamples[label].append(np.column_stack([p[qkeep], r[qkeep]]).astype(np.float32))

        total += n
        print(f"  rows={total:,}")

    rows = []
    for d in defs:
        label = d["label"]
        a = accum[label]
        target_share = a["sum_p"]/a["n"]
        e1 = a["sum_sw_r"]/a["sum_sw"]
        e2 = a["sum_sw_r2"]/a["sum_sw"]
        ess = (e1*e1)/e2
        sample = np.vstack(qsamples[label])
        p_s, r_s = sample[:,0], sample[:,1]
        rows.append({
            "label": label,
            "target_ess_frozen": float(d["target_ess"]),
            "beta_frozen": float(d["beta"]),
            "intercept_frozen": float(d["intercept"]),
            "full_expected_target_share": float(target_share),
            "full_expected_source_to_target_ess": float(ess),
            "ess_abs_deviation": float(abs(ess-float(d["target_ess"]))),
            "p_target_min_full": float(a["min_p"]),
            "p_target_p001_sample": float(np.quantile(p_s, .001)),
            "p_target_p01_sample": float(np.quantile(p_s, .01)),
            "p_target_p50_sample": float(np.quantile(p_s, .50)),
            "p_target_p99_sample": float(np.quantile(p_s, .99)),
            "p_target_p999_sample": float(np.quantile(p_s, .999)),
            "p_target_max_full": float(a["max_p"]),
            "ratio_p50_sample": float(np.quantile(r_s, .50)),
            "ratio_p99_sample": float(np.quantile(r_s, .99)),
            "ratio_p999_sample": float(np.quantile(r_s, .999)),
            "ratio_max_full": float(a["max_r"]),
            "quantile_sample_n": int(len(sample)),
        })

    audit = pd.DataFrame(rows)
    audit.to_csv(out / "criteo_full_x_shift_audit.csv", index=False)

    gate_rows = []
    for _, r in audit.iterrows():
        target_share_pass = abs(float(r["full_expected_target_share"]) - .5) <= .02
        ess_pass = abs(float(r["full_expected_source_to_target_ess"]) - float(r["target_ess_frozen"])) <= .03
        gate_rows.append({
            "label": r["label"],
            "pca_reconstruction_pass": True,
            "target_share_pass_within_02": target_share_pass,
            "ess_generalization_pass_within_03": ess_pass,
        })
    gate = pd.DataFrame(gate_rows)
    gate.to_csv(out / "criteo_r01_gate.csv", index=False)

    summary = {
        "stage": "Criteo R0.1 Shift Materialization Audit",
        "raw_sha256": sha,
        "rows": total,
        "pilot_n": pilot_n_saved,
        "pca_max_abs_loading_diff": loading_diff,
        "pca_score_std_diff": score_std_diff,
        "pca_explained_variance_ratio_diff": explained_diff,
        "all_target_share_pass": bool(gate["target_share_pass_within_02"].all()),
        "all_ess_generalization_pass": bool(gate["ess_generalization_pass_within_03"].all()),
        "outcome_blinding": "No treatment, visit, conversion, or exposure columns read in R0.1.",
        "note": "Frozen R0 beta/intercept are audited, never recalibrated.",
    }
    (out / "criteo_r01_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== CRITEO R0.1 FULL-X SHIFT AUDIT ===")
    print(audit.to_string(index=False))
    print("\n=== R0.1 GATE ===")
    print(gate.to_string(index=False))
    print("\nSummary:", summary)
    print("\nFinished. Results:", out)


if __name__ == "__main__":
    main()
