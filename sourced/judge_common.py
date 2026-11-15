"""Provider-neutral pieces of the judging step: prompts, schemas, page choice, call log."""

import hashlib
import json
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from sourced.urls import _URL

PROMPTS = Path("prompts")
CALL_LOG = Path("data/processed/llm_calls.jsonl")
VERDICTS = ("supports", "partial", "silent", "contradicts")

CLAIM_SCHEMA = {
    "type": "object",
    "properties": {"claim": {"type": "string"}, "language": {"type": "string"}},
    "required": ["claim", "language"],
    "additionalProperties": False,
}
VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "quote": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": ["verdict", "quote", "rationale"],
    "additionalProperties": False,
}


def load_prompt(name: str) -> tuple[str, str]:
    text = (PROMPTS / f"{name}.md").read_text()
    return text, hashlib.sha256(text.encode()).hexdigest()[:16]


def cache_key(task: str, provider: str, model: str, prompt_sha: str, payload: dict) -> str:
    blob = json.dumps([task, provider, model, prompt_sha, payload], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def strip_urls(text: str) -> str:
    return re.sub(r"\s+", " ", _URL.sub("", text or "")).strip(" .")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_found(quote: str, page_text: str) -> bool | None:
    """Is the judge's quote really in the page? None when there is no quote to check."""
    if not quote.strip():
        return None
    return _norm(quote).strip(" .\"'…") in _norm(page_text)


def validate_verdict(out: dict) -> dict:
    if out.get("verdict") not in VERDICTS:
        raise ValueError(f"bad verdict: {out.get('verdict')!r}")
    return out


def best_pages(links: Iterable[dict], live: dict, wayback: dict) -> list[dict]:
    """Amendment 1, item 2: the in-window Wayback copy if readable, else the live page if readable."""
    pages = []
    for link in links:
        note_id, url = link["noteId"], link["url"]
        wb, lv = wayback.get((note_id, url), {}), live.get(url, {})
        if wb.get("state") == "ok":
            pages.append({"noteId": note_id, "url": url, "source": "wayback", "text": wb["text"]})
        elif lv.get("state") == "ok":
            pages.append({"noteId": note_id, "url": url, "source": "live", "text": lv["text"]})
    return pages


def load_pages(processed: str = "data/processed/") -> list[dict]:
    import pandas as pd

    links = pd.read_csv(processed + "sample_links.csv", dtype={"noteId": str}).to_dict("records")
    live = {r["url"]: r for r in map(json.loads, open(processed + "links.jsonl"))}
    wb = {(r["noteId"], r["url"]): r for r in map(json.loads, open(processed + "wayback.jsonl"))}
    return best_pages(links, live, wb)


def judge_inputs(processed: str = "data/processed/", limit: int | None = None) -> tuple[list[dict], dict]:
    """Pages to judge (only notes with an extracted claim) and the claim per note."""
    import pandas as pd

    claims = pd.read_csv(processed + "claims.csv", dtype={"noteId": str}).set_index("noteId").claim.dropna().to_dict()
    pages = [p for p in load_pages(processed) if p["noteId"] in claims][:limit]
    return pages, claims


def memory_audit_pairs(pages: list[dict], claims: dict, n: int = 60, seed: int = 42) -> list[dict]:
    """Amendment 3, C.2: pair a page with the claim of a *different* note. A judge that answers
    anything but 'silent' here is labelling from memory, not from the page."""
    import random

    rng = random.Random(seed)
    note_ids = sorted(claims)
    chosen = rng.sample(pages, min(n, len(pages)))
    pairs = []
    for p in chosen:
        other = rng.choice([nid for nid in note_ids if nid != p["noteId"]])
        pairs.append({**p, "claimNoteId": other, "claim": claims[other]})
    return pairs


def judge_message(claim: str, text: str) -> str:
    return f"CLAIM:\n{claim}\n\nTEXT:\n{text}"


def judge_items(processed: str = "data/processed/", limit: int | None = None, audit: bool = False) -> list[dict]:
    """Each item: the page fields plus the payload (cache identity) and the message to send."""
    pages, claims = judge_inputs(processed, None if audit else limit)
    if audit:
        items = memory_audit_pairs(pages, claims)[:limit]
    else:
        items = [{**p, "claimNoteId": p["noteId"], "claim": claims[p["noteId"]]} for p in pages]
    for it in items:
        it["payload"] = {"noteId": it["noteId"], "url": it["url"], "source": it["source"],
                         **({"audit": True, "claimNoteId": it["claimNoteId"]} if audit else {})}
        it["message"] = judge_message(it["claim"], it["text"])
    return items


def verdict_rows(pages: list[dict], rows: list[dict]) -> list[dict]:
    out = []
    for p, r in zip(pages, rows):
        v = validate_verdict(r["output"]) if r.get("output") else {"verdict": None, "quote": "", "rationale": ""}
        out.append({"noteId": p["noteId"], "url": p["url"], "source": p["source"],
                    "claimNoteId": p.get("claimNoteId", p["noteId"]), **v,
                    "quote_found": quote_found(v["quote"], p["text"]), "fallback": r.get("served_by_fallback")})
    return out


class CallLog:
    """Append-only record of every model call; doubles as a cache so reruns cost nothing."""

    def __init__(self, path: Path = CALL_LOG):
        self.path = path
        self.done = {}
        if path.exists():
            for line in path.open():
                row = json.loads(line)
                self.done[row["key"]] = row

    def get(self, key: str) -> dict | None:
        return self.done.get(key)

    def add(self, row: dict) -> None:
        row = {**row, "logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self.done[row["key"]] = row
        with self.path.open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
