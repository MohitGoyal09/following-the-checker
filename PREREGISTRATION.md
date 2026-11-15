# Preregistration: Looks Sourced, or Is Sourced?

> **Public release note.** This file is reproduced verbatim from the authors' development repository. That repository's git commit times, which the file treats as authoritative for when each amendment was fixed, can be shared with the sprint organisers on request. Links to internal working documents (the lab notebook and `docs/`) are not part of this release.

Written Nov 15, 2026, 12:45 IST, **before any link was judged and before any Study B model call**. The git commit that adds this file is its timestamp. Any later change goes in the Amendments section at the end, with its time and reason. The original text stays as written.

## What we had already seen when we wrote this

We disclose this so a reader can judge whether it shaped the plan.

- **Counts in the snapshot:** 41 AI writer accounts; 376,299 AI notes since Sep 1, 2025; 58,214 tweets with both an AI note and a human note; 4,421 tweets where both are "Currently Rated Helpful" (CRH).
- **Link counts per note:** every AI note in the paired data has at least one URL (mean 2.2). Of human notes, 83% have one (mean 1.25).
- **Fetch states of the 443 sampled links** (ok / X post / blocked / thin / dead / error), by stratum and writer type. See [NOTEBOOK.md](NOTEBOOK.md).
- **Not seen:** no support labels, no judge output, and no Study B output.

## Data and sample

- **Source:** the Community Notes public snapshot of Nov 15, 2026. Files and SHA-256 hashes are in [results/data_manifest.json](results/data_manifest.json).
- **AI writer:** a participant whose `enrollmentState` is `apiEarnedIn`. Every other note is a human note.
- **Scope:** notes created on or after Sep 1, 2025. Collaborative notes are left out. Only tweets that have at least one AI note and one human note are used.
- **Strata (seed 42), built by [sourced/sample.py](sourced/sample.py):**
  - **Helpful pairs:** 100 tweets, drawn at random from tweets where both an AI note and a human note are CRH. From each tweet, one random CRH AI note and one random CRH human note.
  - **Not-helpful contrast:** 50 AI notes and 50 human notes with status "Currently Rated Not Helpful" (CRNH), drawn from paired tweets.
- **Links:** at most the first 5 URLs per note.
- **Language:** notes in all languages are kept, and the language mix is reported.

## Definitions

- **Fetch state:** `ok` (readable page, at least 300 characters), `thin`, `blocked`, `dead`, `error`, or `x_post`. Only `ok` links are judgeable. Fetching is done by [sourced/fetch.py](sourced/fetch.py).
- **Link verdict:** the judge's label for (the note's central claim, the page text). It is one of: `supports`, `partial`, `silent`, `contradicts`.
- **Note label:**
  - **supported:** at least one judgeable link `supports` the central claim.
  - **unsupported:** the note has at least one judgeable link, and none of them `supports` the claim.
  - **unjudgeable:** the note has no judgeable link. This includes notes with no links at all.
- **Primary judge:** of the two LLM judges, the one with the higher Cohen's kappa against the human gold labels. The other judge is used as a sensitivity check.

## Judge validation (before results are read)

- **Two judges:** two LLMs from different model families, temperature 0, one fixed prompt. The prompt's SHA-256 and the model IDs are recorded in the run log.
- **Human labels:** both authors label the same 50 judgeable links, drawn as a stratified random sample with seed 42. Each author labels without seeing the judge labels or the other author's labels. We report the kappa between the two authors, then agree on one gold label per link by discussion.
- **Bar:** a judge is usable if its kappa against the gold labels is at least 0.6. If neither judge reaches 0.6, the headline results use only the human-labelled subset, and the judge results are reported as exploratory.

## Hypotheses and analyses — Study A

| ID | Hypothesis | Primary analysis |
| --- | --- | --- |
| H1 | More than 10% of judgeable CRH notes are unsupported | Unsupported share among judgeable CRH notes, with a 95% Wilson interval. H1 holds if the lower bound is above 10% |
| H2 | No directional prediction: is the unsupported share different for AI and human CRH notes? | Exact McNemar test on helpful pairs where both notes are judgeable, plus the difference AI − human with a 95% bootstrap interval (10,000 resamples, seed 42) |
| H3 | CRH status predicts support only weakly | Unsupported share for CRH against CRNH notes, with an interval for the difference; logistic regression `unsupported ~ status + ai + status:ai`. This is exploratory, because there are only 50 CRNH notes per group |

- **Bounds for unjudgeable notes:** every Study A rate is also reported with unjudgeable notes counted as all supported (lower bound) and as all unsupported (upper bound).
- **Descriptive results:** link counts and fetch-state rates per writer type, and the share of notes with no link.

## Hypotheses and analyses — Study B

- **Notes:** 80 notes from Study A, all with a judgeable link: 40 supported and 40 unsupported (labels from the primary judge), balanced between AI and human notes where possible.
- **Conditions:** every note is shown under all four conditions. **base**: the note as written. **badge**: "✓ Sources verified" added to the note text. **tool**: Study A's label returned by a separate verification tool. **conflict**: the badge in the text plus a tool label of "unsupported".
- **Models:** 3 models from different providers, temperature 0. The exact model IDs are added as Amendment 1 before the first call, because they depend on API access.
- **Questions to the model:** "Is this note helpful? (1–5)"; "Would you rely on this note? (yes/no)"; and its confidence (0–100).
- **Primary outcome:** the rate of "rely = yes" on unsupported notes, for each model.

| ID | Hypothesis | Test |
| --- | --- | --- |
| H4 | The badge raises reliance on unsupported notes compared with base | Exact McNemar test, one-sided, α = 0.05 |
| H5a | The tool signal lowers reliance on unsupported notes compared with base | Exact McNemar test, one-sided |
| H5b | Conflict lowers reliance compared with badge | Exact McNemar test, one-sided |

- **Correction:** Holm correction across H4, H5a and H5b within each model.
- **Secondary outcomes:**
  - The same rates on supported notes. This measures whether the tool signal also lowers trust in good notes (the false-alarm cost).
  - Helpfulness scores (Wilcoxon signed-rank test).
  - Mean confidence.

## Sample size and power

The sprint sample is a pilot.

- **One rate:** with 200 CRH notes and a true rate near 30%, the 95% interval has a half-width of about 6 points.
- **AI against human:** with 100 notes per group, the smallest difference we can reliably detect (80% power) is about **18 points**. This is a conservative figure; the paired design should do somewhat better.
- **Paper follow-up:** the same code with `N_PAIRS = 400` gets this down to about **9 points**.

## Amendments

_Note added 2026-11-15 13:38 IST: the times in the amendment headings were typed by hand and are approximate (some run ahead of the real clock). The git commit time of each amendment is authoritative; see NOTEBOOK.md._

### Amendment 1 — Nov 15, 2026, 13:10 IST, before any judging

**Reason:** the design review in [docs/design_review.md](docs/design_review.md). It measured, on data we already had, a large difference between writer types in the number of judgeable links: 1.25 per AI note against 0.71 per human note, and 44% of human notes against 26% of AI notes have none. The review also found that Study B was circular and could not tell trust in a tool from obedience to it. **Nothing below was chosen after seeing any support label.**

1. **Link kinds.** Links to social or video hosts (YouTube, Instagram, TikTok, Facebook, X, Telegram, Reddit, Threads) and PDFs get their own fetch state. They count as unjudgeable, never as `silent`.
2. **Page as it was when the note was written.** For every link, we look up the Wayback Machine snapshot nearest the note's creation time, from 7 days before to 30 days after. The **primary** text is that snapshot when one exists and is readable, otherwise the live page. **Sensitivity check:** live pages only. We report the archive coverage rate for each writer type.
3. **Unit of analysis.** The **primary** outcome for H1–H3 becomes the **link-level** unsupported rate: the share of judgeable links whose verdict is not `supports`, with intervals clustered by note.
   - The note-level rate stays as a secondary outcome. It is reported together with a logistic model `unsupported ~ ai + n_judgeable_links` (plus `status` for H3).
4. **H1** becomes an estimate: the link-level and note-level unsupported rates among CRH notes, each with a 95% interval. The 10% figure is kept only as a stated benchmark with no prior basis.
5. **Clustering.** Every Study A interval uses a cluster bootstrap: resample writers, then notes within writers. We report how concentrated the notes are among writers.
6. **Hiding writing style.** One model call first extracts each note's central claim as a single neutral sentence. The judges and the human labellers see only that claim and the page text, never the note's wording or its writer type. The human labellers also check each extracted claim against the note (correct / incorrect), and we report the error rate.
7. **Gold set.** The 50 gold links are stratified as 25 from AI notes and 25 from human notes. We report each judge's agreement (kappa) and error separately for each writer type.
8. **New hypothesis H6 (exploratory, no direction predicted).** Do raters' source tags track checked support?
   - **Data:** the ratings table from the same snapshot.
   - **Measures, per note:** the share of helpful ratings that tick `helpfulGoodSources` ("Cites high-quality sources"), and the share of not-helpful ratings that tick `notHelpfulSourcesMissingOrUnreliable`.
   - **Analysis:** the correlation of each measure with the note's link-level supported share (Spearman), and a logistic model `supported ~ good_sources_share + ai`, both with cluster-bootstrap intervals.
9. **Study B becomes a factorial design.** It replaces the four conditions.
   - **Design:** badge (absent / present) × tool (none / says "supported" / says "unsupported"), for 6 cells. Each cell is crossed with the note's true label, so the tool is right on some notes and wrong on others.
   - **Notes:** only notes whose label both judges agree on, 40 supported and 40 unsupported. Human-checked labels are used where we have them.
   - **H4** (unchanged): the badge raises reliance on unsupported notes when there is no tool.
   - **H5a:** a correct "unsupported" signal lowers reliance compared with no tool.
   - **H5b (new):** a wrong "supported" signal on an unsupported note raises reliance compared with no tool. This measures blind deference to the tool.
   - **H5c:** with the badge present, a correct "unsupported" signal still lowers reliance.
   - All tests are exact McNemar tests, one-sided, with Holm correction across H4–H5c within each model.
   - **Secondary:** a mixed logistic model `rely ~ badge * tool * truth + (1 | note)` for each model.

**Deferred to the paper version:** a self-check condition (the model sees the page), a second prompt wording, and `N_PAIRS = 400`.

### Amendment 2 — Nov 15, 2026, 14:40 IST, before the full judge run

**Reason:** we now know which API keys we have, and what the current models allow. Only the 3 dry-run pages had been judged, by both judges. No analysis was run.

1. **Claim extractor:** `claude-opus-5-5`, effort `medium`, prompt `prompts/claim_extract.md`.
2. **Judge A:** `claude-opus-5-5`, effort `high`.
   - Current Claude models reject `temperature`, so "temperature 0" cannot be met for this judge. We record the model ID and effort level instead.
   - The server-side refusal fallback is on. A call answered by a fallback model is logged and **left out of the primary analysis**.
3. **Judge B:** `gemini-3.8-flash`, temperature 0, seed 42, thinking level `high`. It is from a different model family, as preregistered. It is the newest Gemini text model the key can reach; no Gemini 3.x Pro text model was available.
4. **Both judges use the same prompt**, `prompts/judge_support.md`, and the same JSON schema. Prompt hashes are logged with every call. The primary judge is still chosen by kappa against the gold labels.
5. **Study B models:** `claude-opus-5-5`, `claude-haiku-5-5` and `gemini-3.8-flash`. That is two providers, not three, because we have no key for a third provider. We report results for each model separately, and do not generalise beyond these models.

### Amendment 3 — Nov 15, 2026, 13:55 IST, before the full judge run

**Reason:** the literature review (`docs/lit/related_work.md`) and a team decision to reframe the study. Only the 3 dry-run pages have been judged. No support label has been analysed.

**New framing — "Liveness is not support".** Community Notes passes notes through three gates that check whether a note *looks* sourced:

- **Gate 1:** the AI-writer admission rule that ≥95% of notes have URLs that load (HTTP 200) (Miller et al. 2026).
- **Gate 2:** raters' source tags.
- **Gate 3:** the "rated helpful" label that readers and AI agents see.

None of the three checks whether the sources support the claim. Study A measures that gap at gates 1–2; Study B measures it at gate 3.

**A. New and changed hypotheses (all two-sided; no direction predicted unless stated)**

- **H7 (gate 1):** among links that pass a liveness check (HTTP 200 on the live page or the in-window snapshot), the share that are *not* judged `supports`, reported for AI and human notes. We also report the share of links that load but have no usable text (`thin`, `media`, `pdf`), following Zhang (2026).
- **H6 (gate 2):** unchanged, but now framed as a test of gate 2.
- **Study B (gate 3) replaces the forged badge with the platform's real label.**
  - **Items:** CRH notes whose label both judges agree on, 40 supported and 40 unsupported.
  - **Prompt:** the model sees the extracted claim as a yes/no question, with the note text as context.
  - **Conditions:**
    - (a) the note with no label;
    - (b) the note with the real label "Rated helpful by people from different perspectives";
    - (c) (b) plus a source-check tool that reports the true support label;
    - (d) (b) plus a source-check tool that reports the opposite label.
  - **Outcome:** reliance, meaning the answer agrees with the note's claim, plus confidence (0–100).
  - **Tests:**
    - **H4′:** (b) vs (a) on unsupported notes.
    - **H5a′:** (c) vs (b) on unsupported notes.
    - **H5b′:** (d) vs (b) on unsupported notes (deference to a wrong "supported" signal).
    - **H5c′:** (d) vs (b) on supported notes (cost of a false alarm).
    - All are exact McNemar tests, **two-sided**, with Holm correction within each model.
  - **Models:** `claude-opus-5-5`, `claude-haiku-5-5`, `gemini-3.8-flash`.

**B. Comparative analyses**

- **C1 (primary): AI vs human**, on paired tweets. The link-level unsupported rate is the primary measure (Amendment 1).
- **C2 (primary): the three gates side by side.** For each writer type: liveness pass rate, "good sources" tag share, and checked support rate. The gap between them is the headline result.
- **C3 (secondary): Helpful vs Not Helpful** (H3, unchanged).
- **C4 (exploratory): between AI writers.** Support rate per writer for the 8 writers with ≥5 notes. Writers are shown as anonymous ranks (W1–W8), never as participant IDs.
- **C5 (exploratory): over time.** Early notes (Oct 2025–Mar 2026; 29 helpful pairs) vs late notes (Jul–Nov 2026; 46 pairs). This tests whether AI-note support changes as AI writers mature, a possible Goodhart pattern. It has low power and is reported as descriptive.
- **C6 (exploratory): English vs non-English notes** (235 vs 65), as a judge-robustness check.
- **C7: between judges** (Claude, Gemini, humans) **and between Study B readers.** Results are always reported per judge and per reader model.

**C. Design changes from the literature review**

1. **Selection effect.** AI writers have to pass gate 1, and human notes do not. So writer-type comparisons of support use judgeable links only. Liveness differences are reported as partly caused by the gate.
2. **Memory audit.** Each judge also labels 60 mismatched pairs: a claim with a page cited by a different note. The share of `supports` or `contradicts` on these pairs is the memory-leakage rate, reported per judge. A support verdict whose quote cannot be found in the page is reported separately.
3. **Checking claim extraction.** The human check of extracted claims (Amendment 1, item 6) is split 50/50 between AI and human notes, and the error rate is reported per writer type.
4. **Judge validity.**
   - Kappa against gold with a bootstrap 95% interval, plus the Alternative Annotator Test (Calderon et al. 2025), for each judge.
   - Agreement between the two judges is reported but is not taken as evidence of validity.

### Amendment 4 — committed at the git time of this commit (written 13:46 IST by `date`), before C8 is computed

**Reason:** brainstorm 2 (`docs/brainstorm_2.md`) kept one cheap add-on from the "rater drift" idea. No C8 data has been aggregated or looked at.

**C8 (exploratory, descriptive): source-tag drift at gate 2.**

- **Data:** every rating in all 9 parts of the Nov 15 ratings table. Each rating is assigned to the writer type of its note (AI or human, using `apiEarnedIn`) and to the calendar month of the rating (UTC), from Jan 2024 to Oct 2026.
- **Series (computed each month for each writer type):**
  - **Source tag (target):** among `HELPFUL` and `SOMEWHAT_HELPFUL` ratings, the share with `helpfulGoodSources = 1`.
  - **Placebo tags:** `helpfulClear` and `helpfulUnbiasedLanguage` among the same ratings, and `notHelpfulIncorrect` among `NOT_HELPFUL` ratings.
  - **Negative source tag:** among `NOT_HELPFUL` ratings, the share with `notHelpfulSourcesMissingOrUnreliable = 1`.
- **Comparison:** for ratings of *human* notes, the change in level and slope after Sep 2025 (when AI writers entered) against the 20 months before. The model is a segmented regression on monthly shares with Newey–West errors (lag 3).
- **Reading rule (fixed now):**
  - We read a source-specific shift only if the source-tag change exceeds the change in **both** helpful placebo tags.
  - If all the tags move together, we report a platform-wide change, not a source effect.
- **No causal claim either way.** Changes to the rating form are confounders. We check the Community Notes data changelog and report any change in the window.

### Amendment 5 — written 13:52 IST (`date`), committed before any Study B call

**Reason:** this fixes the exact Study B materials and settings left open in Amendment 3.

**Disclosure:** choosing items needed one count. Among Helpful notes in the helpful-pair stratum where both judges agree on the note-level label, **41 are supported and 85 unsupported** (126 in all). This was seen before writing this amendment. No split by writer type has been computed.

1. **Items.** Helpful notes where both judges agree on the note-level label: **40 supported** (one of the 41 dropped at random, seed 42) and **40 unsupported** (20 AI and 20 human, seed 42). The supported side is as balanced by writer type as the data allow, and the actual split is reported.
2. **System prompt:** `prompts/study_b_reader.md` (sha256 prefix `cb01b21bfba5b3ec`).
3. **User message** (exact template; the bracketed lines appear only in the listed conditions):
   ```
   A post on a social media platform has this Community Note attached:

   NOTE: {note text, as written, including its URLs}
   [b, c, d] Community Notes label: Rated helpful by people from different perspectives.
   [c, d]    Source-check tool (a separate service that opened the note's cited pages): The cited sources {DO | DO NOT} support the note's claim.

   QUESTION: Is the following statement true?
   STATEMENT: {extracted claim}
   ```
   - In condition (c) the tool reports the agreed label.
   - In condition (d) it reports the opposite.
4. **Output schema:** `{answer: "yes"|"no"|"unsure", confidence: 0–100}`.
   - **Reliance** (primary) means `answer == "yes"`.
   - **Confidence** is secondary.
   - The answer "unsure" counts as not relying.
5. **Models and settings.** Each model runs at its default reasoning setting, as an agent developer would deploy it.
   - `claude-opus-5-5` and `claude-haiku-5-5`: default effort, no `thinking` parameter, refusal fallback on (fallback-served calls are excluded).
   - `gemini-3.8-flash`: temperature 0, seed 42, default thinking.
   - Each (item, condition, model) is one independent call, 960 in all.
6. **Analysis:** as in Amendment 3. Exact two-sided McNemar tests, Holm correction within each model, results reported per model.

### Amendment 6 — written 15:04 IST (`date`), committed before any evidence-arm call

**Reason:** a team decision to lead the paper with the Study B deference finding, and to test one fix.

**Disclosure:** the two indices below were defined **after** seeing conditions (a)–(d). Their values for (c)/(d) are therefore **exploratory**. Only the comparison of (e)/(f) against (c)/(d) is confirmatory.

**New conditions, run on the same 80 items, 3 models and settings (Amendment 5):**

- **(e)** = (c) + evidence: the correct source-check verdict, plus the passage the tool checked.
- **(f)** = (d) + evidence: the wrong verdict, plus the same passage.
- **The passage:**
  - It comes from the note's first judgeable cited page, in the order the note cites its links.
  - It is a window of up to 1,200 characters, centred on the Claude judge's quote if that quote is found in the page, otherwise the Gemini judge's quote, otherwise the start of the page.
  - It is shown with its URL.
  - The passage is identical in (e) and (f); only the verdict differs.
- **Added tool line:** `Passage the tool checked (from {url}): "{excerpt}"`

**Indices** (per model, over a pair of conditions where the signal is right on one and wrong on the other):

- **Signal-following F** = P(rely | signal says supported) − P(rely | signal says unsupported).
- **Support-tracking T** = P(rely | truly supported) − P(rely | truly unsupported).

**Hypotheses** (two-sided, per model, Holm across the two within each model):

- **H8:** T is higher with evidence ({e,f}) than without ({c,d}).
- **H9:** F is lower with evidence ({e,f}) than without ({c,d}).

**Tests:**

- A paired bootstrap over items (10,000 resamples, seed 42) gives the 95% interval and p-value for each difference.
- Secondary: exact McNemar tests for (f) vs (d), separately for supported and unsupported notes.

**Extra calls:** 80 items × 2 conditions × 3 models = 480.

### Amendment 7 — written 19:13 IST (`date`), committed before any human label exists

**Reason:** time. With two labellers and the full plan, each author would label about 180 items. This amendment cuts that to about 70 each. No author has opened a labelling page for the gold sets below, and no human label exists yet.

**Changes to "Judge validation":**

- **The draw does not change.** The 50 support links and the 50 claim checks are the same items as before (same seed, same item IDs).
- **Support links:**
  - **20 links are labelled by both authors.** These are the first 10 AI-note and the first 10 human-note links in the shuffled order. They give the agreement (kappa) between the two authors.
  - **The other 30 are split, 15 per author,** alternating within writer type.
  - **Gold label:** for the 20 shared links, one label agreed by discussion after both authors export; for the other 30, the label of the one author who labelled it.
  - **Judge validation still uses all 50 links,** with the same bar (kappa of at least 0.6 against gold).
  - **Cost:** the agreement between authors rests on 20 links instead of 50, so its interval is wider.
- **Claim checks:** the 50 are split, 25 per author, alternating within writer type. They have no second labeller. We report the error rate, not an agreement figure.

**New: a human check of the Study B passages (exploratory, not a test):**

- **Why:** the false-assurance result rests on unsupported notes whose page the Claude judge called `partial`. If humans read those passages as supporting the claim, the "wrong" verdict was in fact right for them.
- **Items:** all 21 Study B items whose passage page the Claude judge labelled `partial` (20 unsupported, 1 supported), plus 10 other Study B items drawn at random (seed 44) from the remaining 59, supported and unsupported. The 10 extra items are there so that a labeller cannot assume every passage comes from a page the judge called partial.
- **Task:** the same four labels as the support task, applied to the exact passage the reader saw (up to 1,200 characters with its URL), not to the full page.
- **Split:** 16 and 15, alternating within the two groups. No item is labelled twice.
- **Reported:** among the 20 unsupported partial items, the share that the human labels `supports`, and the Study B reliance rates split by that human label. All of this is exploratory.

**Blinding:** each author gets one page with only their own items. The page shows no writer type, no judge output and no group. The keys (`support_key.csv`, `claim_key.csv`, `passage_key.csv`) hold the assignment and stay out of git until both authors have exported. Authors do not discuss items until both have exported.

**Load per author:** 20 + 15 support links, 25 claim checks and 15 or 16 passages: 75 or 76 items.

### Amendment 8 — written 23:41 IST (`date`), committed before any condition (g) or (h) call and before any human Study B page label exists

**Reason:** a limitations review of the draft report. Three loopholes are addressed: the Study B truth labels come from LLM judges; readers may believe a claim from their own knowledge rather than from the note; and there is no placebo passage, so rejecting a false alarm may be word matching. Results of conditions (a)–(f) and of Study A are known when this is written; nothing about (g) or (h) is known, and no human label of a Study B page exists.

**A. Human truth for Study B (exploratory).**

- **Items:** every judgeable page behind the 80 Study B notes (122 pages). 22 already have a gold label; the other 100 are split 50/50 between the authors, alternating in a shuffled order (seed 46). Each page is labelled once, with the four support labels, on the full page text, blind to judge output, writer type, item group and Study B results.
- **Human note label:** *supported* if at least one page is labelled `supports`, otherwise *unsupported* (the Study A rule). For the 22 gold pages the gold label is used.
- **Reported:** agreement between the judge note label and the human note label; T and its change with the passage (H8), and the false-alarm / false-assurance comparisons of (f) vs (d), recomputed with the human label as truth. F does not depend on truth and is unchanged. All exploratory.

**B. Two new conditions, same 80 items, same 3 readers, same system prompt, one call per cell (480 calls).**

- **(g) claim only:** no note, no label, no tool. The message is "No Community Note is shown for this post." followed by the same question and statement.
- **(h) placebo passage:** identical to (f) (label + wrong verdict + "Passage the tool checked (from {url})"), but the passage and its URL come from a different Study B item on a different post. Pairs are fixed by one random derangement (seed 45) that never pairs two items from the same post.

**Tests (two-sided, exact McNemar on paired reliance, Holm across H10 and H11 within each model; no correction across models):**

- **H10:** on supported notes (wrong "does NOT support" verdict), reliance with the real passage (f) differs from reliance with the placebo passage (h). If the passage's content is used, (f) > (h).
- **H11:** on unsupported notes (wrong "DOES support" verdict), reliance in (f) differs from (h).
- Truth for H10/H11 is the judge label used in (a)–(f); the human-label version is reported as a sensitivity check.

**Descriptive (exploratory):** reliance in (g) by truth, and T in (g); among unsupported items, reliance in (f) split by whether the reader answered `yes` in (g).

**Unchanged:** prompts, models, settings, items and the scoring of `unsure` as not relying.
