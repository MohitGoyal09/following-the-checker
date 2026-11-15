import pandas as pd

from sourced.sample import CRH, CRNH, build_sample

COLS = ["noteId", "tweetId", "ai", "currentStatus", "summary"]


def _notes(rows):
    return pd.DataFrame(rows, columns=COLS)


def test_helpful_pairs_take_one_ai_and_one_human_crh_note_per_tweet():
    df = _notes([
        ("a1", "t1", True, CRH, "x https://a.com"),
        ("a2", "t1", True, CRH, "y https://b.com"),
        ("h1", "t1", False, CRH, "z https://c.com"),
        ("h2", "t1", False, CRNH, "w"),
        ("a3", "t2", True, CRH, "only AI is helpful on t2"),
        ("h3", "t2", False, CRNH, "q"),
    ])
    s = build_sample(df, n_pairs=5, n_contrast_each=0, seed=0)
    helpful = s[s.stratum == "helpful_pair"]
    assert set(helpful.tweetId) == {"t1"}  # t2 has no helpful human note
    assert sorted(helpful.ai.tolist()) == [False, True]
    assert (helpful.currentStatus == CRH).all()


def test_contrast_takes_not_helpful_notes_from_each_writer_type():
    df = _notes([
        ("a1", "t1", True, CRNH, "a"), ("a2", "t2", True, CRNH, "b"),
        ("h1", "t1", False, CRNH, "c"), ("h2", "t2", False, CRNH, "d"),
        ("h3", "t3", False, CRH, "e"),
    ])
    s = build_sample(df, n_pairs=0, n_contrast_each=1, seed=0)
    contrast = s[s.stratum == "not_helpful"]
    assert len(contrast) == 2
    assert sorted(contrast.ai.tolist()) == [False, True]
    assert (contrast.currentStatus == CRNH).all()


def test_sample_is_reproducible_and_has_no_duplicate_notes():
    rows = [(f"a{i}", f"t{i}", True, CRH, "s") for i in range(20)]
    rows += [(f"h{i}", f"t{i}", False, CRH, "s") for i in range(20)]
    rows += [(f"c{i}", f"t{i}", True, CRNH, "s") for i in range(20)]
    df = _notes(rows)
    s1 = build_sample(df, n_pairs=5, n_contrast_each=3, seed=7)
    s2 = build_sample(df, n_pairs=5, n_contrast_each=3, seed=7)
    assert s1.noteId.tolist() == s2.noteId.tolist()
    assert s1.noteId.is_unique
