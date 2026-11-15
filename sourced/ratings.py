"""Per-note rater source tags for the sample (Amendment 1, item 8 / H6).

Usage: uv run python -m sourced.ratings   -> data/processed/rater_tags.csv
The ratings table is split into several ~1.4 GB zips (sorted by noteId). Each is downloaded once,
then streamed so only rows for sampled notes are kept (no 50 GB unzip).
"""

import subprocess
import sys
import zipfile
from collections.abc import Iterable, Iterator
from io import StringIO
from pathlib import Path

import pandas as pd

SNAPSHOT = "2026/11/15"
URL = "https://ton.twimg.com/birdwatch-public-data/{snap}/noteRatings/ratings-{i:05d}.zip"
ZIP_DIR = Path("data/raw/ratings")
FILTERED = Path("data/processed/ratings_sample.tsv")
OUT = Path("data/processed/rater_tags.csv")
COLS = ["noteId", "helpfulnessLevel", "helpfulGoodSources", "notHelpfulSourcesMissingOrUnreliable"]
HELPFUL_LEVELS = {"HELPFUL", "SOMEWHAT_HELPFUL"}
MAX_FILES = 20


def keep_rows(lines: Iterable[bytes], ids: set[bytes]) -> Iterator[bytes]:
    for line in lines:
        if line.split(b"\t", 1)[0] in ids:
            yield line


def aggregate(r: pd.DataFrame) -> pd.DataFrame:
    helpful = r.helpfulnessLevel.isin(HELPFUL_LEVELS)
    not_helpful = r.helpfulnessLevel.eq("NOT_HELPFUL")
    g = r.assign(
        is_helpful=helpful, is_not_helpful=not_helpful,
        good=r.helpfulGoodSources.where(helpful),
        missing=r.notHelpfulSourcesMissingOrUnreliable.where(not_helpful),
    ).groupby("noteId")
    return pd.DataFrame({
        "n_ratings": g.size(),
        "n_helpful": g.is_helpful.sum(),
        "n_not_helpful": g.is_not_helpful.sum(),
        "good_sources_share": g.good.mean(),
        "sources_missing_share": g.missing.mean(),
    }).reset_index()


def _download(i: int) -> Path | None:
    path = ZIP_DIR / f"ratings-{i:05d}.zip"
    if path.exists() and zipfile.is_zipfile(path):
        return path
    url = URL.format(snap=SNAPSHOT, i=i)
    code = subprocess.run(["curl", "-s", "-o", "/dev/null", "-r", "0-0", "--retry", "5", "--max-time", "120",
                           "-w", "%{http_code}", url], capture_output=True, text=True).stdout
    if code not in ("200", "206"):
        return None
    subprocess.run(["curl", "-s", "--retry", "5", "-o", str(path), url], check=True)
    return path if zipfile.is_zipfile(path) else None


def main() -> None:
    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    ids = set(pd.read_csv("data/processed/sample_notes.csv", dtype={"noteId": str}).noteId)
    ids_b = {i.encode() for i in ids}
    header, kept = None, []
    for i in range(MAX_FILES):
        path = _download(i)
        if path is None:
            print(f"ratings-{i:05d}: not found, stopping", file=sys.stderr)
            break
        with zipfile.ZipFile(path) as z, z.open(z.namelist()[0]) as f:
            first = f.readline()  # every part repeats the header
            header = header or first
            rows = list(keep_rows(f, ids_b))
        kept += rows
        print(f"ratings-{i:05d}: kept {len(rows)} rows", file=sys.stderr)
    FILTERED.write_bytes(header + b"".join(kept))
    r = pd.read_csv(StringIO(FILTERED.read_text()), sep="\t", usecols=COLS, dtype={"noteId": str})
    out = aggregate(r)
    out.to_csv(OUT, index=False)
    print(f"{len(r)} ratings for {out.noteId.nunique()} of {len(ids)} sampled notes -> {OUT}")


if __name__ == "__main__":
    main()
