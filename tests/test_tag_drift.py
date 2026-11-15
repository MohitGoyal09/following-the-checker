import pandas as pd

from sourced.tag_drift import monthly_counts


def test_monthly_counts_use_right_denominators_and_writer_type():
    ms = lambda d: int(pd.Timestamp(d, tz="UTC").timestamp() * 1000)  # noqa: E731
    r = pd.DataFrame({
        "noteId": ["a", "a", "h", "h", "h"],
        "createdAtMillis": [ms("2025-09-03"), ms("2025-09-20"), ms("2025-09-05"), ms("2025-10-01"), ms("2025-10-02")],
        "helpfulnessLevel": ["HELPFUL", "NOT_HELPFUL", "SOMEWHAT_HELPFUL", "HELPFUL", "NOT_HELPFUL"],
        "helpfulGoodSources": [1, 0, 0, 1, 0],
        "helpfulClear": [1, 0, 1, 0, 0],
        "helpfulUnbiasedLanguage": [0, 0, 1, 1, 0],
        "notHelpfulSourcesMissingOrUnreliable": [0, 1, 0, 0, 0],
        "notHelpfulIncorrect": [0, 0, 0, 0, 1],
    })
    c = monthly_counts(r, ai_notes={"a"}).set_index(["month", "ai"])
    assert c.loc[("2025-09", True), "n_helpful"] == 1
    assert c.loc[("2025-09", True), "good_sources"] == 1
    assert c.loc[("2025-09", True), "n_not_helpful"] == 1
    assert c.loc[("2025-09", True), "sources_missing"] == 1
    assert c.loc[("2025-09", False), "n_helpful"] == 1  # SOMEWHAT_HELPFUL counts as helpful
    assert c.loc[("2025-10", False), "n_helpful"] == 1
    assert c.loc[("2025-10", False), "incorrect"] == 1
