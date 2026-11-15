"""Study B (gate 3): do LLM readers rely on a Helpful-labelled note whatever its sources show? (Amendments 3, 5)

Usage: uv run python -m sourced.study_b [--limit N]  -> data/processed/study_b_responses.csv
"""

import argparse
import asyncio
import json
import sys

import anthropic
import numpy as np
import pandas as pd
from google import genai
from google.genai import errors, types

from sourced.judge_common import CallLog, cache_key, load_prompt

P = "data/processed/"
CONDITIONS = ("a", "b", "c", "d", "e", "f", "g", "h")  # e, f = c, d + the passage (Amendment 6); g, h: Amendment 8
PLACEBO_SEED = 45
EXCERPT_CHARS = 1200
MODELS = ("claude-opus-5-5", "claude-haiku-5-5", "gemini-3.8-flash")
FALLBACK_MODELS = {"claude-opus-5-5"}  # Haiku 5.5 has no server-side fallback
SEED = 42
CONCURRENCY = 8
LABEL_LINE = "Community Notes label: Rated helpful by people from different perspectives."
SCHEMA_VERSION = 2  # v1 had integer bounds (rejected by Claude); part of the cache key
SCHEMA = {
    "type": "object",
    # Claude structured outputs reject min/max on integers; the 0-100 range is stated in the prompt and
    # enforced in valid_confidence() (out-of-range -> missing, never clipped). Same schema for every model.
    "properties": {"answer": {"type": "string", "enum": ["yes", "no", "unsure"]},
                   "confidence": {"type": "integer"}},
    "required": ["answer", "confidence"],
    "additionalProperties": False,
}


def excerpt(text: str, quote: str, width: int = EXCERPT_CHARS) -> str:
    """Window of `width` chars centred on the judge's quote if it is in the page, else the page start."""
    pos = text.lower().find(quote.strip().lower()[:80]) if quote and quote.strip() else -1
    if pos < 0:
        return text[:width]
    start = max(0, min(pos - width // 2 + len(quote) // 2, len(text) - width))
    return text[start:start + width]


def build_message(note: str, claim: str, condition: str, truth: str,
                  evidence: tuple[str, str] | None = None) -> str:
    if condition == "g":  # Amendment 8: claim only, no note
        return "\n".join(["No Community Note is shown for this post.", "",
                          "QUESTION: Is the following statement true?", f"STATEMENT: {claim}"])
    lines = ["A post on a social media platform has this Community Note attached:", "", f"NOTE: {note}"]
    if condition in ("b", "c", "d", "e", "f", "h"):
        lines.append(LABEL_LINE)
    if condition in ("c", "d", "e", "f", "h"):
        says_supported = (truth == "supported") == (condition in ("c", "e"))
        verb = "DO support" if says_supported else "DO NOT support"
        lines.append("Source-check tool (a separate service that opened the note's cited pages): "
                     f"The cited sources {verb} the note's claim.")
    if condition in ("e", "f", "h"):  # h: placebo passage from another item (Amendment 8)
        url, passage = evidence
        lines.append(f'Passage the tool checked (from {url}): "{passage}"')
    lines += ["", "QUESTION: Is the following statement true?", f"STATEMENT: {claim}"]
    return "\n".join(lines)


def valid_confidence(x) -> int | None:
    return x if isinstance(x, int) and 0 <= x <= 100 else None


def note_labels(verdicts: pd.DataFrame) -> pd.Series:
    return verdicts.groupby("noteId").verdict.apply(lambda s: "supported" if (s == "supports").any() else "unsupported")


def select_items(labels: pd.DataFrame, n_per_label: int, seed: int) -> pd.DataFrame:
    agreed = labels[(labels.c == labels.g) & (labels.stratum == "helpful_pair")].sort_values("noteId")
    unsup = agreed[agreed.c == "unsupported"]
    half = n_per_label // 2
    unsup = pd.concat([g.sample(n=min(half, len(g)), random_state=seed) for _, g in unsup.groupby("ai")])
    sup = agreed[agreed.c == "supported"]
    sup = sup.sample(n=min(n_per_label, len(sup)), random_state=seed)
    items = pd.concat([sup, unsup]).assign(truth=lambda d: d.c)
    return items[["noteId", "ai", "truth"]].reset_index(drop=True)


async def ask_claude(client, model: str, system: str, text: str) -> tuple[dict | None, dict]:
    extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} if model in FALLBACK_MODELS else {}
    resp = await client.beta.messages.create(
        model=model, max_tokens=16000, system=system, messages=[{"role": "user", "content": text}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}}, **extra)
    fallback = any(getattr(it, "type", "") == "fallback_message" for it in (resp.usage.iterations or []))
    out = None
    if resp.stop_reason not in ("refusal", "max_tokens"):
        out = json.loads(next(b.text for b in resp.content if b.type == "text"))
    return out, {"model_served": resp.model, "served_by_fallback": fallback, "stop_reason": resp.stop_reason,
                 "usage": {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens},
                 "request_id": resp._request_id}


async def ask_gemini(client, model: str, system: str, text: str) -> tuple[dict | None, dict]:
    config = types.GenerateContentConfig(system_instruction=system, temperature=0, seed=SEED,
                                         response_mime_type="application/json", response_json_schema=SCHEMA)
    for attempt in range(4):
        try:
            resp = await client.aio.models.generate_content(model=model, contents=text, config=config)
            break
        except errors.APIError as exc:
            if exc.code in (429, 500, 503) and attempt < 3:
                await asyncio.sleep(5 * 2 ** attempt)
                continue
            raise
    finish = resp.candidates[0].finish_reason.name if resp.candidates else "NO_CANDIDATE"
    out = json.loads(resp.text) if finish == "STOP" and resp.text else None
    u = resp.usage_metadata
    return out, {"model_served": resp.model_version or model, "served_by_fallback": False, "stop_reason": finish,
                 "usage": {"input": u.prompt_token_count, "output": u.candidates_token_count},
                 "request_id": resp.response_id}


def placebo_pairs(items: pd.DataFrame, tweets: pd.Series, seed: int = PLACEBO_SEED) -> dict:
    """Amendment 8: one random derangement of the items that never pairs two items from the same post."""
    ids = sorted(items.noteId)
    rng = np.random.default_rng(seed)
    while True:
        perm = rng.permutation(ids)
        if all(a != b and tweets[a] != tweets[b] for a, b in zip(ids, perm)):
            return dict(zip(ids, perm))


def build_evidence(note_ids: set) -> dict:
    """Amendment 6: first judged page of each note (cited order), window around a quote verified in the page
    (Claude judge first, then Gemini), else the page start."""
    from sourced.judge_common import judge_items

    quotes = {}
    for model in ("gemini-3.8-flash", "claude-opus-5-5"):  # Claude written last, so it wins
        v = pd.read_csv(P + f"verdicts_{model}.csv", dtype={"noteId": str})
        for r in v[v.quote_found.astype(str).eq("True")].itertuples():
            quotes[(r.noteId, r.url)] = r.quote
    evidence = {}
    for page in judge_items(P):
        nid = page["noteId"]
        if nid in note_ids and nid not in evidence:
            evidence[nid] = (page["url"], excerpt(page["text"], quotes.get((nid, page["url"]), "")))
    return evidence


async def run(limit: int | None) -> None:
    notes = pd.read_csv(P + "sample_notes.csv", dtype={"noteId": str}).set_index("noteId")
    claims = pd.read_csv(P + "claims.csv", dtype={"noteId": str}).set_index("noteId").claim
    labels = pd.DataFrame({
        "c": note_labels(pd.read_csv(P + "verdicts_claude-opus-5-5.csv", dtype={"noteId": str})),
        "g": note_labels(pd.read_csv(P + "verdicts_gemini-3.8-flash.csv", dtype={"noteId": str})),
    }).dropna().join(notes[["ai", "stratum"]]).reset_index(names="noteId")
    items = select_items(labels, 40, SEED).head(limit)
    items.to_csv(P + "study_b_items.csv", index=False)
    evidence = build_evidence(set(items.noteId))
    tweets = pd.read_csv(P + "sample_notes.csv", dtype={"noteId": str, "tweetId": str}).set_index("noteId").tweetId
    placebo = placebo_pairs(items, tweets)
    system, prompt_sha = load_prompt("study_b_reader")
    log, sem = CallLog(), asyncio.Semaphore(CONCURRENCY)
    gem = genai.Client()

    async with anthropic.AsyncAnthropic() as claude:
        async def one(it, cond, model):
            ev = evidence.get(placebo[it.noteId] if cond == "h" else it.noteId)
            text = build_message(notes.loc[it.noteId, "summary"], claims[it.noteId], cond, it.truth, ev)
            payload = {"noteId": it.noteId, "condition": cond, "truth": it.truth, "schema": SCHEMA_VERSION}
            key = cache_key("study_b", model, model, prompt_sha, payload)
            if (hit := log.get(key)) is None:
                async with sem:
                    try:
                        out, meta = await (ask_gemini(gem, model, system, text) if model.startswith("gemini")
                                           else ask_claude(claude, model, system, text))
                    except (anthropic.APIStatusError, errors.APIError) as exc:
                        print(f"  failed {model} {payload}: {exc}", file=sys.stderr)
                        return None
                hit = {"key": key, "task": "study_b", "provider": model.split("-")[0], "model_requested": model,
                       "prompt_sha": prompt_sha, "payload": payload, "output": out, **meta}
                log.add(hit)
            o = hit["output"] or {}
            return {"noteId": it.noteId, "ai": it.ai, "truth": it.truth, "condition": cond, "model": model,
                    "answer": o.get("answer"), "confidence": valid_confidence(o.get("confidence")),
                    "rely": o.get("answer") == "yes",
                    "fallback": hit.get("served_by_fallback"), "stop_reason": hit.get("stop_reason")}

        rows = await asyncio.gather(*[one(it, c, m) for it in items.itertuples() for c in CONDITIONS for m in MODELS])
    df = pd.DataFrame([r for r in rows if r])
    df.to_csv(P + "study_b_responses.csv", index=False)
    print(f"{len(df)} responses; items {len(items)} (supported by writer type: "
          f"{items[items.truth == 'supported'].ai.value_counts().to_dict()}); "
          f"null answers {df.answer.isna().sum()}; fallback {int(df.fallback.fillna(False).sum())}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="number of items (dry run)")
    asyncio.run(run(ap.parse_args().limit))
