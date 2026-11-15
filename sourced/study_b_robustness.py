"""Robustness checks for Study B, added after an independent review (exploratory, not preregistered).

Usage: uv run python -m sourced.study_b_robustness -> results/study_b_robustness.json
No model calls. Reads the Study B responses, the items, the judge verdicts and the sample.
"""

import json
from pathlib import Path

import pandas as pd

from sourced.study_b import P, build_evidence
from sourced.study_b_analysis import evidence_test, indices

OUT = Path("results/study_b_robustness.json")


def support_gap(d: pd.DataFrame, cond: str) -> float:
    """T within one condition: reliance on supported minus unsupported notes."""
    s = d[d.condition == cond]
    return float(s.rely[s.truth == "supported"].mean() - s.rely[s.truth == "unsupported"].mean())


def item_table() -> pd.DataFrame:
    """Per item: tweet, the Claude verdict on the page the passage came from, and whether the passage is centred on a judge quote."""
    items = pd.read_csv(P + "study_b_items.csv", dtype={"noteId": str})
    tweets = pd.read_csv(P + "sample_notes.csv", dtype={"noteId": str, "tweetId": str}).set_index("noteId").tweetId
    verdicts = pd.read_csv(P + "verdicts_claude-opus-5-5.csv", dtype={"noteId": str}).set_index(["noteId", "url"]).verdict
    quoted = set()
    for model in ("gemini-3.8-flash", "claude-opus-5-5"):  # same rule as build_evidence
        v = pd.read_csv(P + f"verdicts_{model}.csv", dtype={"noteId": str})
        quoted |= set(zip(v.noteId[v.quote_found.astype(str).eq("True")], v.url[v.quote_found.astype(str).eq("True")]))
    ev = build_evidence(set(items.noteId))
    return items.assign(
        tweetId=items.noteId.map(tweets),
        page_verdict=[verdicts[(n, ev[n][0])] for n in items.noteId],
        passage_on_quote=[(n, ev[n][0]) in quoted for n in items.noteId],
    )


def main() -> None:
    d = pd.read_csv(P + "study_b_responses.csv", dtype={"noteId": str})
    d = d[~d.fallback.fillna(False).astype(bool) & d.condition.isin(list("abcdef"))]  # g, h: sourced/study_b_amend8.py
    it = item_table()
    d = d.merge(it[["noteId", "tweetId", "page_verdict"]], on="noteId")
    out = {
        "passage_on_judge_quote_share": it.groupby("truth").passage_on_quote.mean().round(3).to_dict(),
        "page_verdict_counts": pd.crosstab(it.truth, it.page_verdict).to_dict(orient="index"),
        "n_tweets": int(it.tweetId.nunique()),
        "models": {},
    }
    for model, dm in d.groupby("model"):
        unsup = dm[dm.truth == "unsupported"]
        partial = unsup.page_verdict == "partial"
        no_partial = dm[~((dm.truth == "unsupported") & (dm.page_verdict == "partial"))]
        rejects = dm.assign(rely=dm.answer != "no")  # only an explicit "no" counts as not relying
        tw = evidence_test(dm, n_boot=2_000, cluster="tweetId")
        out["models"][model] = {
            "T_no_tool": {c: support_gap(dm, c) for c in ("a", "b")},
            "unsupported_reliance_by_page_verdict": {
                f"{c}_{'partial' if k else 'silent_or_contradicts'}": float(g.rely.mean())
                for (c, k), g in unsup[unsup.condition.isin(["d", "f"])].groupby(["condition", partial])
            },
            "without_partial_items": {"F_cd_T_cd": indices(no_partial, ("c", "d")), "F_ef_T_ef": indices(no_partial, ("e", "f")),
                                      "n_items": int(no_partial.noteId.nunique())},
            "unsure_counts_as_relying": {"F_cd_T_cd": indices(rejects, ("c", "d")), "F_ef_T_ef": indices(rejects, ("e", "f"))},
            "tweet_cluster_ci95": {k: v["ci95"] for k, v in tw.items() if k.startswith("H")},
        }
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
