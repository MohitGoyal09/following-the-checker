"""Build the Study A sample from the raw Community Notes snapshot.

Usage: uv run python -m sourced.sample
Writes data/processed/sample_notes.csv (one row per note) and sample_links.csv (one row per cited URL).
"""

from pathlib import Path

import pandas as pd

from sourced.urls import extract_urls

CRH = "CURRENTLY_RATED_HELPFUL"
CRNH = "CURRENTLY_RATED_NOT_HELPFUL"
SINCE = "2025-09-01"  # first AI note appears 2025-09-02
N_PAIRS = 100
N_CONTRAST_EACH = 50
MAX_LINKS_PER_NOTE = 5
SEED = 42
RAW = Path("data/raw")
OUT = Path("data/processed")


def build_sample(notes: pd.DataFrame, n_pairs: int, n_contrast_each: int, seed: int) -> pd.DataFrame:
    """notes: one row per note on a tweet that has both an AI and a human note."""
    crh = notes[notes.currentStatus == CRH]
    per_tweet = crh.groupby("tweetId").ai.agg(["any", "all"])
    eligible = per_tweet[per_tweet["any"] & ~per_tweet["all"]].index.sort_values()
    tweets = pd.Series(eligible).sample(n=min(n_pairs, len(eligible)), random_state=seed)
    pool = crh[crh.tweetId.isin(tweets)].sort_values("noteId")
    pairs = pool.groupby(["tweetId", "ai"], group_keys=False).sample(n=1, random_state=seed)
    pairs = pairs.assign(stratum="helpful_pair")

    crnh = notes[(notes.currentStatus == CRNH) & ~notes.noteId.isin(pairs.noteId)].sort_values("noteId")
    picks = [g.sample(n=min(n_contrast_each, len(g)), random_state=seed) for _, g in crnh.groupby("ai")]
    contrast = pd.concat([crnh.iloc[0:0], *picks]).assign(stratum="not_helpful")
    return pd.concat([pairs, contrast], ignore_index=True)


def load_paired_notes() -> pd.DataFrame:
    enrol = pd.read_csv(RAW / "userEnrollment-00000.tsv", sep="\t",
                        usecols=["participantId", "enrollmentState"], dtype=str)
    ai_writers = set(enrol.loc[enrol.enrollmentState.str.startswith("api", na=False), "participantId"])
    notes = pd.read_csv(RAW / "notes-00000.tsv", sep="\t",
                        usecols=["noteId", "noteAuthorParticipantId", "createdAtMillis", "tweetId",
                                 "summary", "isCollaborativeNote", "classification"],
                        dtype={"noteId": str, "tweetId": str, "noteAuthorParticipantId": str})
    notes = notes[(pd.to_datetime(notes.createdAtMillis, unit="ms") >= SINCE) & (notes.isCollaborativeNote != 1)]
    notes = notes.assign(ai=notes.noteAuthorParticipantId.isin(ai_writers))
    mix = notes.groupby("tweetId").ai.agg(["any", "all"])
    paired = mix[mix["any"] & ~mix["all"]].index
    notes = notes[notes.tweetId.isin(paired)]
    status = pd.read_csv(RAW / "noteStatusHistory-00000.tsv", sep="\t",
                         usecols=["noteId", "currentStatus"], dtype=str)
    return notes.merge(status, on="noteId", how="left")


def to_links(sample: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {"noteId": r.noteId, "link_rank": i, "url": url}
        for r in sample.itertuples()
        for i, url in enumerate(extract_urls(r.summary)[:MAX_LINKS_PER_NOTE])
    ]
    return pd.DataFrame(rows, columns=["noteId", "link_rank", "url"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sample = build_sample(load_paired_notes(), N_PAIRS, N_CONTRAST_EACH, SEED)
    sample = sample.assign(n_urls=sample.summary.map(lambda s: len(extract_urls(s))))
    sample.drop(columns=["noteAuthorParticipantId"]).to_csv(OUT / "sample_notes.csv", index=False)
    links = to_links(sample)
    links.to_csv(OUT / "sample_links.csv", index=False)
    print(sample.groupby(["stratum", "ai"]).agg(notes=("noteId", "size"), links=("n_urls", "sum")).to_string())
    print(f"{len(links)} links, {links.url.nunique()} unique")


if __name__ == "__main__":
    main()
