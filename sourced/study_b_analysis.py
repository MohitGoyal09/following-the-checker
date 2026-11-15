"""Study B tests exactly as preregistered (Amendments 3 and 5).

Usage: uv run python -m sourced.study_b_analysis -> results/study_b.json, results/fig_study_b.png
Per model: exact two-sided McNemar tests on paired reliance, Holm correction across the 4 tests.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.multitest import multipletests

IN = Path("data/processed/study_b_responses.csv")
OUT = Path("results")
TESTS = {  # name: (truth, condition_x, condition_y)
    "H4' label vs none (unsupported)": ("unsupported", "a", "b"),
    "H5a' correct tool vs label (unsupported)": ("unsupported", "b", "c"),
    "H5b' wrong 'supported' tool vs label (unsupported)": ("unsupported", "b", "d"),
    "H5c' wrong 'unsupported' tool vs label (supported)": ("supported", "b", "d"),
}


def indices(d: pd.DataFrame, conds: tuple[str, str]) -> tuple[float, float]:
    """Amendment 6. conds = (signal-correct, signal-wrong). F = signal-following, T = support-tracking."""
    s = d[d.condition.isin(conds)]
    sig = (s.truth == "supported") == (s.condition == conds[0])
    f = s.rely[sig].mean() - s.rely[~sig].mean()
    t = s.rely[s.truth == "supported"].mean() - s.rely[s.truth == "unsupported"].mean()
    return float(f), float(t)


def evidence_test(dm: pd.DataFrame, n_boot: int = 10_000, seed: int = 42, cluster: str = "noteId") -> dict:
    """H8 (T up with evidence) and H9 (F down with evidence): paired bootstrap over items (or another cluster)."""
    rng = np.random.default_rng(seed)
    f0, t0 = indices(dm, ("c", "d"))
    f1, t1 = indices(dm, ("e", "f"))
    by_note = {n: g for n, g in dm.groupby(cluster)}
    ids = np.array(list(by_note))
    diffs = []
    for _ in range(n_boot):
        sample = pd.concat([by_note[n] for n in rng.choice(ids, size=len(ids), replace=True)])
        a0, b0 = indices(sample, ("c", "d"))
        a1, b1 = indices(sample, ("e", "f"))
        diffs.append((a1 - a0, b1 - b0))
    diffs = np.array(diffs)
    out = {}
    for k, (name, obs) in enumerate((("H9 signal-following F (e,f minus c,d)", f1 - f0),
                                     ("H8 support-tracking T (e,f minus c,d)", t1 - t0))):
        col = diffs[:, k]
        p = 2 * min((col <= 0).mean(), (col >= 0).mean())
        out[name] = {"observed": float(obs), "ci95": [float(np.percentile(col, 2.5)), float(np.percentile(col, 97.5))],
                     "p_boot": float(min(1.0, p))}
    out["values"] = {"F_cd": f0, "T_cd": t0, "F_ef": f1, "T_ef": t1}
    return out


def paired_test(d: pd.DataFrame, truth: str, x: str, y: str) -> dict:
    w = d[d.truth == truth].pivot_table(index="noteId", columns="condition", values="rely", aggfunc="first")
    a, b = w[x].astype(bool), w[y].astype(bool)
    table = [[int((a & b).sum()), int((a & ~b).sum())], [int((~a & b).sum()), int((~a & ~b).sum())]]
    res = mcnemar(table, exact=True)
    return {"n_pairs": int(len(w)), f"rely_{x}": float(a.mean()), f"rely_{y}": float(b.mean()),
            "diff_y_minus_x": float(b.mean() - a.mean()), "discordant_x_only": table[0][1],
            "discordant_y_only": table[1][0], "p_exact": float(res.pvalue)}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    d = pd.read_csv(IN, dtype={"noteId": str})
    d = d[~d.fallback.fillna(False).astype(bool) & d.condition.isin(list("abcdef"))]  # g, h: sourced/study_b_amend8.py
    rates = (d.groupby(["model", "truth", "condition"]).rely.mean().unstack("condition").round(3))
    result = {"reliance_rates": {m: rates.loc[m].to_dict(orient="index") for m in rates.index.levels[0]}, "tests": {}}
    for model, dm in d.groupby("model"):
        tests = {name: paired_test(dm, *spec) for name, spec in TESTS.items()}
        reject, p_holm, _, _ = multipletests([t["p_exact"] for t in tests.values()], method="holm")
        for (name, t), ph, rj in zip(tests.items(), p_holm, reject):
            t["p_holm"], t["reject_0.05"] = float(ph), bool(rj)
        result["tests"][model] = tests
        if {"e", "f"} <= set(dm.condition):
            ev = evidence_test(dm)
            names = [k for k in ev if k.startswith("H")]
            rej, ph, _, _ = multipletests([ev[k]["p_boot"] for k in names], method="holm")
            for k, p, r in zip(names, ph, rej):
                ev[k]["p_holm"], ev[k]["reject_0.05"] = float(p), bool(r)
            ev["secondary_f_vs_d"] = {t: paired_test(dm, t, "d", "f") for t in ("supported", "unsupported")}
            result.setdefault("evidence_arm", {})[model] = ev
    (OUT / "study_b.json").write_text(json.dumps(result, indent=2))
    plot(rates, OUT / "fig_study_b.png")
    if "evidence_arm" in result:
        plot_indices(result["evidence_arm"], OUT / "fig_headline_obeyed_not_evaluated.png")
        for model, ev in result["evidence_arm"].items():
            v = ev["values"]
            print(f"\n{model}: F {v['F_cd']:+.3f} -> {v['F_ef']:+.3f} | T {v['T_cd']:+.3f} -> {v['T_ef']:+.3f}")
            for k in (k for k in ev if k.startswith("H")):
                print(f"  {k}: {ev[k]['observed']:+.3f} CI {ev[k]['ci95'][0]:+.3f}..{ev[k]['ci95'][1]:+.3f} "
                      f"p_holm {ev[k]['p_holm']:.4f}")
    print(rates.to_string())
    for model, tests in result["tests"].items():
        print(f"\n{model}")
        for name, t in tests.items():
            print(f"  {name}: diff {t['diff_y_minus_x']:+.3f}  p_holm {t['p_holm']:.4f}  {'*' if t['reject_0.05'] else ''}")


def plot(rates: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = {"a": "No label", "b": "Helpful\nlabel", "c": "+ correct\ncheck", "d": "+ wrong\ncheck",
             "e": "+ correct check\n+ passage", "f": "+ wrong check\n+ passage"}
    conds = [c for c in "abcdef" if c in rates.columns]
    models = list(rates.index.levels[0])
    fig, axes = plt.subplots(1, len(models), figsize=(13, 3.9), sharey=True)
    for ax, m in zip(axes, models):
        for truth, color in (("supported", "#2f7d4f"), ("unsupported", "#b24a3a")):
            ys = [rates.loc[(m, truth), c] * 100 for c in conds]
            ax.plot(range(len(conds)), ys, marker="o", color=color, lw=2, label=f"{truth} notes")
        ax.set_xticks(range(len(conds)), [names[c] for c in conds], fontsize=7)
        ax.set_title(m, fontsize=10)
        ax.set_ylim(0, 100)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("% of answers relying on the note")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Study B: reliance on Helpful-labelled notes, by condition and real support", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=200)


def plot_indices(ev: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    models = list(ev)
    x = np.arange(len(models))
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    for ax, (key, title) in zip(axes, (("F", "Follows the checker (F)"), ("T", "Tracks real support (T)"))):
        no = [ev[m]["values"][f"{key}_cd"] * 100 for m in models]
        yes = [ev[m]["values"][f"{key}_ef"] * 100 for m in models]
        ax.bar(x - 0.18, no, 0.36, color="#9a9a94", label="verdict only")
        ax.bar(x + 0.18, yes, 0.36, color="#2f5d8a", label="verdict + checked passage")
        ax.axhline(0, color="#555", lw=0.8)
        ax.set_xticks(x, models, fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("percentage-point difference in reliance")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Does the reader follow the checker (F) or the real support (T)?", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=200)


if __name__ == "__main__":
    main()
