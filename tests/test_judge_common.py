import pytest

from sourced.judge_common import (
    VERDICTS, best_pages, cache_key, memory_audit_pairs, quote_found, strip_urls, validate_verdict,
)


def test_memory_audit_never_pairs_a_page_with_its_own_note():
    pages = [{"noteId": f"n{i % 7}", "url": f"u{i}", "source": "live", "text": f"T{i}"} for i in range(40)]
    claims = {f"n{i}": f"claim {i}" for i in range(7)}
    pairs = memory_audit_pairs(pages, claims, n=20, seed=1)
    assert len(pairs) == 20
    assert all(p["claimNoteId"] != p["noteId"] for p in pairs)
    assert all(p["claim"] == claims[p["claimNoteId"]] for p in pairs)
    assert pairs == memory_audit_pairs(pages, claims, n=20, seed=1)  # reproducible


def test_cache_key_is_deterministic_and_input_sensitive():
    a = cache_key("judge", "anthropic", "m1", "p1", {"claim": "x", "text": "y"})
    assert a == cache_key("judge", "anthropic", "m1", "p1", {"text": "y", "claim": "x"})
    assert a != cache_key("judge", "anthropic", "m1", "p1", {"claim": "x", "text": "z"})
    assert a != cache_key("judge", "openai", "m1", "p1", {"claim": "x", "text": "y"})


def test_strip_urls_removes_links_from_note_text():
    assert strip_urls("False. See https://a.com/x and http://b.org.") == "False. See and"


def test_quote_found_ignores_whitespace_and_case_but_not_wording():
    page = "The  Senate passed\nthe bill on 3 March."
    assert quote_found("the senate passed the bill", page)
    assert quote_found("", page) is None  # nothing to check
    assert not quote_found("the house passed the bill", page)


def test_validate_verdict_rejects_unknown_labels():
    ok = {"verdict": "supports", "quote": "q", "rationale": "r"}
    assert validate_verdict(ok) == ok
    with pytest.raises(ValueError):
        validate_verdict({"verdict": "mostly", "quote": "", "rationale": ""})
    assert set(VERDICTS) == {"supports", "partial", "silent", "contradicts"}


def test_best_pages_prefers_in_window_snapshot_then_live():
    links = [{"noteId": "n1", "url": "u1"}, {"noteId": "n1", "url": "u2"}, {"noteId": "n2", "url": "u3"}]
    live = {"u1": {"state": "ok", "text": "LIVE1"}, "u2": {"state": "ok", "text": "LIVE2"},
            "u3": {"state": "blocked", "text": ""}}
    wb = {("n1", "u1"): {"state": "ok", "text": "WB1"}, ("n1", "u2"): {"state": "no_snapshot", "text": ""},
          ("n2", "u3"): {"state": "thin", "text": "x"}}
    got = {(p["noteId"], p["url"]): (p["source"], p["text"]) for p in best_pages(links, live, wb)}
    assert got == {("n1", "u1"): ("wayback", "WB1"), ("n1", "u2"): ("live", "LIVE2")}
