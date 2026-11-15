"""Fetch each cited page as it was when the note was written (Amendment 1, item 2).

Usage: uv run python -m sourced.wayback   -> data/processed/wayback.jsonl (one row per note x link, resumable)
Uses the Wayback availability API for the snapshot closest to note time, keeps it only if it falls
from 7 days before to 30 days after the note, then fetches the original bytes (id_ mode).
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pandas as pd

from sourced.fetch import UnsafeURL, domain_of, fetch_page, make_client

WINDOW_BEFORE = timedelta(days=7)
WINDOW_AFTER = timedelta(days=30)
CONCURRENCY = 4  # archive.org rate-limits hard
AVAILABLE_API = "https://archive.org/wayback/available"
OUT = Path("data/processed/wayback.jsonl")


def to_wayback_ts(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y%m%d%H%M%S")


def in_window(ts: str | None, note_ms: int) -> bool:
    if not ts:
        return False
    snap = datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    note = datetime.fromtimestamp(note_ms / 1000, tz=timezone.utc)
    return note - WINDOW_BEFORE <= snap <= note + WINDOW_AFTER


def snapshot_url(ts: str, url: str) -> str:
    return f"https://web.archive.org/web/{ts}id_/{url}"


async def _closest(client, url: str, note_ms: int) -> str | None:
    for attempt in range(3):
        try:
            resp = await client.get(AVAILABLE_API, params={"url": url, "timestamp": to_wayback_ts(note_ms)})
            if resp.status_code == 429:
                await asyncio.sleep(5 * (attempt + 1))
                continue
            snap = resp.json().get("archived_snapshots", {}).get("closest") or {}
            return snap.get("timestamp") if snap.get("available") else None
        except (httpx.HTTPError, ValueError, OSError, UnsafeURL) as exc:
            print(f"  lookup failed {url}: {type(exc).__name__}", file=sys.stderr)
            await asyncio.sleep(2)
    return None


async def _one(client, sem, note_id: str, url: str, note_ms: int) -> dict:
    async with sem:
        ts = await _closest(client, url, note_ms)
        row = {"noteId": note_id, "url": url, "snapshot_ts": ts, "in_window": in_window(ts, note_ms)}
        if row["in_window"]:
            page = await fetch_page(client, snapshot_url(ts, url), label_domain=domain_of(url))
            row.update({k: page[k] for k in ("state", "status", "error", "content_type", "text")})
        else:
            row.update({"state": "no_snapshot", "status": None, "error": None, "content_type": "", "text": ""})
        return row


async def main() -> None:
    links = pd.read_csv("data/processed/sample_links.csv", dtype={"noteId": str})
    notes = pd.read_csv("data/processed/sample_notes.csv", dtype={"noteId": str})
    todo = links.merge(notes[["noteId", "createdAtMillis"]], on="noteId")
    done = set()
    if OUT.exists():
        done = {(r["noteId"], r["url"]) for r in map(json.loads, OUT.open())}
    todo = [r for r in todo.itertuples() if (r.noteId, r.url) not in done]
    print(f"{len(done)} done, {len(todo)} to look up", file=sys.stderr)
    sem = asyncio.Semaphore(CONCURRENCY)
    async with make_client() as client:
        with OUT.open("a") as out:
            jobs = [_one(client, sem, r.noteId, r.url, int(r.createdAtMillis)) for r in todo]
            for i, coro in enumerate(asyncio.as_completed(jobs), 1):
                out.write(json.dumps(await coro) + "\n")
                out.flush()
                if i % 50 == 0:
                    print(f"  {i}/{len(todo)}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
