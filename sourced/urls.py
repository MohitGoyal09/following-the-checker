"""Pull cited URLs out of Community Note text."""

import re

_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING = ".,;:!?'\"]}>"


def _clean(url: str) -> str:
    while url:
        if url[-1] in _TRAILING:
            url = url[:-1]
        elif url[-1] == ")" and url.count(")") > url.count("("):
            url = url[:-1]
        else:
            break
    return url


def extract_urls(text: str | None) -> list[str]:
    """Return unique http(s) URLs in the order they appear."""
    if not text:
        return []
    seen: dict[str, None] = {}
    for match in _URL.findall(text):
        url = _clean(match)
        if url:
            seen.setdefault(url, None)
    return list(seen)
