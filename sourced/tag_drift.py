"""C8 (Amendment 4): monthly source-tag and placebo-tag counts over all ratings, by note writer type.

Usage: uv run python -m sourced.tag_drift  -> data/processed/tag_drift_monthly.csv (counts only; shares are
computed in the analysis step). Streams every ratings zip; nothing is unzipped to disk.
"""

import sys
import zipfile
from pathlib import Path

import pandas as pd

from sourced.ratings import HELPFUL_LEVELS, ZIP_DIR

RAW = Path("data/raw")
OUT = Path("data/processed/tag_drift_monthly.csv")
COLS = ["noteId", "createdAtMillis", "helpfulnessLevel", "helpfulGoodSources", "helpfulClear",
        "helpfulUnbiasedLanguage", "notHelpfulSourcesMissingOrUnreliable", "notHelpfulIncorrect"]
SUMS = {"good_sources": "helpfulGoodSources", "clear": "helpfulClear", "unbiased": "helpfulUnbiasedLanguage",
        "sources_missing": "notHelpfulSourcesMissingOrUnreliable", "incorrect": "notHelpfulIncorrect"}
HELPFUL_TAGS = {"good_sources", "clear", "unbiased"}


def monthly_counts(r: pd.DataFrame, ai_notes: set) -> pd.DataFrame:
    helpful = r.helpfulnessLevel.isin(HELPFUL_LEVELS)
    not_helpful = r.helpfulnessLevel.eq("NOT_HELPFUL")
    d = pd.DataFrame({
        "month": pd.to_datetime(r.createdAtMillis, unit="ms", utc=True).dt.strftime("%Y-%m"),
        "ai": r.noteId.isin(ai_notes),
        "n_helpful": helpful.astype(int),
        "n_not_helpful": not_helpful.astype(int),
    })
    for name, col in SUMS.items():
        mask = helpful if name in HELPFUL_TAGS else not_helpful
        d[name] = r[col].fillna(0).astype(int).where(mask, 0)
    return d.groupby(["month", "ai"], as_index=False).sum()


def ai_note_ids() -> set:
    enrol = pd.read_csv(RAW / "userEnrollment-00000.tsv", sep="\t", usecols=["participantId", "enrollmentState"],
                        dtype=str)
    writers = set(enrol.loc[enrol.enrollmentState.str.startswith("api", na=False), "participantId"])
    notes = pd.read_csv(RAW / "notes-00000.tsv", sep="\t", usecols=["noteId", "noteAuthorParticipantId"], dtype=str)
    return set(notes.loc[notes.noteAuthorParticipantId.isin(writers), "noteId"])


def main() -> None:
    ai = ai_note_ids()
    print(f"{len(ai)} AI-written notes", file=sys.stderr)
    parts = []
    for path in sorted(ZIP_DIR.glob("ratings-*.zip")):
        with zipfile.ZipFile(path) as z, z.open(z.namelist()[0]) as f:
            for chunk in pd.read_csv(f, sep="\t", usecols=COLS, dtype={"noteId": str}, chunksize=2_000_000):
                parts.append(monthly_counts(chunk, ai))
        print(f"  {path.name} done", file=sys.stderr)
    out = pd.concat(parts).groupby(["month", "ai"], as_index=False).sum().sort_values(["month", "ai"])
    out.to_csv(OUT, index=False)
    print(f"{len(out)} month x writer-type rows -> {OUT}")


if __name__ == "__main__":
    main()
