from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

EXPECTED_RAW_SHA256 = "2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc"
EXPECTED_ROWS = 13_979_592
FEATURES = [f"f{i}" for i in range(12)]
PROPENSITY = 0.85
BUDGETS = (0.10, 0.30, 0.50)

MEMBERSHIP_SEED = np.uint64(2026082803)
ROLE_SEED = np.uint64(2026082805)

MODEL_NAMES = (
    "S-Logit",
    "T-Logit",
    "S-HGB",
    "T-HGB",
    "TO-HGB",
    "DR-HGB",
)

HGB_CLASS_PARAMS = dict(
    learning_rate=0.05,
    max_iter=150,
    max_leaf_nodes=31,
    min_samples_leaf=200,
    l2_regularization=1.0,
    max_bins=255,
    early_stopping=True,
    validation_fraction=0.10,
    n_iter_no_change=15,
    random_state=20260828,
)

HGB_REG_PARAMS = dict(
    learning_rate=0.05,
    max_iter=150,
    max_leaf_nodes=31,
    min_samples_leaf=200,
    l2_regularization=1.0,
    max_bins=255,
    early_stopping=True,
    validation_fraction=0.10,
    n_iter_no_change=15,
    random_state=20260828,
)


def sha256_file(path: Path, block_size: int = 4 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(block_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def sha256_small(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def splitmix64_uniform(indices: np.ndarray, seed: np.uint64) -> np.ndarray:
    with np.errstate(over="ignore"):
        z = indices.astype(np.uint64) + seed + np.uint64(0x9E3779B97F4A7C15)
        z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        z = z ^ (z >> np.uint64(31))
    return (z >> np.uint64(11)).astype(np.float64) * (1.0 / float(1 << 53))


def load_frozen_shift(r0_dir: Path, r01_dir: Path):
    r0_summary = json.loads((r0_dir / "criteo_r0_summary.json").read_text(encoding="utf-8"))
    shifts = pd.read_csv(r0_dir / "criteo_shift_definitions.csv")
    pc = pd.read_csv(r01_dir / "criteo_pc1_materialized_definition.csv")

    if list(pc["feature"]) != FEATURES:
        raise RuntimeError("PC1 feature order mismatch.")

    gmean = pc["global_mean"].to_numpy(float)
    gstd = pc["global_std"].to_numpy(float)
    med = pc["pilot_impute_median"].to_numpy(float)
    center = pc["pca_pilot_center_standardized_x"].to_numpy(float)
    loading = pc["pc1_loading_reconstructed"].to_numpy(float)
    score_mean = float(r0_summary["pc1_pilot_score_mean_before_standardization"])
    score_std = float(r0_summary["pc1_pilot_score_std_before_standardization"])
    safe_std = np.where(gstd > 1e-12, gstd, 1.0)

    return {
        "gmean": gmean,
        "gstd": safe_std,
        "median": med,
        "center": center,
        "loading": loading,
        "score_mean": score_mean,
        "score_std": score_std,
        "shifts": shifts,
        "r0_summary": r0_summary,
    }


def pc1_z(X: np.ndarray, frozen) -> np.ndarray:
    X = np.where(np.isfinite(X), X, frozen["median"][None, :])
    Xs = (X - frozen["gmean"][None, :]) / frozen["gstd"][None, :]
    raw = (Xs - frozen["center"][None, :]) @ frozen["loading"]
    return (raw - frozen["score_mean"]) / frozen["score_std"]


def p_target_from_z(z: np.ndarray, shift_row) -> np.ndarray:
    return np.clip(
        expit(float(shift_row["intercept"]) + float(shift_row["beta"]) * z),
        1e-12,
        1 - 1e-12,
    )


def scenario_seed_offset(name: str) -> int:
    return int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:8], 16)


def build_s_logit_features(X: np.ndarray, a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64).reshape(-1, 1)
    X = np.asarray(X, dtype=np.float64)
    return np.column_stack([X, a, X * a])


def train_model_library(X: np.ndarray, a: np.ndarray, y: np.ndarray, scenario_name: str):
    off = scenario_seed_offset(scenario_name) % 100000
    bundles = {}

    # 1) S-Logit with treatment and treatment-by-X interactions.
    s_logit = Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(
            C=1.0, solver="lbfgs", max_iter=250, random_state=20260828 + off
        )),
    ])
    s_logit.fit(build_s_logit_features(X, a), y)
    bundles["S-Logit"] = {"type": "s_logit", "model": s_logit}

    # 2) T-Logit.
    t0 = Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(
            C=1.0, solver="lbfgs", max_iter=250, random_state=20260829 + off
        )),
    ])
    t1 = Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(
            C=1.0, solver="lbfgs", max_iter=250, random_state=20260830 + off
        )),
    ])
    t0.fit(X[a == 0], y[a == 0])
    t1.fit(X[a == 1], y[a == 1])
    bundles["T-Logit"] = {"type": "t_logit", "model0": t0, "model1": t1}

    # 3) S-HGB.
    hgb_s_params = dict(HGB_CLASS_PARAMS)
    hgb_s_params["random_state"] = 20260831 + off
    s_hgb = HistGradientBoostingClassifier(**hgb_s_params)
    s_hgb.fit(np.column_stack([X, a]), y)
    bundles["S-HGB"] = {"type": "s_hgb", "model": s_hgb}

    # 4) T-HGB. These outcome models are also reused to build DR pseudo-outcomes.
    hgb0_params = dict(HGB_CLASS_PARAMS); hgb0_params["random_state"] = 20260832 + off
    hgb1_params = dict(HGB_CLASS_PARAMS); hgb1_params["random_state"] = 20260833 + off
    h0 = HistGradientBoostingClassifier(**hgb0_params)
    h1 = HistGradientBoostingClassifier(**hgb1_params)
    h0.fit(X[a == 0], y[a == 0])
    h1.fit(X[a == 1], y[a == 1])
    bundles["T-HGB"] = {"type": "t_hgb", "model0": h0, "model1": h1}

    # 5) Transformed-outcome HGB.
    transformed = y * (a / PROPENSITY - (1.0 - a) / (1.0 - PROPENSITY))
    to_params = dict(HGB_REG_PARAMS); to_params["random_state"] = 20260834 + off
    to_hgb = HistGradientBoostingRegressor(**to_params)
    to_hgb.fit(X, transformed)
    bundles["TO-HGB"] = {"type": "direct_tau", "model": to_hgb, "learner": "transformed_outcome"}

    # 6) DR-HGB. Candidate learning can reuse training-fitted outcome models because
    # final algorithm selection occurs on an independent source_select split.
    mu0 = h0.predict_proba(X)[:, 1]
    mu1 = h1.predict_proba(X)[:, 1]
    dr = (
        (mu1 - mu0)
        + a / PROPENSITY * (y - mu1)
        - (1.0 - a) / (1.0 - PROPENSITY) * (y - mu0)
    )
    dr_params = dict(HGB_REG_PARAMS); dr_params["random_state"] = 20260835 + off
    dr_hgb = HistGradientBoostingRegressor(**dr_params)
    dr_hgb.fit(X, dr)
    bundles["DR-HGB"] = {"type": "direct_tau", "model": dr_hgb, "learner": "dr_pseudo_outcome"}

    return bundles


def predict_tau(bundle, X: np.ndarray) -> np.ndarray:
    typ = bundle["type"]
    X = np.asarray(X, dtype=np.float64)

    if typ == "s_logit":
        n = len(X)
        p1 = bundle["model"].predict_proba(build_s_logit_features(X, np.ones(n)))[:, 1]
        p0 = bundle["model"].predict_proba(build_s_logit_features(X, np.zeros(n)))[:, 1]
        return p1 - p0

    if typ == "t_logit":
        return bundle["model1"].predict_proba(X)[:, 1] - bundle["model0"].predict_proba(X)[:, 1]

    if typ == "s_hgb":
        n = len(X)
        p1 = bundle["model"].predict_proba(np.column_stack([X, np.ones(n)]))[:, 1]
        p0 = bundle["model"].predict_proba(np.column_stack([X, np.zeros(n)]))[:, 1]
        return p1 - p0

    if typ == "t_hgb":
        return bundle["model1"].predict_proba(X)[:, 1] - bundle["model0"].predict_proba(X)[:, 1]

    if typ == "direct_tau":
        return bundle["model"].predict(X)

    raise ValueError(f"Unknown bundle type: {typ}")


def collect_scenario_data(
    data_path: Path,
    frozen,
    shift_row,
    chunksize: int,
):
    name = str(shift_row["label"])
    Xtr_parts, atr_parts, ytr_parts = [], [], []
    Xsel_parts, asel_parts, ysel_parts = [], [], []

    counts = {
        "rows": 0,
        "source": 0,
        "target": 0,
        "source_train": 0,
        "source_select": 0,
        "source_infer": 0,
        "target_adapt": 0,
        "target_infer": 0,
        "source_train_treated": 0,
        "source_train_events": 0,
        "source_select_treated": 0,
        "source_select_events": 0,
    }
    odds_sum_source = 0.0
    odds2_sum_source = 0.0

    total = 0
    usecols = FEATURES + ["treatment", "visit"]
    for chunk_id, df in enumerate(pd.read_csv(data_path, compression="gzip", usecols=usecols, chunksize=chunksize)):
        n = len(df)
        idx = np.arange(total, total+n, dtype=np.uint64)
        X = df[FEATURES].to_numpy(dtype=np.float32, copy=False)
        z = pc1_z(X.astype(np.float64, copy=False), frozen)
        p = p_target_from_z(z, shift_row)

        u_mem = splitmix64_uniform(idx, MEMBERSHIP_SEED)
        is_target = u_mem < p
        is_source = ~is_target
        u_role = splitmix64_uniform(idx, ROLE_SEED)

        s_train = is_source & (u_role < 0.30)
        s_select = is_source & (u_role >= 0.30) & (u_role < 0.50)
        s_infer = is_source & (u_role >= 0.50)
        t_adapt = is_target & (u_role < 0.25)
        t_infer = is_target & (u_role >= 0.25)

        counts["rows"] += n
        counts["source"] += int(is_source.sum())
        counts["target"] += int(is_target.sum())
        counts["source_train"] += int(s_train.sum())
        counts["source_select"] += int(s_select.sum())
        counts["source_infer"] += int(s_infer.sum())
        counts["target_adapt"] += int(t_adapt.sum())
        counts["target_infer"] += int(t_infer.sum())

        # The constant prevalence factor cancels from ESS.
        odds = p[is_source] / (1.0 - p[is_source])
        odds_sum_source += float(odds.sum())
        odds2_sum_source += float(np.sum(odds * odds))

        # Target A/Y are deliberately never indexed or summarized.
        if np.any(s_train):
            a = df["treatment"].to_numpy(dtype=np.float32, copy=False)[s_train]
            y = df["visit"].to_numpy(dtype=np.float32, copy=False)[s_train]
            Xtr_parts.append(X[s_train].copy())
            atr_parts.append(a.copy())
            ytr_parts.append(y.copy())
            counts["source_train_treated"] += int(a.sum())
            counts["source_train_events"] += int(y.sum())

        if np.any(s_select):
            a = df["treatment"].to_numpy(dtype=np.float32, copy=False)[s_select]
            y = df["visit"].to_numpy(dtype=np.float32, copy=False)[s_select]
            Xsel_parts.append(X[s_select].copy())
            asel_parts.append(a.copy())
            ysel_parts.append(y.copy())
            counts["source_select_treated"] += int(a.sum())
            counts["source_select_events"] += int(y.sum())

        total += n
        print(f"  [{name}] chunk={chunk_id+1} rows={total:,}")

    if total != EXPECTED_ROWS:
        raise RuntimeError(f"Row count mismatch in {name}: {total}")

    Xtr = np.vstack(Xtr_parts).astype(np.float32, copy=False)
    atr = np.concatenate(atr_parts).astype(np.float32, copy=False)
    ytr = np.concatenate(ytr_parts).astype(np.float32, copy=False)
    Xsel = np.vstack(Xsel_parts).astype(np.float32, copy=False)
    asel = np.concatenate(asel_parts).astype(np.float32, copy=False)
    ysel = np.concatenate(ysel_parts).astype(np.float32, copy=False)

    ess = float((odds_sum_source * odds_sum_source) / (counts["source"] * odds2_sum_source))
    counts["realized_source_to_target_ess_oracle"] = ess
    counts["realized_target_share"] = counts["target"] / counts["rows"]
    counts["source_train_treatment_rate"] = counts["source_train_treated"] / counts["source_train"]
    counts["source_train_visit_rate"] = counts["source_train_events"] / counts["source_train"]
    counts["source_select_treatment_rate"] = counts["source_select_treated"] / counts["source_select"]
    counts["source_select_visit_rate"] = counts["source_select_events"] / counts["source_select"]
    return Xtr, atr, ytr, Xsel, asel, ysel, counts


def source_ipw_gain(policy: np.ndarray, a: np.ndarray, y: np.ndarray):
    psi = policy * (a / PROPENSITY * y - (1.0 - a) / (1.0 - PROPENSITY) * y)
    est = float(np.mean(psi))
    se = float(np.std(psi, ddof=1) / math.sqrt(len(psi)))
    return est, se


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--r0-outdir", required=True)
    ap.add_argument("--r01-outdir", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--chunksize", type=int, default=500_000)
    args = ap.parse_args()

    data_path = Path(args.data).resolve()
    r0 = Path(args.r0_outdir).resolve()
    r01 = Path(args.r01_outdir).resolve()
    out = Path(args.outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    model_root = out / "models"
    model_root.mkdir(exist_ok=True)

    print("R1-1 Verify frozen inputs...")
    raw_sha = sha256_file(data_path)
    if raw_sha != EXPECTED_RAW_SHA256:
        raise RuntimeError(f"Raw SHA mismatch: {raw_sha}")

    frozen = load_frozen_shift(r0, r01)
    shifts = frozen["shifts"].copy()

    protocol = {
        "stage": "Criteo R1 Population Construction and Source Model Library",
        "raw_sha256": raw_sha,
        "r0_shift_definition_sha256": sha256_small(r0 / "criteo_shift_definitions.csv"),
        "r01_pc1_materialization_sha256": sha256_small(r01 / "criteo_pc1_materialized_definition.csv"),
        "membership_seed": int(MEMBERSHIP_SEED),
        "role_seed": int(ROLE_SEED),
        "source_split": {"train":0.30, "select":0.20, "infer":0.50},
        "target_split": {"adapt":0.25, "infer":0.75},
        "primary_outcome": "visit",
        "target_outcomes_used": False,
        "source_selection_metric": "IPW incremental policy gain on independent source_select",
        "treatment_propensity": PROPENSITY,
        "budgets": list(BUDGETS),
        "model_library": list(MODEL_NAMES),
        "model_hyperparameters": {
            "S-Logit": "standardized logistic; X+A+A*X; C=1; lbfgs; max_iter=250",
            "T-Logit": "two standardized arm-specific logistic models; C=1",
            "S-HGB": HGB_CLASS_PARAMS,
            "T-HGB": HGB_CLASS_PARAMS,
            "TO-HGB": HGB_REG_PARAMS,
            "DR-HGB": HGB_REG_PARAMS,
        },
        "note": "No hyperparameter tuning on source_select or target data.",
    }
    (out / "criteo_r1_protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")

    pop_rows = []
    selection_rows = []
    score_rows = []
    winner_rows = []

    for sidx, (_, shift_row) in enumerate(shifts.iterrows()):
        name = str(shift_row["label"])
        print(f"\nR1-2 Construct scenario {name} and collect SOURCE train/select only...")
        Xtr, atr, ytr, Xsel, asel, ysel, counts = collect_scenario_data(
            data_path, frozen, shift_row, args.chunksize
        )

        counts.update({
            "scenario": name,
            "target_ess_frozen": float(shift_row["target_ess"]),
            "beta_frozen": float(shift_row["beta"]),
            "intercept_frozen": float(shift_row["intercept"]),
            "target_outcome_rows_accessed": 0,
        })
        pop_rows.append(counts)

        print(
            f"  source_train={len(Xtr):,} source_select={len(Xsel):,} "
            f"realized_ESS={counts['realized_source_to_target_ess_oracle']:.4f}"
        )

        print(f"R1-3 Train frozen 6-model library for {name}...")
        start = time.time()
        bundles = train_model_library(
            Xtr.astype(np.float64, copy=False),
            atr.astype(np.float64, copy=False),
            ytr.astype(np.float64, copy=False),
            name,
        )
        train_minutes = (time.time() - start) / 60.0
        print(f"  trained 6 models in {train_minutes:.2f} minutes")

        scenario_dir = model_root / name
        scenario_dir.mkdir(exist_ok=True)
        for model_name in MODEL_NAMES:
            joblib.dump(bundles[model_name], scenario_dir / f"{model_name}.joblib", compress=3)

        print(f"R1-4 Independent source selection for {name}...")
        for model_name in MODEL_NAMES:
            bundle = bundles[model_name]
            score_tr = np.asarray(
                predict_tau(bundle, Xtr.astype(np.float64, copy=False)),
                dtype=np.float64
            )
            score_sel = np.asarray(
                predict_tau(bundle, Xsel.astype(np.float64, copy=False)),
                dtype=np.float64
            )

            if not (np.all(np.isfinite(score_tr)) and np.all(np.isfinite(score_sel))):
                raise RuntimeError(f"Non-finite score in {name}/{model_name}")
            if float(np.std(score_sel)) <= 1e-10:
                raise RuntimeError(f"Degenerate score in {name}/{model_name}")

            score_rows.append({
                "scenario": name,
                "model": model_name,
                "train_score_mean": float(score_tr.mean()),
                "train_score_std": float(score_tr.std()),
                "train_score_p01": float(np.quantile(score_tr, .01)),
                "train_score_p50": float(np.quantile(score_tr, .50)),
                "train_score_p99": float(np.quantile(score_tr, .99)),
                "select_score_mean": float(score_sel.mean()),
                "select_score_std": float(score_sel.std()),
                "train_minutes_scenario_total": train_minutes,
            })

            for q in BUDGETS:
                th = float(np.quantile(score_tr, 1.0-q))
                policy = (score_sel >= th).astype(np.float64)
                gain, se = source_ipw_gain(
                    policy,
                    asel.astype(np.float64, copy=False),
                    ysel.astype(np.float64, copy=False),
                )
                selection_rows.append({
                    "scenario": name,
                    "budget": q,
                    "model": model_name,
                    "source_train_threshold": th,
                    "source_select_policy_rate": float(policy.mean()),
                    "source_select_ipw_gain": gain,
                    "source_select_ipw_se": se,
                })

        # Select winner independently for every budget.
        temp = pd.DataFrame([r for r in selection_rows if r["scenario"] == name])
        for q in BUDGETS:
            g = temp[temp["budget"] == q].sort_values(
                ["source_select_ipw_gain", "model"], ascending=[False, True]
            )
            best = g.iloc[0]
            second = g.iloc[1]
            winner_rows.append({
                "scenario": name,
                "budget": q,
                "source_winner": best["model"],
                "winner_ipw_gain": float(best["source_select_ipw_gain"]),
                "runner_up": second["model"],
                "runner_up_ipw_gain": float(second["source_select_ipw_gain"]),
                "winner_minus_runner_up": float(
                    best["source_select_ipw_gain"] - second["source_select_ipw_gain"]
                ),
            })

        # Release large arrays before next scenario.
        del Xtr, atr, ytr, Xsel, asel, ysel, bundles

    pop = pd.DataFrame(pop_rows)
    selection = pd.DataFrame(selection_rows)
    score = pd.DataFrame(score_rows)
    winners = pd.DataFrame(winner_rows)

    pop.to_csv(out / "criteo_r1_population_audit.csv", index=False)
    selection.to_csv(out / "criteo_r1_source_selection.csv", index=False)
    score.to_csv(out / "criteo_r1_score_diagnostics.csv", index=False)
    winners.to_csv(out / "criteo_r1_source_winners.csv", index=False)

    gate_rows = []
    for _, r in pop.iterrows():
        ess_pass = abs(
            float(r["realized_source_to_target_ess_oracle"]) - float(r["target_ess_frozen"])
        ) <= 0.03
        split_pass = (
            int(r["source_train"]) > 100_000
            and int(r["source_select"]) > 100_000
            and int(r["source_infer"]) > 100_000
            and int(r["target_adapt"]) > 100_000
            and int(r["target_infer"]) > 100_000
        )
        treatment_pass = abs(float(r["source_train_treatment_rate"]) - PROPENSITY) <= 0.005
        model_count = int(score[score["scenario"] == r["scenario"]]["model"].nunique())
        finite_selection = bool(
            np.all(np.isfinite(
                selection.loc[selection["scenario"] == r["scenario"], "source_select_ipw_gain"]
            ))
        )
        gate_rows.append({
            "scenario": r["scenario"],
            "realized_ess_pass_within_03": ess_pass,
            "split_size_pass": split_pass,
            "source_train_randomization_pass_within_005": treatment_pass,
            "six_models_fit_pass": model_count == 6,
            "finite_source_selection_pass": finite_selection,
            "target_outcome_blinding_pass": int(r["target_outcome_rows_accessed"]) == 0,
        })

    gate = pd.DataFrame(gate_rows)
    gate.to_csv(out / "criteo_r1_gate.csv", index=False)

    summary = {
        "stage": "Criteo R1 Population Construction and Source Model Library",
        "rows": EXPECTED_ROWS,
        "scenarios": list(pop["scenario"]),
        "models": list(MODEL_NAMES),
        "budgets": list(BUDGETS),
        "all_gate_pass": bool(
            gate.drop(columns=["scenario"]).astype(bool).all(axis=None)
        ),
        "target_outcomes_used": False,
        "source_infer_outcomes_used": False,
        "next_stage_if_pass": "R2 target-X-only portability inference; source_infer outcomes become available there.",
    }
    (out / "criteo_r1_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== CRITEO R1 POPULATION AUDIT ===")
    print(pop[[
        "scenario","source","target","source_train","source_select","source_infer",
        "target_adapt","target_infer","realized_target_share",
        "realized_source_to_target_ess_oracle",
        "source_train_treatment_rate","source_train_visit_rate",
        "source_select_treatment_rate","source_select_visit_rate"
    ]].to_string(index=False))

    print("\n=== CRITEO R1 SOURCE WINNERS ===")
    print(winners.to_string(index=False))

    print("\n=== CRITEO R1 GATE ===")
    print(gate.to_string(index=False))
    print("\nSummary:", summary)
    print("\nFinished. Results:", out)


if __name__ == "__main__":
    main()
