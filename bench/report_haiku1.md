# repo-atlas: LLM benchmark

## Summary (Haiku round, 2026-10-11/12): Haiku 5.5 (claude-haiku-5-5), Claude Code 2.1.293, 1 repetition

The same 40 held-out symptom questions as the Sonnet rounds: Typebot (v2.3) and Open WebUI (v2.2). Arms A / S / H
were interleaved. H is the plugin as shipped (`--plugin-dir`: skill + SessionStart hook); the hook fired in 40/40 runs.

| set | arm | hit@3 | won / lost vs A | tokens mean vs A | per-question ratio median | cheaper than A | cost vs A | tool calls |
|---|---|---|---|---|---|---|---|---|
| Typebot | A | 16/20 | | 140.8k | | | | 7.6 |
| | S | 15/20 | 1 / 2 | 0.59× | 0.82 | 16/20 (p = 0.012) | 0.66× | 4.0 |
| | H | 15/20 | 1 / 2 | 0.54× | 0.65 | 16/20 (p = 0.012) | 0.65× | 3.2 |
| Open WebUI | A | 18/20 | | 123.4k | | | | 7.9 |
| | S | 18/20 | 2 / 2 | 0.59× | 0.54 | 16/20 (p = 0.012) | 0.67× | 3.5 |
| | H | 17/20 | 1 / 2 | 0.53× | 0.53 | 16/20 (p = 0.012) | 0.67× | 3.1 |

- With Haiku the skill saves the most. Without it, Haiku explores far more than Sonnet: 7.6–7.9 tool calls and
  123–141k tokens per question, against 4–6 calls for Sonnet. With the skill it needs about half the tokens, and
  cost drops by about a third.
- Accuracy is unchanged within the noise. Across both sets S won 3 and lost 4, H won 2 and lost 4.
- The whole round cost $0.59 (API-equivalent).

## Results by arm

Each cell: mean ± std over runs (questions × repetitions). tokens_in = input + cache creation + cache read (everything the model processed). hit@3 = a gold file among the first 3 files named; recall@3 = fraction of gold files among them; func_hit = a gold function named in the answer. src KB = bytes returned by Read on source files (not .atlas/.claude).

| repo | arm | n | hit@3 | recall@3 | func_hit | tokens_in | tokens_out | tool calls | src KB | skill used |
|---|---|---|---|---|---|---|---|---|---|---|
| open-webui | A | 20 | 90% | 82% | 87% | 123369 ± 61674 | 2838 ± 955 | 7.9 ± 2.9 | 6.7 ± 4.3 | 0% |
| open-webui | H | 20 | 85% | 74% | 80% | 65182 ± 24536 | 1678 ± 625 | 3.1 ± 1.6 | 1.5 ± 1.7 | 100% |
| open-webui | S | 20 | 90% | 84% | 80% | 72883 ± 43387 | 1775 ± 730 | 3.5 ± 2.3 | 1.5 ± 1.9 | 90% |
| typebot.io | A | 20 | 80% | 72% | 89% | 140828 ± 164501 | 2890 ± 1880 | 7.6 ± 5.1 | 9.4 ± 8.3 | 0% |
| typebot.io | H | 20 | 75% | 68% | 84% | 75421 ± 42394 | 1654 ± 763 | 3.2 ± 2.0 | 1.2 ± 2.3 | 100% |
| typebot.io | S | 20 | 75% | 62% | 84% | 83525 ± 36217 | 1778 ± 670 | 4.0 ± 1.8 | 1.7 ± 2.6 | 85% |

## Paired tests vs A (same question; exact sign / McNemar tests, two-sided)

| repo | arm | hit@3 arm-only / A-only (p) | func_hit arm-only / A-only (p) | tokens_in arm/A median | cheaper than A (p) | cost arm/A |
|---|---|---|---|---|---|---|
| open-webui | H | 1 / 2 (1.00) | 1 / 2 (1.00) | 0.53 | 16/20 (0.012) | 0.67 |
| open-webui | S | 2 / 2 (1.00) | 1 / 2 (1.00) | 0.54 | 16/20 (0.012) | 0.67 |
| typebot.io | H | 1 / 2 (1.00) | 1 / 2 (1.00) | 0.65 | 16/20 (0.012) | 0.65 |
| typebot.io | S | 1 / 2 (1.00) | 1 / 2 (1.00) | 0.82 | 16/20 (0.012) | 0.66 |
| all | H | 2 / 4 (0.69) | 2 / 4 (0.69) | 0.61 | 32/40 (0.000) | 0.66 |
| all | S | 3 / 4 (1.00) | 2 / 4 (0.69) | 0.68 | 32/40 (0.000) | 0.67 |
