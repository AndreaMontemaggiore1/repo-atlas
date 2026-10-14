# repo-atlas: LLM benchmark

## Summary (v2.2 held-out round, 2026-10-11): Sonnet 5.5 (claude-sonnet-5-5), Claude Code 2.1.293, 1 repetition

Change under test: `find` also names the next 4 distinct matching files after its 5 ranked results, and SKILL.md
says to check them when the shown code is only nearby. On a zero-token proxy it put the gold file somewhere in the
output for 111 of 156 questions instead of 92, across three repos.

Questions: 20 new symptom questions on Open WebUI, made from commits 41–80 (older than the v2.1 set). They were
generated after the change and not read before the runs.

| arm | hit@3 | won / lost vs A (p) | tokens mean | vs A | per-question ratio median | cheaper than A | cost vs A | tool calls | skill invoked |
|---|---|---|---|---|---|---|---|---|---|
| A | 20/20 | | 91.0k | | | | | 6.1 | |
| S | 20/20 | 0 / 0 | 77.7k | 0.85× | 0.85 | 12/20 | 0.90× | 4.7 | 11/20 |
| P | 19/20 | 0 / 1 (1.00) | 65.6k | 0.72× | 0.81 | 14/20 (p = 0.12) | 0.83× | 3.6 | 20/20 |

- Every arm found a gold file in almost every question. The set is easier than the v2.1 one, where A had 18/20,
  so it cannot show an accuracy gain. It does show no accuracy loss at lower cost.
- P, with the CLAUDE.md pointer, saves the most: 28% fewer tokens, 17% lower cost, 2.5 fewer tool calls.
- S invoked the skill on its own in 11/20 questions. When it did not, it behaved like A.

## Results by arm

Each cell: mean ± std over runs (questions × repetitions). tokens_in = input + cache creation + cache read (everything the model processed). hit@3 = a gold file among the first 3 files named; recall@3 = fraction of gold files among them; func_hit = a gold function named in the answer. src KB = bytes returned by Read on source files (not .atlas/.claude).

| repo | arm | n | hit@3 | recall@3 | func_hit | tokens_in | tokens_out | tool calls | src KB | skill used |
|---|---|---|---|---|---|---|---|---|---|---|
| open-webui | A | 20 | 100% | 92% | 87% | 91027 ± 88625 | 1714 ± 1115 | 6.1 ± 4.8 | 6.1 ± 9.5 | 0% |
| open-webui | P | 20 | 95% | 87% | 87% | 65641 ± 42936 | 1085 ± 704 | 3.6 ± 3.0 | 1.7 ± 2.7 | 100% |
| open-webui | S | 20 | 100% | 87% | 93% | 77655 ± 58923 | 1288 ± 968 | 4.7 ± 4.1 | 3.8 ± 5.1 | 55% |

## Paired tests vs A (same question; exact sign / McNemar tests, two-sided)

| repo | arm | hit@3 arm-only / A-only (p) | func_hit arm-only / A-only (p) | tokens_in arm/A median | cheaper than A (p) | cost arm/A |
|---|---|---|---|---|---|---|
| open-webui | P | 0 / 1 (1.00) | 2 / 2 (1.00) | 0.81 | 14/20 (0.115) | 0.83 |
| open-webui | S | 0 / 0 (1.00) | 1 / 0 (1.00) | 0.85 | 12/20 (0.503) | 0.90 |
| all | P | 0 / 1 (1.00) | 2 / 2 (1.00) | 0.81 | 14/20 (0.115) | 0.83 |
| all | S | 0 / 0 (1.00) | 1 / 0 (1.00) | 0.85 | 12/20 (0.503) | 0.90 |
