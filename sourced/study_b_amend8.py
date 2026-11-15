"""Amendment 8: placebo passage (H10, H11), claim-only prior (g), and human truth for Study B.

Usage: uv run python -m sourced.study_b_amend8 -> results/study_b_amend8.json
No model calls. Human truth is used only when both authors' studyb_labels_<author>.csv are in data/processed/gold/.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

from sourced.gold import AUTHORS
from sourced.study_b_analysis import paired_test

P = "data/processed/"
G = Path(P + "gold")
OUT = Path("results/study_b_amend8.json")
N_BOOT, SEED = 10_000, 42


def load() -> pd.DataFrame:
    d = pd.read_csv(P + "study_b_responses.csv", dtype={"noteId": str})
    d = d[~d.fallback.fillna(False).astype(bool)]
    # direction of the verdict shown, fixed by the judge truth used to build the stimuli
    says = np.where(d.condition.isin(["c", "e"]), d.truth == "supported",
                    np.where(d.condition.isin(["d", "f", "h"]), d.truth != "supported", np.nan))
    return d.assign(says_supported=says)


def placebo_tests(d: pd.DataFrame) -> dict:
    out = {}
    for model, dm in d.groupby("model"):
        res = {"H10_supported_f_vs_h": paired_test(dm, "supported", "f", "h"),
               "H11_unsupported_f_vs_h": paired_test(dm, "unsupported", "f", "h")}
        holm = multipletests([r["p_exact"] for r in res.values()], method="holm")[1]
        for r, p in zip(res.values(), holm):
            r["p_holm"] = round(float(p), 4)
        out[model] = res
    return out


def prior(d: pd.DataFrame) -> dict:
    out = {}
    for model, dm in d.groupby("model"):
        g = dm[dm.condition == "g"].set_index("noteId")
        rel = g.groupby("truth").rely.mean()
        f = dm[(dm.condition == "f") & (dm.truth == "unsupported")].set_index("noteId").rely
        split = f.groupby(g.rely.reindex(f.index).map({True: "prior_yes", False: "prior_not_yes"})).agg(["mean", "size"])
        out[model] = {"rely_g_by_truth": rel.round(3).to_dict(), "T_g": round(float(rel["supported"] - rel["unsupported"]), 3),
                      "answers_g": g.answer.value_counts().to_dict(),
                      "unsupported_rely_f_by_prior": {k: {"mean": round(float(v["mean"]), 3), "n": int(v["size"])}
                                                      for k, v in split.iterrows()}}
    return out


def human_truth() -> pd.Series | None:
    files = [G / f"studyb_labels_{w}.csv" for w in AUTHORS]
    if not all(f.exists() for f in files):
        return None
    lab = pd.concat([pd.read_csv(f) for f in files])
    key = pd.read_csv(G / "studyb_key.csv", dtype={"noteId": str}).merge(lab[["item", "label"]], on="item")
    gold = pd.read_csv(G / "gold_support.csv", dtype={"noteId": str}).rename(columns={"gold": "label"})
    items = pd.read_csv(P + "study_b_items.csv", dtype={"noteId": str})
    pages = pd.concat([key[["noteId", "label"]], gold[gold.noteId.isin(items.noteId)][["noteId", "label"]]])
    missing = set(items.noteId) - set(pages.noteId)
    if missing:
        raise SystemExit(f"Study B notes without any human page label: {sorted(missing)}")
    return pages.groupby("noteId").label.apply(lambda x: "supported" if (x == "supports").any() else "unsupported")


def ft(s: pd.DataFrame, conds: tuple[str, str], truth: str) -> tuple[float, float]:
    s = s[s.condition.isin(conds)]
    f = s.rely[s.says_supported == 1].mean() - s.rely[s.says_supported == 0].mean()
    t = s.rely[s[truth] == "supported"].mean() - s.rely[s[truth] == "unsupported"].mean()
    return float(f), float(t)


def with_human_truth(d: pd.DataFrame, h: pd.Series) -> dict:
    d = d.assign(truth_h=d.noteId.map(h))
    items = d.drop_duplicates("noteId")
    out = {"agreement_judge_vs_human": round(float((items.truth == items.truth_h).mean()), 3),
           "crosstab_judge_x_human": pd.crosstab(items.truth, items.truth_h).to_dict(orient="index"), "models": {}}
    rng = np.random.default_rng(SEED)
    for model, dm in d.groupby("model"):
        f0, t0 = ft(dm, ("c", "d"), "truth_h")
        f1, t1 = ft(dm, ("e", "f"), "truth_h")
        by = {n: g for n, g in dm.groupby("noteId")}
        ids = np.array(list(by))
        diffs = []
        for _ in range(N_BOOT):
            smp = pd.concat([by[n] for n in rng.choice(ids, len(ids))])
            diffs.append(ft(smp, ("e", "f"), "truth_h")[1] - ft(smp, ("c", "d"), "truth_h")[1])
        rel = dm[dm.condition.isin(["d", "f"])].groupby(["truth_h", "says_supported", "condition"]).rely.mean().round(3)
        wrong = dm[dm.condition.isin(["f", "h"]) & (dm.says_supported == (dm.truth_h != "supported"))]  # wrong verdict, human label
        ph = {"H10_supported_f_vs_h": paired_test(wrong.assign(truth=wrong.truth_h), "supported", "f", "h"),
              "H11_unsupported_f_vs_h": paired_test(wrong.assign(truth=wrong.truth_h), "unsupported", "f", "h")}
        for r, q in zip(ph.values(), multipletests([r["p_exact"] for r in ph.values()], method="holm")[1]):
            r["p_holm"] = round(float(q), 4)
        out["models"][model] = {"placebo_human_truth": ph,
                                "T_cd": round(t0, 3), "T_ef": round(t1, 3), "dT": round(t1 - t0, 3),
                                "dT_ci95": [round(float(np.percentile(diffs, q)), 3) for q in (2.5, 97.5)],
                                "rely_d_f_by_human_truth": {f"{a}|says_supported={int(b)}|{c}": v for (a, b, c), v in rel.items()}}
    return out


def main() -> None:
    d = load()
    h = human_truth()
    out = {"n_responses": int(len(d)), "placebo": placebo_tests(d), "prior_g": prior(d),
           "human_truth": with_human_truth(d, h) if h is not None else "pending: studyb_labels_<author>.csv not found"}
    OUT.write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
