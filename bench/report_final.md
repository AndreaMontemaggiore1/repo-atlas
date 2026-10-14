# repo-atlas: LLM benchmark

## Summary (final check, 2026-10-12): Claude Code 2.1.295, 1 repetition

20 new held-out symptom questions on Typebot, made from older commits (41–80) and not read before the runs. They
compare A (no skill) with H (the plugin as shipped), interleaved, on the latest CLI.

| model | n | hit@3 A → H | H won / lost | tokens mean vs A | per-question ratio median | cheaper than A | cost vs A | tool calls A → H |
|---|---|---|---|---|---|---|---|---|
| Sonnet 5.5 (`claude-sonnet-5-5`) | 20 | 12 → 14 | 3 / 1 | 0.68× | 0.72 | 16/20 (p = 0.012) | 0.82× | 3.9 → 1.7 |
| Opus 5.5 (`claude-opus-5-5`) | 10 | 7 → 7 | 0 / 0 | 0.90× | 0.91 | 7/10 | 0.86× | 5.4 → 5.2 |

- The hook fired in every H run, and Claude invoked the skill every time.
- On the latest CLI, Sonnet saves as much as in the earlier rounds, and here it is also more accurate than A.
- Opus saves less. Even with the skill it goes on checking with about 5 tool calls per question. This was a small
  check of 10 questions, so it is indicative, not significant.
- Cost: $2.31 for Sonnet and $3.31 for Opus (API-equivalent).

## Results by arm

Each cell: mean ± std over runs (questions × repetitions). tokens_in = input + cache creation + cache read (everything the model processed). hit@3 = a gold file among the first 3 files named; recall@3 = fraction of gold files among them; func_hit = a gold function named in the answer. src KB = bytes returned by Read on source files (not .atlas/.claude). hit_any = a gold file named anywhere in the answer. correct / +partial = judge.py verdict on the whole answer against the real commit.

| repo | arm | n | hit@3 | recall@3 | func_hit | hit_any | correct | correct+partial | tokens_in | tokens_out | tool calls | src KB | skill used |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| typebot.io | A | 20 | 60% | 49% | 76% | 70% | 30% | 75% | 61479 ± 18872 | 1173 ± 384 | 3.9 ± 1.6 | 4.6 ± 4.9 | 0% |
| typebot.io | H | 20 | 70% | 54% | 76% | 75% | 35% | 75% | 41777 ± 15845 | 669 ± 214 | 1.7 ± 1.0 | 0.5 ± 1.1 | 100% |

## Paired tests vs A (same question; exact sign / McNemar tests, two-sided)

Cells: questions the arm won / questions A won (p).

| repo | arm | hit@3 arm-only / A-only (p) | func_hit arm-only / A-only (p) | correct arm-only / A-only (p) | tokens_in arm/A median | cheaper than A (p) | cost arm/A |
|---|---|---|---|---|---|---|---|
| typebot.io | H | 3 / 1 (0.62) | 2 / 2 (1.00) | 3 / 2 (1.00) | 0.72 | 16/20 (0.012) | 0.82 |
| all | H | 3 / 1 (0.62) | 2 / 2 (1.00) | 3 / 2 (1.00) | 0.72 | 16/20 (0.012) | 0.82 |
