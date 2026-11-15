"""Second judge from a different model family (Google Gemini), same prompt and schema as the Claude judge.

Usage: uv run python -m sourced.judge_gemini [--model gemini-3.8-flash] [--limit N]
Gemini accepts sampling params, so this judge runs at temperature 0 with a fixed seed.
"""

import argparse
import asyncio
import json
import sys

import pandas as pd
from google import genai
from google.genai import errors, types

from sourced.judge_common import (
    VERDICT_SCHEMA, CallLog, cache_key, judge_items, load_prompt, verdict_rows,
)

PROVIDER = "google"
JUDGE_MODEL = "gemini-3.8-flash"
THINKING_LEVEL = "high"
SEED = 42
CONCURRENCY = 8
P = "data/processed/"


async def call(client, log: CallLog, sem, model: str, prompt: tuple[str, str], payload: dict, user_text: str) -> dict:
    system, prompt_sha = prompt
    key = cache_key("judge", PROVIDER, model, prompt_sha, payload)
    if (hit := log.get(key)) is not None:
        return hit
    config = types.GenerateContentConfig(
        system_instruction=system, temperature=0, seed=SEED,
        response_mime_type="application/json", response_json_schema=VERDICT_SCHEMA,
        thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
    )
    async with sem:
        for attempt in range(4):
            try:
                resp = await client.aio.models.generate_content(model=model, contents=user_text, config=config)
                break
            except errors.APIError as exc:
                if exc.code in (429, 500, 503) and attempt < 3:
                    await asyncio.sleep(5 * 2 ** attempt)
                    continue
                print(f"  judge failed {exc.code}: {payload}", file=sys.stderr)
                return {"key": key, "output": None, "error": exc.code}
    finish = resp.candidates[0].finish_reason.name if resp.candidates else "NO_CANDIDATE"
    output = json.loads(resp.text) if finish == "STOP" and resp.text else None
    usage = resp.usage_metadata
    row = {
        "key": key, "task": "judge", "provider": PROVIDER, "model_requested": model,
        "model_served": resp.model_version or model, "served_by_fallback": False, "prompt_sha": prompt_sha,
        "params": {"temperature": 0, "seed": SEED, "thinking_level": THINKING_LEVEL},
        "payload": payload, "stop_reason": finish, "output": output,
        "usage": {"input": usage.prompt_token_count, "output": usage.candidates_token_count},
        "request_id": resp.response_id,
    }
    log.add(row)
    return row


async def run_judge(model: str, limit: int | None, audit: bool = False) -> None:
    items = judge_items(P, limit, audit)
    log, sem, prompt = CallLog(), asyncio.Semaphore(CONCURRENCY), load_prompt("judge_support")
    client = genai.Client()
    rows = await asyncio.gather(*[call(client, log, sem, model, prompt, it["payload"], it["message"]) for it in items])
    df = pd.DataFrame(verdict_rows(items, rows))
    df.to_csv(P + f"verdicts_{'audit_' if audit else ''}{model}.csv", index=False)
    print(f"{len(df)} items;", df.verdict.value_counts(dropna=False).to_dict())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=JUDGE_MODEL)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--audit", action="store_true", help="memory audit on mismatched claim-page pairs")
    a = ap.parse_args()
    asyncio.run(run_judge(a.model, a.limit, a.audit))
