"""Fetch cited URLs and keep the readable text of each page.

Usage: uv run python -m sourced.fetch data/processed/sample_links.csv data/processed/links.jsonl
Resumable: URLs already in the output file are skipped.
"""

import asyncio
import ipaddress
import json
import sys
import zlib
from pathlib import Path
from urllib.parse import urlparse

import httpcore
import httpx
import pandas as pd
import trafilatura

MIN_TEXT_CHARS = 300  # below this a 200 page is treated as thin (paywall, JS shell, cookie wall)
MAX_TEXT_CHARS = 20_000
MAX_BODY_BYTES = 5_000_000  # cap on the decompressed HTML read per URL (untrusted servers)
DEADLINE_S = 45  # whole-request deadline per URL, redirects and body included
ACCEPT_ENCODING = "gzip, deflate"  # only encodings we can decompress with a hard output limit
CONCURRENCY = 16
TIMEOUT_S = 20
USER_AGENT = "Mozilla/5.0 (research link checker)"
X_DOMAINS = ("x.com", "twitter.com")
MEDIA_DOMAINS = ("youtube.com", "youtu.be", "instagram.com", "tiktok.com", "facebook.com",
                 "fb.watch", "t.me", "reddit.com", "threads.net")
ALLOWED_PORTS = {"http": 80, "https": 443}
UNJUDGEABLE = {"x_post", "media", "pdf", "thin", "blocked", "dead", "error"}


def host_in(domain: str, suffixes: tuple[str, ...]) -> bool:
    """Dot-boundary suffix match: 'm.youtube.com' is youtube, 'box.com' is not x.com."""
    return any(domain == s or domain.endswith("." + s) for s in suffixes)


class UnsafeURL(Exception):
    """URL points at a non-public address, port or scheme (SSRF guard)."""


def _require_global(ip: str, host: str) -> None:
    if not ipaddress.ip_address(ip.split("%")[0]).is_global:
        raise UnsafeURL(f"non-public address for {host}")


async def guard_request(request: httpx.Request) -> None:
    """Runs before every request, redirect hops included. URLs come from untrusted note text."""
    url = request.url
    if url.scheme not in ALLOWED_PORTS or (url.port or ALLOWED_PORTS[url.scheme]) != ALLOWED_PORTS[url.scheme]:
        raise UnsafeURL(f"scheme/port not allowed: {url}")
    host = url.raw_host.decode("ascii").strip("[]")  # the exact bytes httpx will connect to
    for *_, sockaddr in await asyncio.get_running_loop().getaddrinfo(host, None):
        _require_global(sockaddr[0], host)


class GuardedBackend(httpcore.AnyIOBackend):
    """Checks the socket's real peer right after TCP connect, before TLS or any HTTP bytes.

    Closes the DNS-rebinding gap left by guard_request (which resolves separately). Fails closed.
    """

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        stream = await super().connect_tcp(host, port, timeout, local_address, socket_options)
        peer = stream.get_extra_info("server_addr")
        try:
            if not peer:
                raise UnsafeURL(f"peer address unknown for {host!r}")
            _require_global(peer[0], repr(host))
        except UnsafeURL:
            await stream.aclose()
            raise
        return stream


def guarded_transport(limits: httpx.Limits) -> httpx.AsyncHTTPTransport:
    transport = httpx.AsyncHTTPTransport(limits=limits)
    transport._pool._network_backend = GuardedBackend()  # httpx exposes no public hook; pinned by uv.lock
    return transport


async def read_capped(resp: httpx.Response, cap: int = MAX_BODY_BYTES) -> bytes:
    """Read at most `cap` bytes of body, bounding memory before decompression (no zip bombs).

    Raw bytes are read and inflated here with a hard output limit; stacked or unknown encodings are refused.
    """
    enc = resp.headers.get("content-encoding", "identity").strip().lower()
    if enc in ("", "identity"):
        inflater = None
    elif enc in ("gzip", "x-gzip", "deflate"):
        inflater = zlib.decompressobj(32 + zlib.MAX_WBITS)  # auto-detects gzip or zlib headers
    else:
        raise ValueError(f"unsupported content-encoding: {enc!r}")
    out, raw = bytearray(), 0
    async for chunk in resp.aiter_raw():
        raw += len(chunk)
        if inflater is None:
            out += chunk[: cap - len(out)]
        else:
            buf = chunk
            while buf and len(out) < cap:
                out += inflater.decompress(buf, cap - len(out))
                buf = inflater.unconsumed_tail
        if len(out) >= cap or raw >= cap:
            break
    return bytes(out)


def domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host.removeprefix("www.")


def classify(status: int | None, text_len: int, error: str | None, domain: str,
             content_type: str = "") -> str:
    if host_in(domain, X_DOMAINS):
        return "x_post"
    if host_in(domain, MEDIA_DOMAINS):
        return "media"
    if error or status is None:
        return "error"
    if status in (404, 410):
        return "dead"
    if status in (401, 403, 429, 451) or status >= 500:
        return "blocked"
    if status >= 400:
        return "dead"
    if "pdf" in content_type.lower():
        return "pdf"
    return "ok" if text_len >= MIN_TEXT_CHARS else "thin"


async def fetch_page(client: httpx.AsyncClient, url: str, label_domain: str | None = None) -> dict:
    """GET one URL and classify it. label_domain overrides the domain used for the state
    (a Wayback copy of a YouTube page is still media)."""
    domain = label_domain or domain_of(url)
    if host_in(domain, X_DOMAINS + MEDIA_DOMAINS):
        return {"url": url, "domain": domain, "state": classify(None, 0, None, domain), "status": None,
                "final_url": url, "error": None, "content_type": "", "text": ""}
    status, final_url, error, text, ctype = None, url, None, "", ""
    try:
        async with asyncio.timeout(DEADLINE_S), client.stream("GET", url, headers={"Accept-Encoding": ACCEPT_ENCODING}) as resp:
            status, final_url = resp.status_code, str(resp.url)
            ctype = resp.headers.get("content-type", "")
            if resp.status_code < 400 and "html" in ctype:
                html = (await read_capped(resp)).decode(resp.encoding or "utf-8", errors="replace")
                text = trafilatura.extract(html, include_comments=False) or ""
    except (httpx.HTTPError, ValueError, OSError, UnsafeURL, zlib.error) as exc:  # TimeoutError is an OSError
        error = type(exc).__name__
    text = text[:MAX_TEXT_CHARS]
    return {"url": url, "domain": label_domain or domain_of(final_url),
            "state": classify(status, len(text), error, domain, ctype),
            "status": status, "final_url": final_url, "error": error, "content_type": ctype, "text": text}


async def _fetch_one(client: httpx.AsyncClient, url: str) -> dict:
    return await fetch_page(client, url)


def make_client() -> httpx.AsyncClient:
    limits = httpx.Limits(max_connections=CONCURRENCY)
    return httpx.AsyncClient(follow_redirects=True, timeout=TIMEOUT_S, transport=guarded_transport(limits),
                             headers={"User-Agent": USER_AGENT, "Accept-Encoding": ACCEPT_ENCODING}, event_hooks={"request": [guard_request]})


async def fetch_all(urls: list[str], out_path: Path) -> None:
    done = set()
    if out_path.exists():
        done = {json.loads(line)["url"] for line in out_path.open()}
    todo = [u for u in dict.fromkeys(urls) if u not in done]
    print(f"{len(done)} done, {len(todo)} to fetch", file=sys.stderr)
    sem = asyncio.Semaphore(CONCURRENCY)
    async with make_client() as client:
        async def run(url: str) -> dict:
            async with sem:
                return await _fetch_one(client, url)

        with out_path.open("a") as out:
            for i, coro in enumerate(asyncio.as_completed([run(u) for u in todo]), 1):
                out.write(json.dumps(await coro) + "\n")
                if i % 50 == 0:
                    print(f"  {i}/{len(todo)}", file=sys.stderr)


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    asyncio.run(fetch_all(pd.read_csv(src)["url"].tolist(), dst))
