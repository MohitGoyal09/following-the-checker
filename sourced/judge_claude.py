"""Claude calls: claim extraction and support judging (Anthropic Python SDK).

Usage:
  uv run python -m sourced.judge_claude claims  [--limit N]
  uv run python -m sourced.judge_claude judge   [--model claude-opus-5-5] [--limit N]
Every call is logged in data/processed/llm_calls.jsonl and reused on reruns.
Sampling params (temperature) are not accepted by current Claude models; model ID + effort are recorded.
"""

import argparse
import asyncio
import json
import sys

import anthropic
import pandas as pd

from sourced.judge_common import (
    CLAIM_SCHEMA, VERDICT_SCHEMA, CallLog, cache_key, judge_items, load_prompt, strip_urls, verdict_rows,
)

PROVIDER = "anthropic"
CLAIM_MODEL = "claude-opus-5-5"
JUDGE_MODEL = "claude-opus-5-5"
EFFORT = {"claim": "medium", "judge": "high"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"
CONCURRENCY = 8
P = "data/processed/"


async def call(client, log: CallLog, sem, task: str, model: str, prompt: tuple[str, str],
               payload: dict, user_text: str, schema: dict) -> dict:
    system, prompt_sha = prompt
    key = cache_key(task, PROVIDER, model, prompt_sha, payload)
    if (hit := log.get(key)) is not None:
        return hit
    async with sem:
        try:
            resp = await client.beta.messages.create(
                model=model, max_tokens=16000, system=system,
                messages=[{"role": "user", "content": user_text}],
                output_config={"effort": EFFORT[task], "format": {"type": "json_schema", "schema": schema}},
                betas=[FALLBACK_BETA], fallbacks="default",
            )
        except anthropic.APIStatusError as exc:
            print(f"  {task} failed {exc.status_code}: {payload}", file=sys.stderr)
            return {"key": key, "output": None, "error": exc.status_code}
    served_fallback = any(getattr(it, "type", "") == "fallback_message" for it in (resp.usage.iterations or []))
    output = None
    if resp.stop_reason not in ("refusal", "max_tokens"):
        output = json.loads(next(b.text for b in resp.content if b.type == "text"))
    row = {
        "key": key, "task": task, "provider": PROVIDER, "model_requested": model, "model_served": resp.model,
        "served_by_fallback": served_fallback, "prompt_sha": prompt_sha, "effort": EFFORT[task],
        "payload": payload, "stop_reason": resp.stop_reason, "output": output,
        "usage": {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens},
        "request_id": resp._request_id,
    }
    log.add(row)
    return row


async def run_claims(limit: int | None) -> None:
    notes = pd.read_csv(P + "sample_notes.csv", dtype={"noteId": str}).head(limit)
    log, sem, prompt = CallLog(), asyncio.Semaphore(CONCURRENCY), load_prompt("claim_extract")
    async with anthropic.AsyncAnthropic() as client:
        rows = await asyncio.gather(*[
            call(client, log, sem, "claim", CLAIM_MODEL, prompt, {"noteId": n.noteId},
                 strip_urls(n.summary), CLAIM_SCHEMA)
            for n in notes.itertuples()
        ])
    out = pd.DataFrame([{"noteId": n.noteId, **(r["output"] or {"claim": None, "language": None}),
                         "claim_fallback": r.get("served_by_fallback")} for n, r in zip(notes.itertuples(), rows)])
    out.to_csv(P + "claims.csv", index=False)
    print(f"{out.claim.notna().sum()}/{len(out)} claims -> {P}claims.csv")


async def run_judge(model: str, limit: int | None, audit: bool = False) -> None:
    items = judge_items(P, limit, audit)
    log, sem, prompt = CallLog(), asyncio.Semaphore(CONCURRENCY), load_prompt("judge_support")
    async with anthropic.AsyncAnthropic() as client:
        rows = await asyncio.gather(*[
            call(client, log, sem, "judge", model, prompt, it["payload"], it["message"], VERDICT_SCHEMA)
            for it in items
        ])
    df = pd.DataFrame(verdict_rows(items, rows))
    df.to_csv(P + f"verdicts_{'audit_' if audit else ''}{model}.csv", index=False)
    print(f"{len(df)} items;", df.verdict.value_counts(dropna=False).to_dict())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["claims", "judge"])
    ap.add_argument("--model", default=JUDGE_MODEL)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--audit", action="store_true", help="memory audit on mismatched claim-page pairs")
    a = ap.parse_args()
    asyncio.run(run_claims(a.limit) if a.step == "claims" else run_judge(a.model, a.limit, a.audit))
