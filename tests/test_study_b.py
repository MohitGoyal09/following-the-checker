import pandas as pd
import pytest

from sourced.study_b import (
    CONDITIONS, LABEL_LINE, SCHEMA, build_message, excerpt, note_labels, placebo_pairs, select_items, valid_confidence,
)


def test_schema_has_no_integer_bounds_and_range_is_enforced_in_code():
    assert "minimum" not in SCHEMA["properties"]["confidence"]  # Claude rejects integer bounds
    assert valid_confidence(0) == 0 and valid_confidence(100) == 100
    assert valid_confidence(101) is None and valid_confidence(-1) is None and valid_confidence("80") is None


def test_conditions_are_the_preregistered_eight():
    assert CONDITIONS == ("a", "b", "c", "d", "e", "f", "g", "h")  # g, h: Amendment 8


def test_claim_only_condition_shows_no_note_label_or_tool():
    m = build_message("SECRET NOTE", "C.", "g", "supported")
    assert "SECRET NOTE" not in m and LABEL_LINE not in m and "Source-check" not in m and m.endswith("STATEMENT: C.")


@pytest.mark.parametrize("truth", ["supported", "unsupported"])
def test_placebo_condition_matches_f_except_for_the_passage(truth):
    ev = ("https://other.com/x", "unrelated text")
    assert build_message("N", "C.", "h", truth, evidence=ev) == build_message("N", "C.", "f", truth, evidence=ev)


def test_placebo_pairs_never_pair_an_item_with_itself_or_its_post():
    items = pd.DataFrame({"noteId": list("abcdef")})
    tweets = pd.Series({"a": 1, "b": 1, "c": 2, "d": 2, "e": 3, "f": 3})
    pairs = placebo_pairs(items, tweets)
    assert sorted(pairs.values()) == list("abcdef")
    assert all(a != b and tweets[a] != tweets[b] for a, b in pairs.items())


@pytest.mark.parametrize("truth", ["supported", "unsupported"])
def test_evidence_conditions_add_only_the_passage_line(truth):
    ev = ("https://a.com/p", "the passage text")
    for plain, with_ev in (("c", "e"), ("d", "f")):
        m_plain = build_message("N", "C.", plain, truth)
        m_ev = build_message("N", "C.", with_ev, truth, evidence=ev)
        passage = 'Passage the tool checked (from https://a.com/p): "the passage text"'
        assert passage in m_ev
        assert m_ev.replace(passage + "\n", "") == m_plain  # identical apart from the passage line
    # e and f show the same passage, opposite verdicts
    e, f = build_message("N", "C.", "e", truth, ev), build_message("N", "C.", "f", truth, ev)
    assert ("DO support" in e) != ("DO support" in f)


def test_plain_conditions_are_unchanged_by_evidence_argument():
    assert build_message("N", "C.", "c", "supported", evidence=("u", "x")) == build_message("N", "C.", "c", "supported")


def test_excerpt_centres_on_quote_and_falls_back_to_start():
    text = "A" * 3000 + "KEY SENTENCE HERE" + "B" * 3000
    ex = excerpt(text, "key sentence here")
    assert "KEY SENTENCE HERE" in ex and len(ex) <= 1200
    assert excerpt(text, "") == text[:1200]
    assert excerpt(text, "not in the page") == text[:1200]
    assert excerpt("short", "short") == "short"


@pytest.mark.parametrize("truth,cond,expect_label,expect_tool", [
    ("supported", "a", False, None),
    ("supported", "b", True, None),
    ("supported", "c", True, "DO support"),
    ("supported", "d", True, "DO NOT support"),
    ("unsupported", "c", True, "DO NOT support"),
    ("unsupported", "d", True, "DO support"),
])
def test_message_shows_label_and_tool_only_where_preregistered(truth, cond, expect_label, expect_tool):
    m = build_message("Note text https://a.com", "The claim.", cond, truth)
    assert "NOTE: Note text https://a.com" in m and "STATEMENT: The claim." in m
    assert (LABEL_LINE in m) == expect_label
    if expect_tool is None:
        assert "Source-check tool" not in m
    else:
        assert f"The cited sources {expect_tool} the note's claim." in m


def test_note_label_is_supported_if_any_link_supports():
    v = pd.DataFrame({"noteId": ["n1", "n1", "n2", "n2"], "verdict": ["silent", "supports", "partial", "silent"]})
    assert note_labels(v).to_dict() == {"n1": "supported", "n2": "unsupported"}


def test_select_items_uses_agreed_helpful_notes_and_balances_unsupported():
    rows = []
    for i in range(60):
        rows.append({"noteId": f"u{i}", "ai": i % 2 == 0, "stratum": "helpful_pair", "c": "unsupported", "g": "unsupported"})
    for i in range(45):
        rows.append({"noteId": f"s{i}", "ai": i % 3 == 0, "stratum": "helpful_pair", "c": "supported", "g": "supported"})
    rows.append({"noteId": "x", "ai": True, "stratum": "helpful_pair", "c": "supported", "g": "unsupported"})
    rows.append({"noteId": "y", "ai": True, "stratum": "not_helpful", "c": "supported", "g": "supported"})
    items = select_items(pd.DataFrame(rows), n_per_label=40, seed=42)
    assert len(items) == 80 and items.noteId.is_unique
    assert not items.noteId.isin(["x", "y"]).any()
    u = items[items.truth == "unsupported"]
    assert u.ai.value_counts().to_dict() == {True: 20, False: 20}
    assert (items.truth == "supported").sum() == 40
