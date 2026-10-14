# repo-atlas: LLM benchmark

## Summary (v2.4 held-out round, 2026-10-11/12): Sonnet 5.5 (claude-sonnet-5-5), Claude Code 2.1.293, 1 repetition

Two large apps never used before, cloned with the last 400 commits. 20 symptom questions each, generated and not
read before the runs. Arms A / S / P interleaved. The round was interrupted overnight and resumed on the same CLI.

- **LibreChat**: JS/TS, React + Node, 6.2k files, monoliths up to 9.8k lines, 93 duplicate bodies.
- **Dify**: Python backend + Next.js frontend, 13k files, large generated type files, 208 duplicate bodies.

| repo | arm | hit@3 | won / lost vs A (p) | tokens mean vs A | per-question ratio median | cheaper than A | cost vs A | tool calls |
|---|---|---|---|---|---|---|---|---|
| LibreChat | A | 18/20 | | 117.4k | | | | 7.2 |
| | S | 15/20 | 0 / 3 (0.25) | 0.67× | 0.68 | 17/20 (p = 0.003) | 0.75× | 4.0 |
| | P | 16/20 | 0 / 2 (0.50) | 1.07× | 0.71 | 15/20 (p = 0.04) | 0.92× | 5.2 |
| Dify | A | 16/20 | | 88.8k | | | | 5.9 |
| | S | 17/20 | 2 / 1 (1.00) | 0.96× | 1.01 | 10/20 | 1.00× | 4.7 |
| | P | 17/20 | 2 / 1 (1.00) | 0.74× | 0.68 | 14/20 | 0.80× | 3.1 |

- LibreChat's mean for P is pulled up by one question that every arm failed. A used 475k tokens on it, S 426k and
  P 1.26M (42 tool calls). P's later lookups were refused in this headless mode because they were written as
  `cd … && bash …`, which is not the pre-approved form, so the model fell back to 30 Greps. SKILL.md now says to
  run the command exactly as written.
- On Dify, S does not save tokens, while P saves 26% of tokens and 20% of cost. With the pointer the skill is
  used consistently, and that is what pays off.
- In every LibreChat question the skill arms lost, the gold file was missing from the lookup's output. That is
  the ranking limit on vague questions.
- Cost of the round: $9.71.

## Results by arm

Each cell: mean ± std over runs (questions × repetitions). tokens_in = input + cache creation + cache read (everything the model processed). hit@3 = a gold file among the first 3 files named; recall@3 = fraction of gold files among them; func_hit = a gold function named in the answer. src KB = bytes returned by Read on source files (not .atlas/.claude).

| repo | arm | n | hit@3 | recall@3 | func_hit | tokens_in | tokens_out | tool calls | src KB | skill used |
|---|---|---|---|---|---|---|---|---|---|---|
| dify | A | 20 | 80% | 70% | 63% | 88798 ± 42749 | 1544 ± 737 | 5.9 ± 3.0 | 3.5 ± 3.4 | 0% |
| dify | P | 20 | 85% | 74% | 58% | 66026 ± 40069 | 890 ± 504 | 3.1 ± 2.4 | 0.7 ± 1.7 | 100% |
| dify | S | 20 | 85% | 72% | 79% | 85156 ± 57781 | 1262 ± 847 | 4.7 ± 3.7 | 2.7 ± 3.2 | 80% |
| librechat | A | 20 | 90% | 76% | 69% | 117414 ± 102094 | 1854 ± 1089 | 7.2 ± 4.2 | 4.6 ± 6.3 | 0% |
| librechat | P | 20 | 80% | 70% | 62% | 125348 ± 272257 | 1428 ± 2153 | 5.2 ± 9.2 | 1.1 ± 3.2 | 100% |
| librechat | S | 20 | 75% | 62% | 77% | 78667 ± 88000 | 1130 ± 1134 | 4.0 ± 4.8 | 1.2 ± 2.9 | 85% |

## Paired tests vs A (same question; exact sign / McNemar tests, two-sided)

| repo | arm | hit@3 arm-only / A-only (p) | func_hit arm-only / A-only (p) | tokens_in arm/A median | cheaper than A (p) | cost arm/A |
|---|---|---|---|---|---|---|
| dify | P | 2 / 1 (1.00) | 0 / 1 (1.00) | 0.68 | 14/20 (0.115) | 0.80 |
| dify | S | 2 / 1 (1.00) | 3 / 0 (0.25) | 1.01 | 10/20 (1.000) | 1.00 |
| librechat | P | 0 / 2 (0.50) | 0 / 1 (1.00) | 0.71 | 15/20 (0.041) | 0.92 |
| librechat | S | 0 / 3 (0.25) | 1 / 0 (1.00) | 0.68 | 17/20 (0.003) | 0.75 |
| all | P | 2 / 3 (1.00) | 0 / 2 (0.50) | 0.68 | 29/40 (0.006) | 0.86 |
| all | S | 2 / 4 (0.69) | 4 / 0 (0.12) | 0.83 | 27/40 (0.038) | 0.86 |
