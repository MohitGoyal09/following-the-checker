"""Report figures (vector PDF + PNG) from committed results and data. No model calls.

Usage: uv run python paper/make_figures.py -> paper/figures/fig{1,2,3}_*.{pdf,png}
Sources: results/study_a.json, results/review_fixes.json, results/gold.json, data/processed/study_b_responses.csv.
Okabe-Ito colours, with marker/line style as a second cue.
"""

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from statsmodels.stats.proportion import proportion_confint

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "figures"
MODELS = {"claude-haiku-5-5": "Haiku 5.5", "claude-opus-5-5": "Opus 5.5", "gemini-3.8-flash": "Gemini 3.8 Flash"}
OI = {"orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73", "blue": "#0072B2", "verm": "#D55E00",
      "purple": "#CC79A7", "grey": "#7F7F7F", "black": "#000000"}
N_BOOT, SEED = 2_000, 42
mpl.rcParams.update({"font.family": "Helvetica", "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
                     "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7, "axes.spines.top": False,
                     "axes.spines.right": False, "pdf.fonttype": 42, "savefig.dpi": 300})


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{ext}", facecolor="white")
    plt.close(fig)


# ---------- Figure 1: design ----------
def box(ax, x, y, w, h, text, fc="#FFFFFF", ec="#333333", size=6.6, weight="normal"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.008,rounding_size=0.012", fc=fc, ec=ec, lw=0.8))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, weight=weight, wrap=True)


def arrow(ax, x0, y0, x1, y1, color="#333333"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=8, lw=0.9, color=color))


def fig_design() -> None:
    fig = plt.figure(figsize=(6.6, 2.85))
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set(xlim=(-0.012, 1.012), ylim=(0.0, 1.0)); ax.axis("off")
    # Panel A: gates
    ax.text(0.0, 0.975, "A  Community Notes checks that a note looks sourced", fontsize=8.5, weight="bold", va="top")
    y, h, w = 0.71, 0.19, 0.178
    xs = [0.0, 0.205, 0.41, 0.615, 0.822]
    labels = ["Note with\ncited links", "Gate 1\nlinks load\n(AI writers: ≥95%)", "Gate 2\nraters tick \"cites\nhigh-quality sources\"",
              "Gate 3\n\"Rated helpful\" label", "Readers,\nincl. AI agents"]
    fills = ["#FFFFFF", "#F2F2F2", "#F2F2F2", "#F2F2F2", "#FFFFFF"]
    for x, lab, fc in zip(xs, labels, fills):
        box(ax, x, y, w, h, lab, fc=fc)
    for a, b in zip(xs[:-1], xs[1:]):
        arrow(ax, a + w + 0.004, y + h / 2, b - 0.004, y + h / 2)
    ax.annotate("", xy=(0.205, 0.675), xytext=(0.793, 0.675),
                arrowprops=dict(arrowstyle="-", lw=0.8, color=OI["blue"], linestyle=(0, (3, 2))))
    ax.text(0.5, 0.655, "Study A opens each cited page: does it support the note's claim?\n"
            "200 paired AI/human Helpful notes + 100 Not Helpful; 2 LLM judges; human labels",
            ha="center", va="top", fontsize=6.8, color=OI["blue"])
    # Panel B: Study B
    ax.text(0.0, 0.53, "B  Study B: what does an AI reader do with a source-check verdict?", fontsize=8.5, weight="bold", va="top")
    yb, hb = 0.07, 0.38
    box(ax, 0.0, yb + 0.20, 0.16, 0.19, "Community Note\n+ \"Rated helpful\"\nlabel", fc="#FFFFFF")
    box(ax, 0.19, yb + 0.20, 0.205, 0.19, "Source-check verdict:\n\"the cited sources DO /\nDO NOT support the claim\"", fc="#FFF4D6", ec=OI["orange"])
    box(ax, 0.43, yb + 0.20, 0.19, 0.19, "Passage the tool\nchecked (≤1,200 chars)", fc="#E3F1FB", ec=OI["sky"])
    ax.text(0.2925, yb + 0.165, "right (c, e)  or  wrong (d, f, h)", ha="center", va="top", fontsize=6.8)
    ax.text(0.525, yb + 0.165, "none (c, d) · real (e, f)\nunrelated placebo (h)", ha="center", va="top", fontsize=6.8)
    box(ax, 0.66, yb + 0.20, 0.15, 0.19, "AI reader:\nOpus 5.5, Haiku 5.5,\nGemini 3.8 Flash", fc="#FFFFFF")
    box(ax, 0.845, yb + 0.20, 0.155, 0.19, "\"Is the claim true?\"\nyes / unsure / no\n+ confidence", fc="#FFFFFF")
    for a, b in ((0.16, 0.19), (0.395, 0.43), (0.62, 0.66), (0.81, 0.845)):
        arrow(ax, a + 0.004, yb + 0.295, b - 0.004, yb + 0.295)
    ax.text(0.0, yb - 0.02, "Conditions: (a) note only, (b) + label, (c)–(f) + verdict ± passage, (g) claim only, (h) wrong verdict + unrelated passage.\n"
            "80 Helpful notes (40 supported, 40 unsupported) × 8 conditions × 3 readers = 1,920 answers.  Reliance = answering \"yes\".",
            fontsize=6.6, va="bottom", color="#333333")
    save(fig, "fig1_design")


# ---------- Figure 2: Study B ----------
def ft(s: pd.DataFrame, conds: tuple[str, str]) -> tuple[float, float]:
    s = s[s.condition.isin(conds)]
    sig = (s.truth == "supported") == (s.condition == conds[0])
    return s.rely[sig].mean() - s.rely[~sig].mean(), s.rely[s.truth == "supported"].mean() - s.rely[s.truth == "unsupported"].mean()


def ft_with_ci(dm: pd.DataFrame) -> dict:
    by = {n: g for n, g in dm.groupby("noteId")}
    ids = np.array(list(by))
    rng = np.random.default_rng(SEED)
    pt = {k: ft(dm, c) for k, c in (("cd", ("c", "d")), ("ef", ("e", "f")))}
    boots = {"cd": [], "ef": []}
    for _ in range(N_BOOT):
        smp = pd.concat([by[n] for n in rng.choice(ids, len(ids))])
        for k, c in (("cd", ("c", "d")), ("ef", ("e", "f"))):
            boots[k].append(ft(smp, c))
    return {k: (pt[k], np.percentile(np.array(boots[k]), [2.5, 97.5], axis=0)) for k in pt}


def fig_study_b() -> None:
    d = pd.read_csv(ROOT / "data/processed/study_b_responses.csv", dtype={"noteId": str})
    d = d[~d.fallback.fillna(False).astype(bool)]
    rf = json.loads((ROOT / "results/review_fixes.json").read_text())
    fig, axs = plt.subplots(2, 2, figsize=(6.6, 4.2), layout="constrained")
    ypos = np.arange(3)[::-1]
    for col, (name, idx) in enumerate((("F: follows the verdict", 0), ("T: tracks real support", 1))):
        ax = axs[0, col]
        for y, (m, lab) in zip(ypos, MODELS.items()):
            r = ft_with_ci(d[d.model == m])
            (p0, c0), (p1, c1) = r["cd"], r["ef"]
            v0, v1 = 100 * p0[idx], 100 * p1[idx]
            ax.plot([v0, v1], [y, y], color="#BBBBBB", lw=1.2, zorder=1)
            ax.errorbar(v0, y + 0.12, xerr=[[v0 - 100 * c0[0, idx]], [100 * c0[1, idx] - v0]], fmt="o", ms=5,
                        color=OI["orange"], mfc="white", mew=1.4, capsize=2, lw=0.9, label="verdict only (c, d)" if y == 2 else None)
            ax.errorbar(v1, y - 0.12, xerr=[[v1 - 100 * c1[0, idx]], [100 * c1[1, idx] - v1]], fmt="s", ms=4.5,
                        color=OI["blue"], capsize=2, lw=0.9, label="+ checked passage (e, f)" if y == 2 else None)
        ax.axvline(0, color="#666666", lw=0.6)
        ax.set(yticks=ypos, yticklabels=list(MODELS.values()), xlim=(-25, 85), ylim=(-1.05, 2.4),
               xlabel="percentage points", title=f"{'AB'[col]}  {name}")
        ax.title.set_ha("left"); ax.title.set_x(0.0)
    axs[0, 0].legend(loc="lower right", frameon=False, ncol=2, handletextpad=0.3, columnspacing=0.8)
    # C: accuracy
    ax = axs[1, 0]
    conds = [("b", "no tool\n(b)"), ("c", "right\n(c)"), ("d", "wrong\n(d)"), ("e", "right\n+ passage\n(e)"), ("f", "wrong\n+ passage\n(f)")]
    x = np.arange(len(conds))
    for k, (m, lab), mk, colr in zip(range(3), MODELS.items(), ("o", "s", "^"), (OI["verm"], OI["blue"], OI["green"])):
        dm = d[d.model == m]
        correct = np.where(dm.truth == "supported", dm.answer == "yes", dm.answer != "yes")
        acc = pd.Series(correct, index=dm.index).groupby(dm.condition)
        vals = [100 * acc.mean()[c] for c, _ in conds]
        ci = [proportion_confint(int(acc.sum()[c]), int(acc.size()[c]), method="wilson") for c, _ in conds]
        ax.errorbar(x + (k - 1) * 0.16, vals, yerr=[[v - 100 * lo for v, (lo, hi) in zip(vals, ci)], [100 * hi - v for v, (lo, hi) in zip(vals, ci)]],
                    fmt=mk, ms=4, color=colr, capsize=1.5, lw=0.8, label=lab)
    ax.axhline(50, color="#999999", lw=0.6, ls=":")
    ax.set(xticks=x, ylim=(0, 100), ylabel="reader accuracy (%)", title="C  Accuracy against source support")
    ax.set_xticklabels([c[1] for c in conds], fontsize=6.6)
    ax.title.set_ha("left"); ax.title.set_x(0.0)
    ax.legend(loc="lower left", frameon=False, ncol=3, handletextpad=0.2, columnspacing=0.8)
    # D: placebo
    ax = axs[1, 1]
    for y, (m, lab) in zip(ypos, MODELS.items()):
        for off, truth, colr, mk, tl in ((0.12, "supported", OI["purple"], "D", "false alarm (supported notes)"),
                                         (-0.12, "unsupported", OI["grey"], "o", "false assurance (unsupported notes)")):
            r = rf["placebo_h_minus_f"][f"{m}|{truth}"]
            v, (lo, hi) = 100 * r["h_minus_f"], (100 * r["ci95"][0], 100 * r["ci95"][1])
            ax.errorbar(v, y + off, xerr=[[v - lo], [hi - v]], fmt=mk, ms=4, color=colr, capsize=2, lw=0.9,
                        label=tl if y == 2 else None)
    ax.axvline(0, color="#666666", lw=0.6)
    ax.set(yticks=ypos, yticklabels=list(MODELS.values()), xlim=(-45, 30), ylim=(-1.15, 2.4),
           xlabel="unrelated − real passage, reliance (pp)", title="D  Placebo passage, wrong verdict")
    ax.title.set_ha("left"); ax.title.set_x(0.0)
    ax.legend(loc="lower center", frameon=False, ncol=1, handletextpad=0.3)
    save(fig, "fig2_study_b")


# ---------- Figure 3: Study A ----------
def fig_study_a() -> None:
    a = json.loads((ROOT / "results/study_a.json").read_text())["judges"]
    fig, ax = plt.subplots(figsize=(6.6, 1.55), layout="constrained")
    rows = [("Gate 1: link loads (now or archived)", "gate1_live_pass"), ("Gate 2: helpful ratings tick \"good sources\"", "gate2_good_sources_tag"),
            ("Checked: page supports the claim (Claude judge)", "checked_support")]
    ys = np.arange(len(rows))[::-1]
    for w, off, colr, mk, lab in (("ai", 0.13, OI["verm"], "o", "AI notes"), ("human", -0.13, OI["blue"], "s", "human notes")):
        for y, (_, key) in zip(ys[:3], rows):
            r = a["claude-opus-5-5"]["C2"][w][key]
            v, lo, hi = (100 * r["est"], 100 * r["ci95"][0], 100 * r["ci95"][1])
            ax.errorbar(v, y + off, xerr=[[v - lo], [hi - v]], fmt=mk, ms=4.5, color=colr, capsize=2, lw=0.9, label=lab if y == ys[0] else None)
    ax.set(yticks=ys, yticklabels=[r[0] for r in rows],
           xlim=(0, 100), xlabel="% (95% interval)")
    ax.legend(loc="lower right", frameon=False)
    save(fig, "fig3_study_a")


if __name__ == "__main__":
    fig_design()
    fig_study_b()
    fig_study_a()
    print("figures ->", OUT)
