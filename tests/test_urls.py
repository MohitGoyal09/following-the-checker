from sourced.urls import extract_urls


def test_extracts_plain_urls_in_order():
    text = "Claim is false. https://a.com/x and http://b.org/y?z=1"
    assert extract_urls(text) == ["https://a.com/x", "http://b.org/y?z=1"]


def test_strips_trailing_sentence_punctuation():
    text = "See https://a.com/report. Also (https://b.com/page), and https://c.com/q?!"
    assert extract_urls(text) == ["https://a.com/report", "https://b.com/page", "https://c.com/q"]


def test_keeps_balanced_parentheses_inside_url():
    text = "Per https://en.wikipedia.org/wiki/Foo_(bar) the claim fails."
    assert extract_urls(text) == ["https://en.wikipedia.org/wiki/Foo_(bar)"]


def test_deduplicates_and_handles_empty():
    assert extract_urls("https://a.com https://a.com") == ["https://a.com"]
    assert extract_urls("") == []
    assert extract_urls(None) == []
