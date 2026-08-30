from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from pandas.testing import assert_frame_equal

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "outputs"
RUN = ROOT / "reproduction_runs" / "manuscript_assets"
FIG = RUN / "figures"
TAB = RUN / "tables"
FIG.mkdir(parents=True, exist_ok=True)
TAB.mkdir(parents=True, exist_ok=True)


def _normalize_text_line_endings(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize CRLF/CR embedded inside string cells to LF for semantic comparison."""
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].map(
                lambda x: x.replace("\r\n", "\n").replace("\r", "\n")
                if isinstance(x, str) else x
            )
    return out


def reproduce_simulation_figure():
    df = pd.read_csv(FROZEN / "simulation" / "rare_binary_operating_characteristics.csv")
    core = df[df["regime"] == "core"].copy()
    core["label"] = core.apply(
        lambda r: f"{int(r.source_n/1000)}k/{r.design_ess:g}/{r.separation}", axis=1
    )
    fig, ax = plt.subplots(figsize=(11, 5.5))
    x = range(len(core))
    ax.plot(x, core["contrast_upper_coverage"], marker="o",
            label="Contrast upper coverage")
    ax.plot(x, core["all_budget_regret_bound_coverage"], marker="s",
            label="All-budget regret-bound coverage")
    ax.axhline(0.95, linestyle="--", linewidth=1, label="0.95 reference")
    ax.set_xticks(list(x))
    ax.set_xticklabels(core["label"], rotation=45, ha="right")
    ax.set_ylim(0.88, 1.01)
    ax.set_ylabel("Empirical coverage")
    ax.set_xlabel("Source n / design ESS / policy separation")
    ax.set_title("Finite-Sample Operating Boundary in Rare-Binary Simulations")
    ax.legend()
    fig.tight_layout()
    out = FIG / "figure2_simulation_operating_boundary.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def reproduce_criteo_assets():
    bounds = pd.read_csv(FROZEN / "criteo" / "r2_budget_bounds.csv")
    bench = pd.read_csv(FROZEN / "criteo" / "r3_budget_benchmark.csv")
    df = bounds.merge(
        bench,
        on=["scenario", "budget", "source_selected_model"],
        validate="one_to_one",
    )

    shift = {
        "null_ess1.0": "No shift",
        "pc1_ess0.8": "Moderate",
        "pc1_ess0.5": "Stronger",
    }
    df["label"] = df.apply(
        lambda r: f"{shift[r.scenario]}\nq={r.budget:g}", axis=1
    )

    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    x = range(len(df))
    ax.plot(x, df["upper_regret_bound"], marker="o",
            label="Frozen outcome-blind upper regret bound")
    ax.plot(x, df["benchmark_point_regret"], marker="s",
            label="Held-out AIPW benchmark point regret")
    ax.axhline(0.0005, linestyle="--", linewidth=1,
               label="Tolerance epsilon = 0.0005")
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["label"])
    ax.set_ylabel("Incremental visit-probability regret")
    ax.set_xlabel("Population-shift condition and treatment budget")
    ax.set_title("Outcome-Blind Portability Bounds and Held-Out Target Benchmark")
    ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    ax.legend()
    fig.tight_layout()
    fig_out = FIG / "figure3_criteo_portability_benchmark.png"
    fig.savefig(fig_out, dpi=300, bbox_inches="tight")
    plt.close(fig)

    table_out = TAB / "table4_criteo_portability_benchmark.csv"
    df.to_csv(table_out, index=False, lineterminator="\n")

    frozen_table = FROZEN / "tables" / "table4_criteo_portability_benchmark.csv"
    if frozen_table.is_file():
        old = _normalize_text_line_endings(pd.read_csv(frozen_table))
        new = _normalize_text_line_endings(pd.read_csv(table_out))
        assert_frame_equal(
            old,
            new,
            check_dtype=False,
            check_exact=False,
            rtol=1e-12,
            atol=1e-15,
        )
        print("Table IV semantic equality with frozen table: PASS")

    return fig_out, table_out


if __name__ == "__main__":
    f2 = reproduce_simulation_figure()
    f3, t4 = reproduce_criteo_assets()
    print("Manuscript assets regenerated under reproduction_runs/manuscript_assets.")
    print("Figure 2:", f2)
    print("Figure 3:", f3)
    print("Table IV:", t4)
