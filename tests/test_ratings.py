import pandas as pd

from sourced.ratings import aggregate, keep_rows


def test_keep_rows_matches_whole_note_id_only():
    lines = [b"111\tA\n", b"1112\tB\n", b"222\tC\n", b"11\tD\n"]
    assert list(keep_rows(lines, {b"111", b"222"})) == [b"111\tA\n", b"222\tC\n"]


def test_aggregate_shares_use_the_right_denominators():
    r = pd.DataFrame({
        "noteId": ["n1"] * 5 + ["n2"],
        "helpfulnessLevel": ["HELPFUL", "HELPFUL", "SOMEWHAT_HELPFUL", "NOT_HELPFUL", "NOT_HELPFUL", "HELPFUL"],
        "helpfulGoodSources": [1, 0, 1, 0, 0, 0],
        "notHelpfulSourcesMissingOrUnreliable": [0, 0, 0, 1, 0, 0],
    })
    a = aggregate(r).set_index("noteId")
    # good-sources share is over helpful + somewhat-helpful ratings (the only ones shown that question)
    assert a.loc["n1", "n_ratings"] == 5
    assert a.loc["n1", "good_sources_share"] == 2 / 3
    # sources-missing share is over not-helpful ratings only
    assert a.loc["n1", "sources_missing_share"] == 1 / 2
    assert pd.isna(a.loc["n2", "sources_missing_share"])  # no not-helpful ratings -> undefined, not 0
