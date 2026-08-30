from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

EXPECTED_R1_SHA256 = "1c7fe26cebf45f9215c7ec8de54f06ec2e72eb8e72744b3fb2a8d392ae0f3e0e"
EXPECTED_R1F_WINNERS_SHA256 = "3e547e2a75829cc257c7f38aae200c2acedc9caeba441f6841c64db21af0cdfe"
EXPECTED_R1F_SELECTION_SHA256 = "6cff4bc7cafd03cc95fc4fd7be11816830044f3f055b0881298fedb78aefd83d"

FEATURES = [f"f{i}" for i in range(12)]
BUDGETS = (0.10, 0.30, 0.50)
MODELS = ("S-Logit","T-Logit","S-HGB","T-HGB","TO-HGB","DR-HGB")
TIE_SEED = np.uint64(2026082806)
DOMAIN_SAMPLE_SEED = np.uint64(2026082809)
GAUSSIAN_SEED_BASE = 2026082810
DOMAIN_SAMPLE_N = 1_000_000
GAUSSIAN_DRAWS = 20_000
EPSILON_GRID = (0.0005, 0.0010, 0.0020, 0.0050)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_r1_module(path: Path):
    sha = sha256_file(path)
    if sha != EXPECTED_R1_SHA256:
        raise RuntimeError(f"Frozen R1 source hash mismatch: {sha}")
    spec = importlib.util.spec_from_file_location("r1_frozen", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod, sha


def choose_smallest_hash(r1, row_idx: np.ndarray, n: int, seed: np.uint64):
    if len(row_idx) <= n:
        return np.arange(len(row_idx))
    u = r1.splitmix64_uniform(row_idx.astype(np.uint64), seed)
    return np.argpartition(u, n)[:n]


def fit_exact_topq(r1, score: np.ndarray, row_idx: np.ndarray, q: float):
    score = np.asarray(score, dtype=np.float64)
    row_idx = np.asarray(row_idx, dtype=np.uint64)
    n = len(score)
    k = int(round(q*n))
    c = float(np.partition(score, n-k)[n-k])

    gt = score > c
    eq = score == c
    n_gt = int(gt.sum())
    n_eq = int(eq.sum())
    need = int(k-n_gt)
    if need < 0 or need > n_eq:
        raise RuntimeError("Invalid target-adapt tie geometry")

    u = r1.splitmix64_uniform(row_idx, TIE_SEED)
    if need == 0:
        ucut = -1.0
    elif need == n_eq:
        ucut = 1.0
    else:
        ue = u[eq]
        ucut = float(np.partition(ue, need-1)[need-1])

    pol = gt | (eq & (u <= ucut))
    if int(pol.sum()) != k:
        raise RuntimeError(f"Target-adapt exact budget failure: wanted {k}, got {pol.sum()}")

    return {
        "score_cut":c,
        "score_cut_hex":c.hex(),
        "tie_u_cut":ucut,
        "tie_u_cut_hex":float(ucut).hex(),
        "target_adapt_n":n,
        "target_adapt_k":k,
        "target_adapt_rate":float(k/n),
        "threshold_tie_count":n_eq,
        "tie_selected_count":need,
    }


def apply_rule(r1, score: np.ndarray, row_idx: np.ndarray, rule):
    score = np.asarray(score, dtype=np.float64)
    u = r1.splitmix64_uniform(np.asarray(row_idx,dtype=np.uint64), TIE_SEED)
    return (score > rule["score_cut"]) | (
        (score == rule["score_cut"]) & (u <= rule["tie_u_cut"])
    )


def collect_adaptation_and_domain_data(r1, data_path: Path, frozen, shift, chunksize: int):
    Xs, Is = [], []
    Xt, It = [], []
    total = 0

    for ci, df in enumerate(pd.read_csv(data_path, compression="gzip", usecols=FEATURES, chunksize=chunksize)):
        n = len(df)
        idx = np.arange(total,total+n,dtype=np.uint64)
        X = df[FEATURES].to_numpy(np.float32,copy=False)
        z = r1.pc1_z(X.astype(np.float64,copy=False), frozen)
        p_t = r1.p_target_from_z(z, shift)

        target = r1.splitmix64_uniform(idx,r1.MEMBERSHIP_SEED) < p_t
        source = ~target
        role = r1.splitmix64_uniform(idx,r1.ROLE_SEED)

        s_train = source & (role < .30)
        t_adapt = target & (role < .25)

        if np.any(s_train):
            Xs.append(X[s_train].copy()); Is.append(idx[s_train].copy())
        if np.any(t_adapt):
            Xt.append(X[t_adapt].copy()); It.append(idx[t_adapt].copy())

        total += n
        print(f"  [adapt {shift['label']}] chunk={ci+1} rows={total:,}")

    return np.vstack(Xs), np.concatenate(Is), np.vstack(Xt), np.concatenate(It)


def fit_domain_ratio_model(r1, Xs, Is, Xt, It):
    ns = min(DOMAIN_SAMPLE_N,len(Xs))
    nt = min(DOMAIN_SAMPLE_N,len(Xt))
    n = min(ns,nt)

    si = choose_smallest_hash(r1,Is,n,DOMAIN_SAMPLE_SEED)
    ti = choose_smallest_hash(r1,It,n,DOMAIN_SAMPLE_SEED)

    X = np.vstack([Xs[si],Xt[ti]]).astype(np.float64)
    d = np.concatenate([np.zeros(n,dtype=np.int8),np.ones(n,dtype=np.int8)])

    mdl = Pipeline([
        ("scale",StandardScaler()),
        ("logit",LogisticRegression(
            C=1.0,solver="lbfgs",max_iter=250,random_state=20260828
        ))
    ])
    mdl.fit(X,d)
    return mdl, n


def ratio_predict(model, X):
    p = np.clip(model.predict_proba(X.astype(np.float64,copy=False))[:,1],1e-8,1-1e-8)
    # Domain model was fit with equal source/target class counts.
    return p/(1-p)


def oracle_ratio(r1, X, frozen, shift, source_count, target_count):
    z = r1.pc1_z(X.astype(np.float64,copy=False),frozen)
    pt = r1.p_target_from_z(z,shift)
    return (pt/(1-pt))*(source_count/target_count)


class Moments:
    def __init__(self,k):
        self.k=k
        self.n=0
        self.sum=np.zeros(k,dtype=np.float64)
        self.cross=np.zeros((k,k),dtype=np.float64)

    def update(self,Z):
        Z=np.asarray(Z,dtype=np.float64)
        if len(Z)==0:
            return
        self.n += len(Z)
        self.sum += Z.sum(axis=0)
        self.cross += Z.T@Z

    def mean(self):
        return self.sum/self.n

    def covariance_of_mean(self):
        if self.n <= 1:
            raise RuntimeError("Insufficient inference rows")
        centered_ss = self.cross - np.outer(self.sum,self.sum)/self.n
        sample_cov = centered_ss/(self.n-1)
        return sample_cov/self.n


def make_contrasts(winners: pd.DataFrame, scenario: str):
    rows=[]
    for q in BUDGETS:
        w = winners[
            (winners.scenario==scenario)&(np.isclose(winners.budget,q))
        ].iloc[0].final_source_winner
        for m in MODELS:
            if m == w:
                continue
            rows.append({
                "budget":q,
                "source_winner":w,
                "competitor":m,
                "contrast":f"q={q:.1f}:{m}-{w}",
            })
    if len(rows)!=15:
        raise RuntimeError("Expected 15 directed contrasts")
    return pd.DataFrame(rows)


def stabilize_corr(cov):
    se=np.sqrt(np.maximum(np.diag(cov),0))
    if np.any(se <= 1e-12):
        raise RuntimeError("Degenerate contrast SE")
    corr=cov/np.outer(se,se)
    corr=(corr+corr.T)/2
    np.fill_diagonal(corr,1.0)
    eigval,eigvec=np.linalg.eigh(corr)
    min_eig=float(eigval.min())
    eigval=np.maximum(eigval,1e-10)
    corr_psd=(eigvec*eigval)@eigvec.T
    d=np.sqrt(np.diag(corr_psd))
    corr_psd=corr_psd/np.outer(d,d)
    return se,corr_psd,min_eig


def gaussian_critical(corr, seed):
    rng=np.random.default_rng(seed)
    draws=rng.multivariate_normal(
        mean=np.zeros(corr.shape[0]),cov=corr,size=GAUSSIAN_DRAWS,
        check_valid="ignore",method="svd"
    )
    c_upper=float(np.quantile(draws.max(axis=1),.95))
    return c_upper


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data",required=True)
    ap.add_argument("--r0-outdir",required=True)
    ap.add_argument("--r01-outdir",required=True)
    ap.add_argument("--r1-source",required=True)
    ap.add_argument("--r1-outdir",required=True)
    ap.add_argument("--r12-outdir",required=True)
    ap.add_argument("--r1f-outdir",required=True)
    ap.add_argument("--outdir",required=True)
    ap.add_argument("--chunksize",type=int,default=500_000)
    args=ap.parse_args()

    data=Path(args.data).resolve()
    r0=Path(args.r0_outdir).resolve()
    r01=Path(args.r01_outdir).resolve()
    r1out=Path(args.r1_outdir).resolve()
    r12out=Path(args.r12_outdir).resolve()
    r1fout=Path(args.r1f_outdir).resolve()
    out=Path(args.outdir).resolve()
    out.mkdir(parents=True,exist_ok=True)
    (out/"domain_ratio_models").mkdir(exist_ok=True)

    print("R2-1 Verify frozen provenance...")
    r1,r1sha=load_r1_module(Path(args.r1_source).resolve())

    wpath=r1fout/"criteo_r1f_source_winners.csv"
    spath=r1fout/"criteo_r1f_source_selection.csv"
    if sha256_file(wpath)!=EXPECTED_R1F_WINNERS_SHA256:
        raise RuntimeError("R1F winner artifact hash mismatch")
    if sha256_file(spath)!=EXPECTED_R1F_SELECTION_SHA256:
        raise RuntimeError("R1F selection artifact hash mismatch")

    winners=pd.read_csv(wpath)
    frozen=r1.load_frozen_shift(r0,r01)

    pairwise_rows=[]
    bound_rows=[]
    classification_rows=[]
    ratio_rows=[]
    policy_rows=[]
    gate_rows=[]

    for sidx,(_,shift) in enumerate(frozen["shifts"].iterrows()):
        name=str(shift["label"])
        print(f"\\nR2-2 Adapt target policies and fit X-only domain ratio for {name}...")

        Xs,Is,Xt,It=collect_adaptation_and_domain_data(
            r1,data,frozen,shift,args.chunksize
        )

        domain_model,domain_n=fit_domain_ratio_model(r1,Xs,Is,Xt,It)
        joblib.dump(
            domain_model,
            out/"domain_ratio_models"/f"{name}_source_target_logit.joblib",
            compress=3,
        )

        bundles={
            m:joblib.load(r1out/"models"/name/f"{m}.joblib")
            for m in MODELS
        }
        propensity=joblib.load(
            r12out/"propensity_models"/f"{name}_propensity_logit.joblib"
        )
        outcome_bundle=bundles["T-HGB"]

        # Target-adaptive exact top-q rules, all constructed in memory.
        rules={}
        target_adapt_scores={}
        for m in MODELS:
            sc=r1.predict_tau(bundles[m],Xt.astype(np.float64,copy=False))
            target_adapt_scores[m]=sc
            for q in BUDGETS:
                rule=fit_exact_topq(r1,sc,It,q)
                rules[(m,q)]=rule
                policy_rows.append({
                    "scenario":name,"model":m,"budget":q,
                    "score_cut_hex":rule["score_cut_hex"],
                    "tie_u_cut_hex":rule["tie_u_cut_hex"],
                    "target_adapt_n":rule["target_adapt_n"],
                    "target_adapt_k":rule["target_adapt_k"],
                    "target_adapt_rate":rule["target_adapt_rate"],
                    "threshold_tie_count":rule["threshold_tie_count"],
                    "tie_selected_count":rule["tie_selected_count"],
                    "target_infer_rate":np.nan,
                })

        contrasts=make_contrasts(winners,name)
        K=len(contrasts)
        mt=Moments(K)
        ms=Moments(K)
        ms_oracle=Moments(K)

        n_source_total=n_target_total=0
        ratio_n=0
        ratio_sum=ratio_sq=0.0
        ratio_or_sum=ratio_or_sq=0.0
        log_ratio_sqerr=0.0
        ratio_cross=ratio_x=ratio_y=ratio_x2=ratio_y2=0.0
        prop_values=[]
        ratio_values=[]
        oracle_values=[]
        target_policy_counts={(m,q):0 for m in MODELS for q in BUDGETS}
        target_infer_n=0
        source_infer_n=0
        source_infer_events=0
        source_infer_treated=0

        # First get realized total source/target counts using already materialized sizes.
        # Xs is source_train (30% of source), Xt target_adapt (25% of target);
        # exact whole-pop counts are recovered in the inference stream below, but
        # ratio prior correction is virtually 1. For oracle ratio we use frozen
        # expected target share from R0 mechanism, hence source/target prior=1.
        # This is exact for null and within <0.1% for shifted mechanisms.
        prior_source_over_target=1.0

        print(f"R2-3 Stream SOURCE infer outcomes + TARGET infer X for {name}...")
        total=0
        usecols=FEATURES+["treatment","visit"]
        for ci,df in enumerate(pd.read_csv(data,compression="gzip",usecols=usecols,chunksize=args.chunksize)):
            n=len(df)
            idx=np.arange(total,total+n,dtype=np.uint64)
            X=df[FEATURES].to_numpy(np.float32,copy=False)
            z=r1.pc1_z(X.astype(np.float64,copy=False),frozen)
            pt=r1.p_target_from_z(z,shift)
            is_target=r1.splitmix64_uniform(idx,r1.MEMBERSHIP_SEED)<pt
            is_source=~is_target
            role=r1.splitmix64_uniform(idx,r1.ROLE_SEED)
            s_inf=is_source & (role>=.50)
            t_inf=is_target & (role>=.25)

            n_source_total += int(is_source.sum())
            n_target_total += int(is_target.sum())

            # TARGET component: X only. No target A/Y indexing.
            if np.any(t_inf):
                Xi=X[t_inf].astype(np.float64,copy=False)
                Ii=idx[t_inf]
                nt=len(Xi)
                target_infer_n += nt

                mu0=outcome_bundle["model0"].predict_proba(Xi)[:,1]
                mu1=outcome_bundle["model1"].predict_proba(Xi)[:,1]
                tau=mu1-mu0

                pol={}
                for m in MODELS:
                    sc=r1.predict_tau(bundles[m],Xi)
                    for q in BUDGETS:
                        pp=apply_rule(r1,sc,Ii,rules[(m,q)])
                        pol[(m,q)]=pp
                        target_policy_counts[(m,q)] += int(pp.sum())

                H=np.empty((nt,K),dtype=np.float64)
                for k,r in contrasts.iterrows():
                    q=float(r.budget)
                    H[:,k]=(
                        pol[(r.competitor,q)].astype(np.float64)
                        -pol[(r.source_winner,q)].astype(np.float64)
                    )
                mt.update(H*tau[:,None])

            # SOURCE residual component: source-infer A/Y only.
            if np.any(s_inf):
                Xi=X[s_inf].astype(np.float64,copy=False)
                Ii=idx[s_inf]
                ai=df["treatment"].to_numpy(np.float32,copy=False)[s_inf].astype(np.float64)
                yi=df["visit"].to_numpy(np.float32,copy=False)[s_inf].astype(np.float64)
                ns=len(Xi)
                source_infer_n += ns
                source_infer_events += int(yi.sum())
                source_infer_treated += int(ai.sum())

                e=np.clip(propensity.predict_proba(Xi)[:,1],.02,.98)
                rh=ratio_predict(domain_model,Xi)
                # Oracle membership mechanism, prior approximately one.
                ro=(pt[s_inf]/(1-pt[s_inf]))*prior_source_over_target

                mu0=outcome_bundle["model0"].predict_proba(Xi)[:,1]
                mu1=outcome_bundle["model1"].predict_proba(Xi)[:,1]
                resid=(
                    ai/e*(yi-mu1)
                    -(1-ai)/(1-e)*(yi-mu0)
                )

                pol={}
                for m in MODELS:
                    sc=r1.predict_tau(bundles[m],Xi)
                    for q in BUDGETS:
                        pol[(m,q)]=apply_rule(r1,sc,Ii,rules[(m,q)])

                H=np.empty((ns,K),dtype=np.float64)
                for k,r in contrasts.iterrows():
                    q=float(r.budget)
                    H[:,k]=(
                        pol[(r.competitor,q)].astype(np.float64)
                        -pol[(r.source_winner,q)].astype(np.float64)
                    )

                ms.update(H*(rh*resid)[:,None])
                ms_oracle.update(H*(ro*resid)[:,None])

                ratio_n += ns
                ratio_sum += float(rh.sum())
                ratio_sq += float(np.sum(rh*rh))
                ratio_or_sum += float(ro.sum())
                ratio_or_sq += float(np.sum(ro*ro))
                lr=np.log(np.maximum(rh,1e-12))-np.log(np.maximum(ro,1e-12))
                log_ratio_sqerr += float(np.sum(lr*lr))

                # Lightweight tail diagnostics.
                ratio_values.append(rh.astype(np.float32))
                oracle_values.append(ro.astype(np.float32))
                prop_values.append(e.astype(np.float32))

            total += n
            print(f"  [infer {name}] chunk={ci+1} rows={total:,}")

        # Correct the oracle source/target prior using realized full population counts.
        # We accumulated oracle moments using prior 1.0. Recompute its exact scaling
        # analytically because all source oracle residual contributions are linear in r.
        realized_prior=n_source_total/n_target_total
        # m_oracle sum and cross scale by c and c^2.
        ms_oracle.sum *= realized_prior
        ms_oracle.cross *= realized_prior**2

        # Estimated primary contrasts.
        delta=mt.mean()+ms.mean()
        cov=mt.covariance_of_mean()+ms.covariance_of_mean()
        se,corr,min_eig=stabilize_corr(cov)
        crit=gaussian_critical(corr,GAUSSIAN_SEED_BASE+sidx)
        upper=delta+crit*se
        lower=delta-crit*se

        # Oracle-ratio sensitivity.
        delta_or=mt.mean()+ms_oracle.mean()
        cov_or=mt.covariance_of_mean()+ms_oracle.covariance_of_mean()
        se_or,corr_or,min_eig_or=stabilize_corr(cov_or)
        crit_or=gaussian_critical(corr_or,GAUSSIAN_SEED_BASE+100+sidx)
        upper_or=delta_or+crit_or*se_or

        for k,r in contrasts.iterrows():
            pairwise_rows.append({
                "scenario":name,
                "budget":float(r.budget),
                "source_winner":r.source_winner,
                "competitor":r.competitor,
                "contrast":r.contrast,
                "delta_hat":float(delta[k]),
                "se_hat":float(se[k]),
                "lower_95_one_sided_family":float(lower[k]),
                "upper_95_one_sided_family":float(upper[k]),
                "gaussian_critical":crit,
                "oracle_ratio_delta_hat":float(delta_or[k]),
                "oracle_ratio_se_hat":float(se_or[k]),
                "oracle_ratio_upper_95_one_sided_family":float(upper_or[k]),
                "oracle_ratio_critical":crit_or,
            })

        pairtemp=pd.DataFrame([
            rr for rr in pairwise_rows if rr["scenario"]==name
        ])

        for q in BUDGETS:
            g=pairtemp[np.isclose(pairtemp.budget,q)]
            point_regret=max(0.0,float(g.delta_hat.max()))
            bu=max(0.0,float(g.upper_95_one_sided_family.max()))
            bl=max(0.0,float(g.lower_95_one_sided_family.max()))
            bu_or=max(0.0,float(g.oracle_ratio_upper_95_one_sided_family.max()))
            sw=g.iloc[0].source_winner
            bound_rows.append({
                "scenario":name,"budget":q,"source_winner":sw,
                "point_target_regret_hat":point_regret,
                "asymptotic_upper_regret_bound_95":bu,
                "directional_lower_regret_bound_95":bl,
                "oracle_ratio_upper_regret_bound_95":bu_or,
                "estimated_minus_oracle_upper_bound":bu-bu_or,
            })
            for eps in EPSILON_GRID:
                if bu <= eps:
                    status="PORTABLE_AT_TOLERANCE"
                elif bl > eps:
                    status="EVIDENCE_OF_NON_PORTABILITY"
                else:
                    status="UNCERTAIN"
                classification_rows.append({
                    "scenario":name,"budget":q,"source_winner":sw,
                    "epsilon":eps,"status":status,
                    "upper_regret_bound":bu,
                    "lower_regret_bound":bl,
                })

        # Fill target-infer policy rates into the previously appended rows.
        for row in policy_rows:
            if row["scenario"]==name:
                key=(row["model"],row["budget"])
                row["target_infer_rate"]=target_policy_counts[key]/target_infer_n
                row["target_infer_abs_budget_deviation"]=abs(
                    row["target_infer_rate"]-row["budget"]
                )

        rv=np.concatenate(ratio_values).astype(np.float64)
        rov=np.concatenate(oracle_values).astype(np.float64)
        ev=np.concatenate(prop_values).astype(np.float64)
        ess_hat=(ratio_sum*ratio_sum)/(ratio_n*ratio_sq)
        ess_or=(ratio_or_sum*ratio_or_sum)/(ratio_n*ratio_or_sq)
        logrmse=math.sqrt(log_ratio_sqerr/ratio_n)

        ratio_rows.append({
            "scenario":name,
            "domain_fit_n_per_class":domain_n,
            "source_total":n_source_total,
            "target_total":n_target_total,
            "source_infer_n":source_infer_n,
            "target_infer_n":target_infer_n,
            "source_infer_visit_events":source_infer_events,
            "source_infer_treatment_rate":source_infer_treated/source_infer_n,
            "estimated_ratio_mean_source":ratio_sum/ratio_n,
            "estimated_ratio_ess":ess_hat,
            "oracle_ratio_ess_unscaled":ess_or,
            "ratio_log_rmse_vs_oracle":logrmse,
            "estimated_ratio_p99":float(np.quantile(rv,.99)),
            "estimated_ratio_p999":float(np.quantile(rv,.999)),
            "estimated_ratio_max":float(rv.max()),
            "oracle_ratio_p999":float(np.quantile(rov,.999)),
            "propensity_p001_source_infer":float(np.quantile(ev,.001)),
            "propensity_p999_source_infer":float(np.quantile(ev,.999)),
            "covariance_min_corr_eigenvalue":min_eig,
            "oracle_covariance_min_corr_eigenvalue":min_eig_or,
            "gaussian_critical":crit,
        })

        scenpol=pd.DataFrame([
            r for r in policy_rows if r["scenario"]==name
        ])
        gate_rows.append({
            "scenario":name,
            "all_target_adapt_discrete_topq_exact":bool(np.all([
                abs(
                    rr["target_adapt_rate"]
                    -rr["target_adapt_k"]/rr["target_adapt_n"]
                ) <= 1e-15
                for rr in policy_rows if rr["scenario"]==name
            ])),
            "all_target_infer_policy_rates_within_005":bool(
                np.all(scenpol.target_infer_abs_budget_deviation <= .005)
            ),
            "estimated_ratio_ess_within_05_of_design":bool(
                abs(ess_hat-float(shift["target_ess"])) <= .05
            ),
            "estimated_ratio_p999_pass_le_6":bool(np.quantile(rv,.999)<=6.0),
            "source_propensity_overlap_pass":bool(
                np.quantile(ev,.001)>=.05 and np.quantile(ev,.999)<=.98
            ),
            "all_15_contrasts_finite":bool(
                np.all(np.isfinite(delta)) and np.all(np.isfinite(se))
            ),
            "correlation_psd_numeric_pass":bool(min_eig>=-1e-8),
            "target_treatment_outcomes_used":False,
            "source_infer_outcomes_used":True,
        })

        del Xs,Is,Xt,It,bundles,propensity,domain_model

    pairwise=pd.DataFrame(pairwise_rows)
    bounds=pd.DataFrame(bound_rows)
    classes=pd.DataFrame(classification_rows)
    ratios=pd.DataFrame(ratio_rows)
    policies=pd.DataFrame(policy_rows)
    gates=pd.DataFrame(gate_rows)

    pairwise.to_csv(out/"criteo_r2_pairwise_contrasts.csv",index=False)
    bounds.to_csv(out/"criteo_r2_portability_bounds.csv",index=False)
    classes.to_csv(out/"criteo_r2_tolerance_frontier.csv",index=False)
    ratios.to_csv(out/"criteo_r2_ratio_inference_audit.csv",index=False)
    policies.to_csv(out/"criteo_r2_target_policy_rules.csv",index=False)
    gates.to_csv(out/"criteo_r2_gate.csv",index=False)

    substantive_cols=[
        "all_target_adapt_discrete_topq_exact",
        "all_target_infer_policy_rates_within_005",
        "estimated_ratio_ess_within_05_of_design",
        "estimated_ratio_p999_pass_le_6",
        "source_propensity_overlap_pass",
        "all_15_contrasts_finite",
        "correlation_psd_numeric_pass",
    ]
    summary={
        "stage":"Criteo R2 Target-Outcome-Blind Portability Assessment",
        "r1_source_sha256":r1sha,
        "r1f_winner_sha256":EXPECTED_R1F_WINNERS_SHA256,
        "r1f_selection_sha256":EXPECTED_R1F_SELECTION_SHA256,
        "primary_inference":"estimated source-to-target density ratio + transported DR + one-sided Gaussian max-t upper family",
        "ratio_sensitivity":"oracle emulated-membership ratio, outcomes still hidden",
        "epsilon_grid":list(EPSILON_GRID),
        "target_treatment_outcomes_used":False,
        "source_infer_outcomes_used":True,
        "all_technical_gates_pass":bool(gates[substantive_cols].all(axis=None)),
        "r12_strict_propensity_gate":"FAIL remains permanent",
        "criteo_role":"secondary large-scale real-data application/benchmark",
        "next_if_pass":"Freeze R2 results, then R3 unlock target treatment/outcomes solely for benchmark evaluation.",
    }
    (out/"criteo_r2_summary.json").write_text(
        json.dumps(summary,indent=2),encoding="utf-8"
    )

    print("\\n=== R2 PORTABILITY BOUNDS ===")
    print(bounds.to_string(index=False))
    print("\\n=== R2 TOLERANCE FRONTIER ===")
    print(classes.to_string(index=False))
    print("\\n=== R2 RATIO/INFERENCE AUDIT ===")
    print(ratios.to_string(index=False))
    print("\\n=== R2 GATE ===")
    print(gates.to_string(index=False))
    print("\\nSummary:",summary)
    print("\\nFinished. Results:",out)


if __name__=="__main__":
    main()
