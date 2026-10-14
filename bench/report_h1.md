# repo-atlas: LLM benchmark

## Summary (arm H, 2026-10-11): Sonnet 5.5 (claude-sonnet-5-5), Claude Code 2.1.293, 1 repetition

Arm H is the plugin as shipped, loaded with `--plugin-dir`. It has the skill plus the SessionStart hook, which
adds the CLAUDE.md pointer line to the session context in repos that have a map. No file is edited. The questions
are the two held-out symptom sets: Typebot (v2.3) and Open WebUI (v2.2). The A, S and P rows here are copies of
those rounds' rows, and H was run a few hours later on the same CLI and model, so H was **not interleaved** with A.

| set | hit@3 A / S / P / H | H won / lost vs A | tokens vs A: S / P / H | cost vs A: S / P / H | tool calls A → H |
|---|---|---|---|---|---|
| Typebot | 18 / 16 / 18 / 17 | 0 / 1 | 0.88 / 0.89 / 0.77 | 0.86 / 0.89 / 0.80 | 4.3 → 2.5 |
| Open WebUI | 20 / 20 / 19 / 19 | 0 / 1 | 0.85 / 0.72 / 0.70 | 0.90 / 0.83 / 0.80 | 6.1 → 2.8 |

- The hook fired in 40/40 runs, and Claude invoked the skill in 40/40.
- H saves at least as much as P, the CLAUDE.md pointer: 23–30% fewer tokens and 20% lower cost. It loses one
  question per set, as P does.

## Results by arm

Each cell: mean ± std over runs (questions × repetitions). tokens_in = input + cache creation + cache read (everything the model processed). hit@3 = a gold file among the first 3 files named; recall@3 = fraction of gold files among them; func_hit = a gold function named in the answer. src KB = bytes returned by Read on source files (not .atlas/.claude).

| repo | arm | n | hit@3 | recall@3 | func_hit | tokens_in | tokens_out | tool calls | src KB | skill used |
|---|---|---|---|---|---|---|---|---|---|---|
| open-webui | A | 20 | 100% | 92% | 87% | 91027 ± 88625 | 1714 ± 1115 | 6.1 ± 4.8 | 6.1 ± 9.5 | 0% |
| open-webui | H | 20 | 95% | 84% | 87% | 63294 ± 61809 | 941 ± 786 | 2.8 ± 2.9 | 2.3 ± 8.5 | 100% |
| open-webui | P | 20 | 95% | 87% | 87% | 65641 ± 42936 | 1085 ± 704 | 3.6 ± 3.0 | 1.7 ± 2.7 | 100% |
| open-webui | S | 20 | 100% | 87% | 93% | 77655 ± 58923 | 1288 ± 968 | 4.7 ± 4.1 | 3.8 ± 5.1 | 55% |
| typebot.io | A | 20 | 90% | 72% | 100% | 65492 ± 20017 | 1214 ± 365 | 4.3 ± 1.4 | 2.7 ± 3.7 | 0% |
| typebot.io | H | 20 | 85% | 74% | 89% | 50129 ± 17937 | 730 ± 321 | 2.5 ± 1.4 | 0.3 ± 0.5 | 100% |
| typebot.io | P | 20 | 90% | 74% | 95% | 58281 ± 37052 | 794 ± 522 | 2.7 ± 2.2 | 1.1 ± 2.3 | 100% |
| typebot.io | S | 20 | 80% | 71% | 89% | 57706 ± 25274 | 869 ± 434 | 2.9 ± 1.9 | 1.4 ± 2.2 | 75% |

## Paired tests vs A (same question; exact sign / McNemar tests, two-sided)

| repo | arm | hit@3 arm-only / A-only (p) | func_hit arm-only / A-only (p) | tokens_in arm/A median | cheaper than A (p) | cost arm/A |
|---|---|---|---|---|---|---|
| open-webui | H | 0 / 1 (1.00) | 2 / 2 (1.00) | 0.69 | 15/20 (0.041) | 0.80 |
| open-webui | P | 0 / 1 (1.00) | 2 / 2 (1.00) | 0.81 | 14/20 (0.115) | 0.83 |
| open-webui | S | 0 / 0 (1.00) | 1 / 0 (1.00) | 0.85 | 12/20 (0.503) | 0.90 |
| typebot.io | H | 0 / 1 (1.00) | 0 / 2 (0.50) | 0.76 | 15/20 (0.041) | 0.80 |
| typebot.io | P | 1 / 1 (1.00) | 0 / 1 (1.00) | 0.71 | 14/20 (0.115) | 0.89 |
| typebot.io | S | 0 / 2 (0.50) | 0 / 2 (0.50) | 0.89 | 11/20 (0.824) | 0.86 |
| all | H | 0 / 2 (0.50) | 2 / 4 (0.69) | 0.70 | 30/40 (0.002) | 0.80 |
| all | P | 1 / 2 (1.00) | 2 / 3 (1.00) | 0.75 | 28/40 (0.017) | 0.86 |
| all | S | 0 / 2 (0.50) | 1 / 2 (1.00) | 0.85 | 23/40 (0.430) | 0.88 |
