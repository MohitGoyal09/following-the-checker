import asyncio

import httpx
import pytest

from sourced.fetch import GuardedBackend, UnsafeURL, classify, guard_request


def test_backend_refuses_private_peer_at_connect_time():
    # simulates DNS rebinding: the name passed the pre-check, the socket lands on loopback
    async def run():
        server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            with pytest.raises(UnsafeURL):
                await GuardedBackend().connect_tcp("127.0.0.1", port)
        finally:
            server.close()
    asyncio.run(run())


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin", "http://localhost/", "http://10.0.0.5/", "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/", "http://[::1]/", "https://8.8.8.8:8443/", "ftp://8.8.8.8/",
])
def test_guard_refuses_non_public_hosts_ports_and_schemes(url):
    with pytest.raises(UnsafeURL):
        asyncio.run(guard_request(httpx.Request("GET", url)))


def test_guard_allows_public_ip_on_standard_ports():
    asyncio.run(guard_request(httpx.Request("GET", "https://8.8.8.8/")))
    asyncio.run(guard_request(httpx.Request("GET", "http://1.1.1.1:80/x")))


def test_ok_page_with_text():
    assert classify(200, 2000, None, "reuters.com") == "ok"


def test_thin_page_is_flagged():
    # paywalls and JS-only pages return 200 with almost no text
    assert classify(200, 120, None, "nytimes.com") == "thin"


def test_dead_and_blocked():
    assert classify(404, 0, None, "a.com") == "dead"
    assert classify(410, 0, None, "a.com") == "dead"
    assert classify(403, 0, None, "a.com") == "blocked"
    assert classify(429, 0, None, "a.com") == "blocked"


def test_network_error():
    assert classify(None, 0, "ConnectTimeout", "a.com") == "error"


def test_x_posts_are_not_fetchable_without_login():
    assert classify(200, 5000, None, "x.com") == "x_post"
    assert classify(200, 5000, None, "twitter.com") == "x_post"
    assert classify(200, 5000, None, "mobile.twitter.com") == "x_post"


def test_social_and_video_hosts_are_media_not_silent():
    # page text of these hosts is site chrome, not the cited content (Amendment 1, item 1)
    for d in ("youtube.com", "m.youtube.com", "youtu.be", "instagram.com", "tiktok.com",
              "facebook.com", "t.me", "reddit.com", "threads.net"):
        assert classify(200, 5000, None, d) == "media", d


def test_pdfs_are_their_own_state():
    assert classify(200, 0, None, "who.int", "application/pdf") == "pdf"
    assert classify(200, 0, None, "who.int", "application/pdf; charset=binary") == "pdf"


def test_similar_looking_domains_are_not_media():
    assert classify(200, 5000, None, "notyoutube.com") == "ok"
    assert classify(200, 5000, None, "box.com") == "ok"


def test_body_read_is_capped_before_parsing(monkeypatch):
    import asyncio

    import httpx

    from sourced import fetch

    huge = b"<html><body>" + b"a" * (fetch.MAX_BODY_BYTES * 2) + b"</body></html>"
    transport = httpx.MockTransport(lambda req: httpx.Response(200, headers={"content-type": "text/html"}, content=huge))
    seen = {}
    monkeypatch.setattr(fetch.trafilatura, "extract", lambda html, **kw: seen.setdefault("n", len(html)) and "x" * 500)

    async def go():
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch.fetch_page(client, "https://example.org/big")

    out = asyncio.run(go())
    assert seen["n"] <= fetch.MAX_BODY_BYTES
    assert out["state"] == "ok" and out["error"] is None
