"""Human truth for Study B (Amendment 8, part A): labelling pages for the Study B pages without a gold label.

Usage: uv run python -m sourced.gold_b -> data/processed/gold/studyb_key.csv + label_b_<author>.html
Same blind page and labels as the support task; the key holds the assignment.
"""

import json
from pathlib import Path

import pandas as pd

from sourced.gold import AUTHORS
from sourced.judge_common import judge_items

SEED = 46
P = Path("data/processed")
OUT = P / "gold"


def main() -> None:
    items = pd.read_csv(P / "study_b_items.csv", dtype={"noteId": str})
    pages = pd.DataFrame(judge_items(str(P) + "/"))[["noteId", "url", "source", "claim", "text"]]
    pages = pages[pages.noteId.isin(items.noteId)]
    gold = pd.read_csv(OUT / "gold_support.csv", dtype={"noteId": str})[["noteId", "url", "source"]]
    todo = pages.merge(gold, on=["noteId", "url", "source"], how="left", indicator=True)
    todo = todo[todo._merge == "left_only"].drop(columns="_merge").sort_values(["noteId", "url"])
    todo = todo.sample(frac=1, random_state=SEED).reset_index(drop=True)
    todo.insert(0, "item", [f"B{i + 1:03d}" for i in range(len(todo))])
    todo["labeller"] = [AUTHORS[i % 2] for i in range(len(todo))]
    todo[["item", "noteId", "url", "source", "labeller"]].to_csv(OUT / "studyb_key.csv", index=False)
    template = (Path(__file__).parent / "label_template.html").read_text()
    for who in AUTHORS:
        mine = todo[todo.labeller == who][["item", "claim", "url", "text"]].to_dict("records")
        payload = {"support": mine, "claims": [], "passages": []}
        page = template.replace("__DATA__", json.dumps(payload).replace("</", "<\\/"))  # untrusted page text
        page = page.replace("gold_labels_", "studyb_labels_")  # do not overwrite the earlier exports
        (OUT / f"label_b_{who}.html").write_text(page)
        print(f"{who}: {len(mine)} pages -> {OUT}/label_b_{who}.html")


if __name__ == "__main__":
    main()
