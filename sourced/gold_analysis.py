"""Human gold labels: author agreement, judge validation, claim checks and the Study B passage check.

Usage: uv run python -m sourced.gold_analysis -> results/gold.json
Reads data/processed/gold/gold_labels_<author>.csv, the keys, and agreed.csv (item,label) for the
shared links the authors disagreed on (PREREGISTRATION.md, Amendment 7). No model calls.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from sourced.gold import AUTHORS

P = "data/processed/"
G = P + "gold/"
OUT = Path("results/gold.json")
JUDGES = ("claude-opus-5-5", "gemini-3.8-flash")
N_BOOT, SEED, EPS = 10_000, 42, 0.2  # EPS: Alternative Annotator Test margin for skilled annotators (Calderon et al. 2025)


def kappa(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    cats = np.union1d(a, b)
    po = (a == b).mean()
    pe = sum((a == c).mean() * (b == c).mean() for c in cats)
    return float((po - pe) / (1 - pe)) if pe < 1 else 1.0


def kappa_ci(a, b, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    a, b = np.asarray(a), np.asarray(b)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), (n_boot, len(a)))
    ks = np.array([kappa(a[i], b[i]) for i in idx])
    lo, hi = np.nanpercentile(ks, [2.5, 97.5])
    return {"kappa": round(kappa(a, b), 3), "ci95": [round(lo, 3), round(hi, 3)], "n": int(len(a)),
            "agree": round(float((a == b).mean()), 3)}


def binary(x) -> np.ndarray:
    return np.asarray(x) == "supports"


def alt_test(llm, ann: dict, eps: float = EPS) -> dict:
    """Alternative Annotator Test with leave-one-out; here only 2 annotators, so descriptive."""
    from scipy.stats import ttest_rel
    out = {}
    for j in ann:
        others = [o for o in ann if o != j]
        ref = np.asarray(ann[others[0]])
        s_llm, s_h = (np.asarray(llm) == ref).astype(float), (np.asarray(ann[j]) == ref).astype(float)
        p = ttest_rel(s_llm, s_h - eps, alternative="greater").pvalue
        out[j] = {"llm_align": round(s_llm.mean(), 3), "human_align": round(s_h.mean(), 3), "p": round(float(p), 4)}
    out["winning_rate"] = sum(v["p"] < 0.05 for v in out.values()) / len(ann)
    return out


def load_labels() -> pd.DataFrame:
    return pd.concat([pd.read_csv(G + f"gold_labels_{w}.csv") for w in AUTHORS])


def support_gold(lab: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    key = pd.read_csv(G + "support_key.csv", dtype={"noteId": str})
    s = lab[lab.item.str.startswith("S")].pivot(index="item", columns="labeller", values="label")
    shared = s.loc[key.item[key.labeller == "both"]]
    agreed = pd.read_csv(G + "agreed.csv").set_index("item").label if Path(G + "agreed.csv").exists() else pd.Series(dtype=str)
    missing = [i for i in shared.index[shared[AUTHORS[0]] != shared[AUTHORS[1]]] if i not in agreed.index]
    if missing:
        raise SystemExit(f"agreed.csv lacks a gold label for disagreed links: {missing}")
    gold = s.bfill(axis=1).iloc[:, 0].rename("gold")  # single-labelled items: the one label
    gold.loc[shared.index] = np.where(shared[AUTHORS[0]] == shared[AUTHORS[1]], shared[AUTHORS[0]],
                                      agreed.reindex(shared.index))
    return key.merge(gold, left_on="item", right_index=True), shared


def judge_validation(gold: pd.DataFrame, shared: pd.DataFrame) -> dict:
    out = {}
    for j in JUDGES:
        v = pd.read_csv(P + f"verdicts_{j}.csv", dtype={"noteId": str})
        m = gold.merge(v[["noteId", "url", "source", "verdict"]], on=["noteId", "url", "source"], how="left")
        assert m.verdict.notna().all(), f"{j}: gold link without a verdict"
        res = {"all": kappa_ci(m.gold, m.verdict), "binary_supports": kappa_ci(binary(m.gold), binary(m.verdict))}
        for ai, g in m.groupby("ai"):
            res["ai" if ai else "human"] = kappa_ci(g.gold, g.verdict)
        res["confusion"] = pd.crosstab(m.gold, m.verdict).to_dict(orient="index")
        sh = m.set_index("item").loc[shared.index]
        res["alt_test_shared20"] = alt_test(sh.verdict, {a: shared[a].values for a in AUTHORS})
        out[j] = res
    ranked = sorted(JUDGES, key=lambda j: out[j]["all"]["kappa"], reverse=True)
    out["primary_judge"] = ranked[0]
    out["primary_passes_bar_0.6"] = out[ranked[0]]["all"]["kappa"] >= 0.6
    return out


def claim_checks(lab: pd.DataFrame) -> dict:
    key = pd.read_csv(G + "claim_key.csv", dtype={"noteId": str})
    m = key.merge(lab[lab.item.str.startswith("C")][["item", "label"]], on="item")
    err = m.label.eq("incorrect")
    return {"n": int(len(m)), "incorrect": int(err.sum()),
            "error_rate_by_writer": {("ai" if k else "human"): round(float(v), 3) for k, v in err.groupby(m.ai).mean().items()}}


def passage_check(lab: pd.DataFrame) -> dict:
    key = pd.read_csv(G + "passage_key.csv", dtype={"noteId": str})
    m = key.merge(lab[lab.item.str.startswith("P")][["item", "label"]].rename(columns={"label": "human"}), on="item")
    unsup_partial = m[(m.truth == "unsupported") & (m.stratum == "partial")]
    r = pd.read_csv(P + "study_b_responses.csv", dtype={"noteId": str})
    r = r[~r.fallback.fillna(False).astype(bool) & r.condition.isin(["e", "f"])].merge(m[["noteId", "human", "truth"]], on=["noteId", "truth"])
    rel = r[r.truth == "unsupported"].groupby(["model", "condition", "human"]).rely.agg(["mean", "size"]).round(3)
    return {
        "labels_by_stratum_truth": {f"{s}|{t}": v for (s, t), v in pd.crosstab([m.stratum, m.truth], m.human).to_dict(orient="index").items()},
        "unsupported_partial_n": int(len(unsup_partial)),
        "unsupported_partial_human_supports_share": round(float(unsup_partial.human.eq("supports").mean()), 3),
        "unsupported_reliance_ef_by_human_label": {f"{a}|{b}|{c}": v for (a, b, c), v in rel.to_dict(orient="index").items()},
    }


def main() -> None:
    lab = load_labels()
    gold, shared = support_gold(lab)
    a, b = shared[AUTHORS[0]], shared[AUTHORS[1]]
    out = {
        "inter_author_shared20": {"labels": kappa_ci(a, b), "binary_supports": kappa_ci(binary(a), binary(b)),
                                  "confusion": pd.crosstab(a, b).to_dict(orient="index")},
        "gold_counts": gold.gold.value_counts().to_dict(),
        "judges": judge_validation(gold, shared),
        "claims": claim_checks(lab),
        "passages": passage_check(lab),
    }
    gold[["item", "noteId", "url", "source", "ai", "gold"]].to_csv(G + "gold_support.csv", index=False)
    OUT.write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
