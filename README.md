# Following the Checker: How AI Readers Use Source-Check Verdicts on Community Notes

Mohit Goyal and Ananya Bhattacharya. Apart Research AI x Epistemics Research Sprint, November 2026 (Track 2: Trust Infrastructure; Track 4: Open).

**Report:** [paper/report.pdf](paper/report.pdf) (source: [paper/report.md](paper/report.md))

## Summary

Community Notes checks whether a note *looks* sourced (its links load, raters tick "cites high-quality sources", readers see "Rated helpful"), not whether the cited page supports the claim. A source-check tool could tell readers, but its verdict can itself be wrong.

- **Study B.** Three chat LLMs (Claude Opus 5.5, Claude Haiku 5.5, Gemini 3.8 Flash) read 80 real Helpful notes with right or wrong source-check verdicts, with and without the passage the tool checked (1,920 answers). With a verdict only, the readers inherited the checker's errors. Adding the checked passage cut dependence on the verdict by 26–51 points in all three models, but the protection was one-sided: readers rejected false alarms and rarely false assurances.
- **Study A.** A page-level check of 200 paired AI-written and human-written Helpful notes: 52–56% (human labels) to 68% (LLM judge) of readable cited pages do not fully support the note's claim, with no detectable difference between AI and human notes.

All numbers, intervals, tests and limitations are in the report.

## Repository

| Path | Contents |
| --- | --- |
| `paper/` | Report (Markdown source and PDF), figure script, PDF build script and LaTeX template |
| `sourced/` | Pipeline and analysis code (sampling, fetching, judging, Study A, Study B, robustness checks) |
| `prompts/` | Claim-extraction, judge and reader prompts |
| `tests/` | Unit tests (`uv run pytest -q`) |
| `results/` | Every number in the report as JSON, plus figures and the data manifest (snapshot file hashes) |
| `data/processed/` | Sample, extracted claims, judge verdicts, Study B responses, human labels and label keys |
| `PREREGISTRATION.md` | Hypotheses, definitions and analyses, with eight dated amendments |

## Reproduce

```bash
uv sync
uv run pytest -q
```

The analyses run from the committed files without model calls:

```bash
uv run python -m sourced.study_a
uv run python -m sourced.gold_analysis
uv run python -m sourced.study_b_analysis
uv run python -m sourced.study_b_robustness
uv run python -m sourced.study_b_amend8
uv run python -m sourced.review_fixes
uv run python paper/make_figures.py
uv run python paper/build_pdf.py   # needs pandoc and xelatex
```

Rebuilding the data from scratch needs the public Community Notes snapshot of Nov 15, 2026 (`https://ton.twimg.com/birdwatch-public-data/2026/11/15/<table>/<table>-00000.zip`) in `data/raw/`, and `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` for the model calls. In order: `sourced.sample`, `sourced.fetch`, `sourced.wayback`, `sourced.judge_claude claims`, `sourced.judge_claude judge`, `sourced.judge_gemini`, `sourced.study_b`, `sourced.ratings`, `sourced.tag_drift`, `sourced.c8_analysis`. Some steps need page text, which is not published (see below).

## Data and ethics

- Built only from the public Community Notes data release. We publish note IDs, extracted claims, labels and aggregate results; no participant IDs. AI writers appear only as anonymous ranks.
- We do not republish the text of cited third-party pages or the raw snapshot. Analyses that need page text (judging, Study B prompts, labelling pages) can be rebuilt with the fetch scripts.
- We posted nothing to X or Community Notes.

## Notes

- **Preexisting code:** none. All code was written during the sprint.
- **LLM use:** described in the report's LLM Usage Statement.
- **Licence:** code under the MIT licence (`LICENSE`). Community Notes data remain subject to X's terms.
