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
