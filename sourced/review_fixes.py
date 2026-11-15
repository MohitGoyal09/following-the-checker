"""Analyses added after the independent review (exploratory, post hoc; no model calls).

Usage: uv run python -m sourced.review_fixes -> results/review_fixes.json
- Reader accuracy by condition and the checker accuracy at which a verdict starts to help (break-even).
- Answer mix (yes / unsure / no) by condition.
- 95% paired-bootstrap intervals for the placebo contrasts (h minus f).
- Human-only Study A rate under both resolutions of the 5 disputed gold links, with note-clustered intervals.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

P = "data/processed/"
G = P + "gold/"
OUT = Path("results/review_fixes.json")
N_BOOT, SEED = 10_000, 42


def responses() -> pd.DataFrame:
    d = pd.read_csv(P + "study_b_responses.csv", dtype={"noteId": str})
    d = d[~d.fallback.fillna(False).astype(bool)]
    return d.assign(correct=np.where(d.truth == "supported", d.answer == "yes", d.answer != "yes"))


def accuracy(d: pd.DataFrame) -> dict:
    out = {}
    for model, dm in d.groupby("model"):
        acc = dm.groupby("condition").correct.mean()
        base = acc["b"]  # the label is shown in every tool condition
        # checker accuracy p at which p*acc(right) + (1-p)*acc(wrong) equals no-tool accuracy; 0 if even a wrong verdict does no harm
        be = lambda right, wrong: max(0.0, float((base - wrong) / (right - wrong))) if right != wrong else None  # noqa: E731
        out[model] = {"accuracy": acc.round(4).to_dict(),
                      "break_even_checker_accuracy_verdict_only": round(be(acc["c"], acc["d"]), 4),
                      "break_even_checker_accuracy_with_passage": round(be(acc["e"], acc["f"]), 4)}
    return out


def answer_mix(d: pd.DataFrame) -> dict:
    t = d[d.condition.isin(list("cdef"))].groupby(["model", "truth", "condition"]).answer.value_counts().unstack(fill_value=0)
    return {f"{m}|{tr}|{c}": row.to_dict() for (m, tr, c), row in t.iterrows()}


def placebo_ci(d: pd.DataFrame) -> dict:
    rng = np.random.default_rng(SEED)
    out = {}
    for (model, truth), g in d[d.condition.isin(["f", "h"])].groupby(["model", "truth"]):
        w = g.pivot_table(index="noteId", columns="condition", values="rely", aggfunc="first").astype(float)
        diff = (w["h"] - w["f"]).to_numpy()
        boots = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(N_BOOT)]
        out[f"{model}|{truth}"] = {"h_minus_f": round(float(diff.mean()), 4), "n": int(len(diff)),
                                    "ci95": [round(float(np.percentile(boots, q)), 4) for q in (2.5, 97.5)]}
    return out


def gold_rate() -> dict:
    lab = pd.concat([pd.read_csv(G + f"gold_labels_{w}.csv") for w in ("mohit", "ananya")])
    s = lab[lab.item.str.startswith("S")].pivot(index="item", columns="labeller", values="label")
    key = pd.read_csv(G + "support_key.csv", dtype={"noteId": str}).set_index("item")
    rng = np.random.default_rng(SEED)
    out = {}
    for who in ("ananya", "mohit"):  # whose label settles the 5 disputed shared links
        other = "mohit" if who == "ananya" else "ananya"
        gold = s[who].fillna(s[other])
        d = key.assign(gold=gold).reset_index()
        d["not_sup"] = d.gold != "supports"
        notes = {n: g.not_sup.to_numpy() for n, g in d.groupby("noteId")}
        ids = list(notes)
        boots = []
        for _ in range(N_BOOT):
            pick = np.concatenate([notes[ids[i]] for i in rng.integers(0, len(ids), len(ids))])
            boots.append(pick.mean())
        out[f"disputes_settled_by_{who}"] = {"not_fully_supported": round(float(d.not_sup.mean()), 4),
                                             "ci95_note_clustered": [round(float(np.percentile(boots, q)), 4) for q in (2.5, 97.5)],
                                             "n_links": int(len(d)), "n_notes": len(ids)}
    return out


def main() -> None:
    d = responses()
    out = {"accuracy": accuracy(d), "answer_mix_cdef": answer_mix(d), "placebo_h_minus_f": placebo_ci(d),
           "gold_human_rate": gold_rate()}
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("accuracy", "placebo_h_minus_f", "gold_human_rate")}, indent=1))


if __name__ == "__main__":
    main()
