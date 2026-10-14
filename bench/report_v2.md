# repo-atlas: LLM benchmark

## Summary (v2, 2026-10-07): Sonnet 5.5 (claude-sonnet-5-5), Claude Code 2.1.288, 1 repetition

Repos: gPodder (Python, ~31k code lines) and Formbricks (Next.js/TypeScript monorepo, ~690k code lines, 4.8k files).
96 questions: 60 from commit subjects (they often name the identifier) + 36 "symptom" questions (the same commits
rewritten by an LLM as a product owner would ask, no identifiers; gold unchanged). Arms run interleaved, same CLI:

- **A**: no skill.
- **S**: v2 skill installed, prebuilt map, no hint anywhere: what a public user gets.
- **P**: S + the 2-line CLAUDE.md pointer written by `atlas init --claude-md`.

### Pre-registered criteria (written before the runs)

| criterion | result | verdict |
|---|---|---|
| P: median per-question tokens ≤ 0.85× A | 0.76× | pass |
| P: hit@3 ≥ A − 3 pts | 80.2% vs 80.2% (7 won / 7 lost) | pass |
| S: spontaneous invocation on symptom questions ≥ 50% | 72% (26/36) | pass |
| cost of notes ≤ 15% of a task | not measured (no notes arm in v2) | n/a |

### Pooled results (96 questions per arm)

| arm | hit@3 | func_hit | tokens_in mean | tokens_in median | per-question ratio vs A (median) | API-equiv. cost | tool calls |
|---|---|---|---|---|---|---|---|
| A | 80.2% | 70.0% | 68.9k | 57.2k | — | $6.28 | 4.4 |
| S | 75.0% | 70.0% | 56.9k (0.83×) | 56.2k | 1.00 | $5.59 (0.89×) | 3.1 |
| P | 80.2% | 67.5% | 54.5k (0.79×) | 47.8k | 0.76 | $5.60 (0.89×) | 2.6 |

By question kind (hit@3 arm-only / A-only, exact McNemar p):

| kind | arm | hit@3 | won / lost vs A (p) | tokens mean vs A | cheaper than A |
|---|---|---|---|---|---|
| commit (60) | A | 75.0% | | | |
| | S | 78.3% | 4 / 2 (0.69) | 0.84× | 23/60 |
| | P | 81.7% | 6 / 2 (0.29) | 0.82× | 32/60 |
| symptom (36) | A | 88.9% | | | |
| | S | 69.4% | **0 / 7 (0.016)** | 0.80× | 23/36 |
| | P | 77.8% | 1 / 5 (0.22) | 0.74× | 27/36 (p = 0.004) |

### What this says

1. **The v2 skill saves tokens; v1 cost more.** v1 (stage 1) cost 1.36–1.71× A. v2 processes 17–21% fewer tokens on
   average and costs 11% less in API-equivalent dollars, in both repos. Most input tokens are cache reads at
   a tenth of the price, which is why $ savings are smaller than token savings. The saving comes from fewer turns
   (2.6–3.1 tool calls vs 4.4), as designed.
2. **It saves more where the repo is big.** Mean tokens vs A on Formbricks: P 0.75×, S 0.78×. On gPodder: 0.83× and 0.87×.
   On gPodder commit questions, which name the identifier, S is not cheaper (median 1.02×, cheaper in only 9/30).
   Grep is enough there. The skill listing adds ~200 tokens per API call even when unused.
3. **On commit questions the skill is as accurate or better.** On Formbricks, P finds a gold file in 5 questions
   A misses and loses 1 (73% vs 60%).
4. **On symptom questions it is less accurate, and for S that is significant (0 won, 7 lost, p = 0.016).**
   Every lost case was read. Four causes:
   - *Files the map does not index*: Windows installer `.nsi` and GTK `.ui` layouts. The lookup returns the
     nearest code, the model answers from it, and A finds the real file with Grep.
   - *Stopping early*: answers that say "I haven't opened the code that renders the image, so I'm assuming…".
     The SKILL.md rule "answer from the code shown" makes the model trust results that are only adjacent.
   - *Consumer instead of definition*: it named the file that imports a list, not the file that defines it.
   - *An ambiguous question* ("tidy up the notes in the data part of the app"): every arm guessed. A happened to
     list the gold file among its first three.
   With the CLAUDE.md pointer (P) the loss is smaller (1/5, not significant) and tokens drop most (0.74×).
5. **Triggering works.** With no hint, S invoked the skill in 30% of commit questions (by design: the description
   says to skip it when the exact symbol is known) and 72% of symptom questions. On the separate triggering set
   (gPodder, written before any run) it fired on 10/10 prompts that should use it and 0/10 that should not
   (general questions, one-liners, "read only that function", license, README typo).

### Limits

- Correction (2026-10-11): the scorer did not recognise some extensions (`.svelte`, `.mts`, `.vue`…). Fixing it
  turned one Formbricks commit question into a hit for all three arms (+1 pt each). The paired tests are unchanged.

- 1 repetition, 2 public repos, one model (Sonnet 5.5). Symptom questions are LLM-written. Gold = files and
  functions of the commit, so another valid place counts as a miss for every arm alike.
- Wall time is not comparable. Each run uses a fresh copy, and Windows real-time antivirus scans every file on
  its first open. The first lookup on a Formbricks copy took 25 s, of which 22 s were spent in `open()`. The same
  lookup takes 3.9 s once the files have been scanned, as in a real working copy.
- The copies have no `.git`. Churn and co-change come from the prebuilt map, built on a real clone.
- Earlier stage-1 baselines (CLI 2.1.281) are not comparable: the fixed context per call shrank from ~23k to
  ~13.4k tokens between CLI versions.

### Next, before publishing (to be validated on new questions, not these)

- SKILL.md: replace "answer from the code shown" with a check. If the shown code is only next to what was asked
  (you would write "probably" or "I assume"), take one targeted step (Grep an identifier you saw, or `find` with
  other words) before answering.
- `find`: also list non-indexed files (layouts, installers, templates) whose path matches the query words.
- Recommend `atlas init --claude-md` in the README: P is as accurate as A and the cheapest arm.

## Results by arm

Each cell: mean ± std over runs (questions × repetitions). tokens_in = input + cache creation + cache read (everything the model processed). hit@3 = a gold file among the first 3 files named; recall@3 = fraction of gold files among them; func_hit = a gold function named in the answer. src KB = bytes returned by Read on source files (not .atlas/.claude).

| repo | arm | n | hit@3 | recall@3 | func_hit | tokens_in | tokens_out | tool calls | src KB | skill used |
|---|---|---|---|---|---|---|---|---|---|---|
| formbricks | A | 47 | 68% | 56% | 70% | 66712 ± 34594 | 1104 ± 571 | 4.3 ± 2.6 | 1.8 ± 3.9 | 0% |
| formbricks | P | 47 | 72% | 52% | 70% | 49771 ± 23161 | 657 ± 343 | 2.1 ± 1.4 | 0.5 ± 1.5 | 100% |
| formbricks | S | 47 | 66% | 50% | 76% | 51937 ± 21523 | 758 ± 385 | 2.7 ± 1.4 | 0.8 ± 3.4 | 60% |
| gpodder | A | 49 | 92% | 83% | 70% | 71023 ± 40768 | 1100 ± 729 | 4.6 ± 2.8 | 1.7 ± 3.9 | 0% |
| gpodder | P | 49 | 88% | 79% | 65% | 58956 ± 29402 | 766 ± 454 | 3.0 ± 2.1 | 0.8 ± 1.8 | 96% |
| gpodder | S | 49 | 84% | 76% | 65% | 61737 ± 24752 | 884 ± 471 | 3.6 ± 1.9 | 1.3 ± 2.3 | 33% |

## By question kind (commit = commit subject; symptom = rewritten without identifiers)

| repo | kind | arm | n | hit@3 | func_hit | tokens_in median | tokens_in mean | tool calls | skill used |
|---|---|---|---|---|---|---|---|---|---|
| formbricks | commit | A | 30 | 60% | 62% | 49728 | 63883 | 3.9 | 0% |
| formbricks | commit | P | 30 | 73% | 67% | 47556 | 48413 | 2.1 | 100% |
| formbricks | commit | S | 30 | 67% | 75% | 47074 | 51099 | 2.7 | 40% |
| formbricks | symptom | A | 17 | 82% | 85% | 60211 | 71704 | 4.9 | 0% |
| formbricks | symptom | P | 17 | 71% | 77% | 47716 | 52168 | 2.1 | 100% |
| formbricks | symptom | S | 17 | 65% | 77% | 46566 | 53416 | 2.5 | 94% |
| gpodder | commit | A | 30 | 90% | 67% | 56122 | 70723 | 4.7 | 0% |
| gpodder | commit | P | 30 | 90% | 67% | 62508 | 61932 | 3.2 | 93% |
| gpodder | commit | S | 30 | 90% | 67% | 57790 | 61952 | 3.7 | 20% |
| gpodder | symptom | A | 19 | 95% | 75% | 60032 | 71498 | 4.4 | 0% |
| gpodder | symptom | P | 19 | 84% | 62% | 47158 | 54257 | 2.6 | 100% |
| gpodder | symptom | S | 19 | 74% | 62% | 58917 | 61397 | 3.4 | 53% |

## Paired tests vs A (same question; exact sign / McNemar tests, two-sided)

| repo | arm | hit@3 arm-only / A-only (p) | func_hit arm-only / A-only (p) | tokens_in arm/A median | cheaper than A (p) | cost arm/A |
|---|---|---|---|---|---|---|
| formbricks | P | 5 / 3 (0.73) | 3 / 3 (1.00) | 0.72 | 33/47 (0.008) | 0.89 |
| formbricks | S | 2 / 3 (1.00) | 4 / 2 (0.69) | 0.91 | 26/47 (0.560) | 0.89 |
| gpodder | P | 2 / 4 (0.69) | 4 / 6 (0.75) | 0.90 | 26/49 (0.775) | 0.89 |
| gpodder | S | 2 / 6 (0.29) | 2 / 4 (0.69) | 1.01 | 20/49 (0.253) | 0.89 |
| all | P | 7 / 7 (1.00) | 7 / 9 (0.80) | 0.76 | 59/96 (0.032) | 0.89 |
| all | S | 4 / 9 (0.27) | 6 / 6 (1.00) | 1.00 | 46/96 (0.760) | 0.89 |

## Triggering (skill installed, no hint): was it invoked?

| repo | arm | should invoke: invoked | should not: invoked |
|---|---|---|---|
| gpodder | S | 10/10 | 0/10 |
