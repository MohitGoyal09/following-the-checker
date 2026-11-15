"""Draw the human gold sets and write one self-contained labelling page per author (Amendments 1, 3 and 7).

Usage: uv run python -m sourced.gold  -> data/processed/gold/{support,claim,passage}_key.csv + label_<author>.html
The pages show no writer type, no judge output and no group. The keys hold them and stay local.
"""

import json
from pathlib import Path

import pandas as pd

from sourced.judge_common import judge_items

SEED = 42
PER_GROUP = 25
AUTHORS = ("mohit", "ananya")
SUPPORT_SHARED = 20  # Amendment 7: labelled by both authors
PASSAGE_EXTRA = 10  # Amendment 7: non-partial Study B items mixed in with the 20 partial ones
P = Path("data/processed")
OUT = P / "gold"


def stratified(df: pd.DataFrame, by: str, per_group: int, seed: int) -> pd.DataFrame:
    parts = [g.sample(n=min(per_group, len(g)), random_state=seed) for _, g in df.groupby(by)]
    return pd.concat(parts).sample(frac=1, random_state=seed).reset_index(drop=True)


def assign(df: pd.DataFrame, by: str, n_shared: int = 0) -> pd.Series:
    """Amendment 7: the first n_shared/2 rows of each group (the frame is already shuffled) go to both authors;
    the rest alternate between the authors in group order, so each gets a near-equal share of every group."""
    out = pd.Series("", index=df.index, dtype=object)
    rest = []
    for _, g in df.groupby(by, sort=True):
        out[g.index[: n_shared // 2]] = "both"
        rest += list(g.index[n_shared // 2:])
    out[rest[0::2]] = AUTHORS[0]
    out[rest[1::2]] = AUTHORS[1]
    return out


def passages(claims: pd.DataFrame) -> pd.DataFrame:
    """Amendment 7: the Study B passages behind a Claude `partial` page, plus PASSAGE_EXTRA others (seed 44)."""
    from sourced.study_b import build_evidence
    from sourced.study_b_robustness import item_table

    it = item_table().sort_values("noteId")
    it["stratum"] = it.page_verdict.eq("partial").map({True: "partial", False: "other"})
    extra = it[it.stratum == "other"].sample(n=PASSAGE_EXTRA, random_state=SEED + 2)
    pick = pd.concat([it[it.stratum == "partial"], extra]).sample(frac=1, random_state=SEED + 2).reset_index(drop=True)
    ev = build_evidence(set(pick.noteId))
    pick["url"] = [ev[n][0] for n in pick.noteId]
    pick["text"] = [ev[n][1] for n in pick.noteId]
    pick = pick.merge(claims, on="noteId", how="left")
    pick.insert(0, "item", [f"P{i + 1:02d}" for i in range(len(pick))])
    return pick


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    notes = pd.read_csv(P / "sample_notes.csv", dtype={"noteId": str})[["noteId", "ai", "summary"]]
    claims = pd.read_csv(P / "claims.csv", dtype={"noteId": str})[["noteId", "claim"]]

    pages = pd.DataFrame(judge_items(str(P) + "/"))[["noteId", "url", "source", "claim", "text"]]
    pages = pages.merge(notes[["noteId", "ai"]], on="noteId").sort_values(["noteId", "url"])
    support = stratified(pages, "ai", PER_GROUP, SEED)
    support.insert(0, "item", [f"S{i + 1:02d}" for i in range(len(support))])

    cn = notes.merge(claims, on="noteId").dropna(subset=["claim"]).sort_values("noteId")
    claim_set = stratified(cn, "ai", PER_GROUP, SEED + 1)
    claim_set.insert(0, "item", [f"C{i + 1:02d}" for i in range(len(claim_set))])

    support["labeller"] = assign(support, "ai", SUPPORT_SHARED)
    claim_set["labeller"] = assign(claim_set, "ai")
    psg = passages(claims)
    psg["labeller"] = assign(psg, "stratum")

    support[["item", "noteId", "url", "source", "ai", "labeller"]].to_csv(OUT / "support_key.csv", index=False)
    claim_set[["item", "noteId", "ai", "labeller"]].to_csv(OUT / "claim_key.csv", index=False)
    psg[["item", "noteId", "url", "truth", "page_verdict", "stratum", "labeller"]].to_csv(OUT / "passage_key.csv", index=False)
    template = (Path(__file__).parent / "label_template.html").read_text()
    (OUT / "label.html").unlink(missing_ok=True)  # the old shared page; Amendment 7 replaces it
    for who in AUTHORS:
        mine = lambda df: df[df.labeller.isin(["both", who])]  # noqa: E731
        payload = {
            "support": mine(support)[["item", "claim", "url", "text"]].to_dict("records"),
            "claims": mine(claim_set)[["item", "summary", "claim"]].to_dict("records"),
            "passages": mine(psg)[["item", "claim", "url", "text"]].to_dict("records"),
        }
        # page text is untrusted web content: embed as JSON (no HTML parsing), block any '</script' breakout
        page = template.replace("__DATA__", json.dumps(payload).replace("</", "<\\/"))
        (OUT / f"label_{who}.html").write_text(page)
        print(f"{who}: S {len(payload['support'])}, C {len(payload['claims'])}, P {len(payload['passages'])} "
              f"-> {OUT}/label_{who}.html")


if __name__ == "__main__":
    main()
