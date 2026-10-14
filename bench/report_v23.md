# repo-atlas: LLM benchmark

## Summary (v2.3, 2026-10-11): Sonnet 5.5 (claude-sonnet-5-5), Claude Code 2.1.293, 1 repetition, skill as in v2.2

Two sets of symptom questions, arms A / S / P interleaved:

- **Typebot**, held out: a Next.js/TypeScript app with ~167k code lines, 2.7k files, 33 duplicate bodies and
  231 names defined in several files. The 20 questions were generated and not read before the runs.
- **Open WebUI v2.1 set**, a re-test: the 20 questions where v2.1 lost 2 (S) and 4 (P). They were used to
  diagnose the ranking failure behind v2.2, so this re-test is not a fair test.

| set | arm | hit@3 | won / lost vs A (p) | tokens mean vs A | per-question ratio median | cheaper than A | cost vs A | tool calls |
|---|---|---|---|---|---|---|---|---|
| Typebot | A | 18/20 | | 65.5k | | | | 4.3 |
| | S | 16/20 | 0 / 2 (0.50) | 0.88× | 0.89 | 11/20 | 0.86× | 2.9 |
| | P | 18/20 | 1 / 1 (1.00) | 0.89× | 0.71 | 14/20 | 0.89× | 2.7 |
| Open WebUI v2.1 set | A | 17/20 | | 77.8k | | | | 5.1 |
| | S | 18/20 | 1 / 0 (1.00) | 0.79× | 0.77 | 15/20 (p = 0.04) | 0.86× | 3.4 |
| | P | 18/20 | 1 / 0 (1.00) | 0.79× | 0.70 | 14/20 | 0.88× | 3.0 |

- On the v2.1 set, the v2.2 change turned 0/2 and 0/4 into 1/0 for both arms, at about 21% fewer tokens.
  This is consistent with the diagnosis, but the set is biased.
- On the held-out Typebot set the result looks like the earlier rounds. P matches A's accuracy and S is 2
  questions behind (not significant). Both arms save 11–12% of tokens on average and 11–14% of cost, and P's
  median question costs 0.71× A's.
- A's own score on the same Open WebUI questions was 18/20 in v2.1 and 17/20 here: one-repetition noise.

## Results by arm

Each cell: mean ± std over runs (questions × repetitions). tokens_in = input + cache creation + cache read (everything the model processed). hit@3 = a gold file among the first 3 files named; recall@3 = fraction of gold files among them; func_hit = a gold function named in the answer. src KB = bytes returned by Read on source files (not .atlas/.claude).

| repo | arm | n | hit@3 | recall@3 | func_hit | tokens_in | tokens_out | tool calls | src KB | skill used |
|---|---|---|---|---|---|---|---|---|---|---|
| open-webui | A | 20 | 85% | 81% | 79% | 77790 ± 31618 | 1421 ± 589 | 5.1 ± 2.3 | 3.2 ± 3.5 | 0% |
| open-webui | P | 20 | 90% | 83% | 79% | 61163 ± 33961 | 896 ± 530 | 3.0 ± 2.3 | 1.2 ± 1.9 | 100% |
| open-webui | S | 20 | 90% | 86% | 79% | 61174 ± 28920 | 994 ± 527 | 3.4 ± 2.1 | 1.3 ± 1.9 | 60% |
| typebot.io | A | 20 | 90% | 72% | 100% | 65492 ± 20017 | 1214 ± 365 | 4.3 ± 1.4 | 2.7 ± 3.7 | 0% |
| typebot.io | P | 20 | 90% | 74% | 95% | 58281 ± 37052 | 794 ± 522 | 2.7 ± 2.2 | 1.1 ± 2.3 | 100% |
| typebot.io | S | 20 | 80% | 71% | 89% | 57706 ± 25274 | 869 ± 434 | 2.9 ± 1.9 | 1.4 ± 2.2 | 75% |

## Paired tests vs A (same question; exact sign / McNemar tests, two-sided)

| repo | arm | hit@3 arm-only / A-only (p) | func_hit arm-only / A-only (p) | tokens_in arm/A median | cheaper than A (p) | cost arm/A |
|---|---|---|---|---|---|---|
| open-webui | P | 1 / 0 (1.00) | 2 / 2 (1.00) | 0.70 | 14/20 (0.115) | 0.88 |
| open-webui | S | 1 / 0 (1.00) | 0 / 0 (1.00) | 0.77 | 15/20 (0.041) | 0.86 |
| typebot.io | P | 1 / 1 (1.00) | 0 / 1 (1.00) | 0.71 | 14/20 (0.115) | 0.89 |
| typebot.io | S | 0 / 2 (0.50) | 0 / 2 (0.50) | 0.89 | 11/20 (0.824) | 0.86 |
| all | P | 2 / 1 (1.00) | 2 / 3 (1.00) | 0.71 | 28/40 (0.017) | 0.89 |
| all | S | 1 / 2 (1.00) | 0 / 2 (0.50) | 0.78 | 26/40 (0.081) | 0.86 |
