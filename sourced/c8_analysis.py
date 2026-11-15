"""C8 analysis exactly as preregistered in Amendment 4.

Usage: uv run python -m sourced.c8_analysis -> results/c8_tag_drift.json, results/fig_c8_tag_drift.png
Window Jan 2024 - Oct 2026; break at Sep 2025 (AI writers enter). Human-note series is the test;
AI-note series is shown descriptively. Segmented OLS with Newey-West (HAC, lag 3) errors.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

START, END, BREAK = "2024-01", "2026-10", "2025-09"
HAC_LAGS = 3
IN = Path("data/processed/tag_drift_monthly.csv")
OUT = Path("results")
SHARES = {  # name: (numerator, denominator)
    "good_sources": ("good_sources", "n_helpful"),
    "clear": ("clear", "n_helpful"),
    "unbiased": ("unbiased", "n_helpful"),
    "sources_missing": ("sources_missing", "n_not_helpful"),
    "incorrect": ("incorrect", "n_not_helpful"),
}


def segmented_fit(y: np.ndarray, break_index: int) -> dict:
    t = np.arange(len(y), dtype=float)
    post = (t >= break_index).astype(float)
    X = sm.add_constant(np.column_stack([t, post, (t - break_index) * post]))
    res = sm.OLS(np.asarray(y, float), X).fit(cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})
    ci = res.conf_int()
    return {
        "level_change": float(res.params[2]), "level_ci": [float(ci[2][0]), float(ci[2][1])],
        "level_p": float(res.pvalues[2]),
        "slope_change": float(res.params[3]), "slope_ci": [float(ci[3][0]), float(ci[3][1])],
        "slope_p": float(res.pvalues[3]),
        "pre_slope": float(res.params[1]), "n_months": int(len(y)),
    }


def shares(d: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({k: d[n] / d[den] for k, (n, den) in SHARES.items()}).assign(month=d.month.values)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    d = pd.read_csv(IN)
    d = d[(d.month >= START) & (d.month <= END)]
    human = shares(d[~d.ai].sort_values("month").reset_index(drop=True))
    ai = shares(d[d.ai].sort_values("month").reset_index(drop=True))
    b = int((human.month < BREAK).sum())
    fits = {k: segmented_fit(human[k].values, b) for k in SHARES}
    diffs = {f"good_sources_minus_{p}": segmented_fit((human.good_sources - human[p]).values, b)
             for p in ("clear", "unbiased")}
    target = fits["good_sources"]["level_change"]
    rule = all(target > fits[p]["level_change"] for p in ("clear", "unbiased"))
    result = {
        "window": [START, END], "break": BREAK, "hac_lags": HAC_LAGS, "pre_months": b,
        "human_note_fits": fits, "difference_fits": diffs,
        "reading_rule_source_specific": rule,
        "ai_note_series_mean": {k: float(ai[k].mean()) for k in SHARES},
        "human_post_mean": {k: float(human[k][b:].mean()) for k in SHARES},
    }
    (OUT / "c8_tag_drift.json").write_text(json.dumps(result, indent=2))
    plot(human, ai, OUT / "fig_c8_tag_drift.png")
    print(json.dumps({k: {x: round(v[x], 4) for x in ("level_change", "level_p", "slope_change", "slope_p")}
                      for k, v in {**fits, **diffs}.items()}, indent=1))
    print("source-specific by preregistered rule:", rule)


def plot(human: pd.DataFrame, ai: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4.2))
    styles = {"good_sources": ("#2f5d8a", "Cites high-quality sources (target)"),
              "clear": ("#9a9a94", "Clear (placebo)"), "unbiased": ("#c7a252", "Unbiased language (placebo)")}
    x = pd.to_datetime(human.month)
    for k, (c, lab) in styles.items():
        ax.plot(x, human[k] * 100, color=c, lw=2, label=f"Human notes: {lab}")
    ax.plot(pd.to_datetime(ai.month), ai.good_sources * 100, color="#2f5d8a", lw=1.5, ls="--",
            label="AI notes: cites high-quality sources")
    ax.axvline(pd.Timestamp(BREAK + "-01"), color="#555", lw=1, ls=":")
    ax.text(pd.Timestamp(BREAK + "-01"), ax.get_ylim()[1], " AI writers enter", va="top", fontsize=9, color="#555")
    ax.set_ylabel("% of helpful ratings with tag")
    ax.set_title("Source tag and placebo tags on helpful ratings, by month")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, frameon=False, loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=200)


if __name__ == "__main__":
    main()
