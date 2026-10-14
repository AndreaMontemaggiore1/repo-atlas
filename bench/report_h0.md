# repo-atlas: LLM benchmark

## H0: the plugin on a repo it has never seen (2026-10-14): Sonnet 5.5, Claude Code 2.1.295 (new build)

H0 is the plugin with no prebuilt map. The copy is a one-commit git snapshot, so there is no history to leak
answers, and the hook can count the tracked files. With at least 200 tracked code files and no map, the hook now
suggests the skill. The first lookup builds the map inside the invocation, which took 11–14 s on Typebot. The A
rows are the re-check's A runs on the same build and questions, run in parallel.

| set | n | hit@3 A → H0 | H0 won / lost | tokens vs A | per-question ratio median | cheaper than A | cost vs A | tool calls A → H0 |
|---|---|---|---|---|---|---|---|---|
| Typebot | 20 | 12 → 13 | 1 / 0 | 0.69× | 0.72 | 17/20 (p = 0.003) | 0.82× | 4.0 → 1.8 |
| Open WebUI | 20 | 20 → 20 | 0 / 0 | 0.78× | 0.78 | 14/20 | 0.87× | 5.9 → 3.5 |

- The hook fired in 40/40 runs, and Claude invoked the skill in 38/40.
- First use costs a little more than with a prebuilt map (0.69–0.78× against 0.63–0.69×), because every run
  here builds the map. In real use the map is built once per repo.

## Results by arm

Each cell: mean ± std over runs (questions × repetitions). tokens_in = input + cache creation + cache read (everything the model processed). hit@3 = a gold file among the first 3 files named; recall@3 = fraction of gold files among them; func_hit = a gold function named in the answer. src KB = bytes returned by Read on source files (not .atlas/.claude).

| repo | arm | n | hit@3 | recall@3 | func_hit | tokens_in | tokens_out | tool calls | src KB | skill used |
|---|---|---|---|---|---|---|---|---|---|---|
| open-webui | A | 20 | 100% | 92% | 87% | 89522 ± 67318 | 1603 ± 785 | 5.9 ± 3.2 | 5.8 ± 8.7 | 0% |
| open-webui | H0 | 20 | 100% | 89% | 93% | 69986 ± 52440 | 1063 ± 685 | 3.5 ± 2.7 | 2.3 ± 4.8 | 90% |
| typebot.io | A | 20 | 60% | 47% | 76% | 61975 ± 23545 | 1185 ± 468 | 4.0 ± 1.8 | 3.9 ± 4.0 | 0% |
| typebot.io | H0 | 20 | 65% | 52% | 76% | 42844 ± 15559 | 628 ± 214 | 1.8 ± 1.1 | 0.4 ± 0.9 | 100% |

## Paired tests vs A (same question; exact sign / McNemar tests, two-sided)

| repo | arm | hit@3 arm-only / A-only (p) | func_hit arm-only / A-only (p) | tokens_in arm/A median | cheaper than A (p) | cost arm/A |
|---|---|---|---|---|---|---|
| open-webui | H0 | 0 / 0 (1.00) | 1 / 0 (1.00) | 0.78 | 14/20 (0.115) | 0.87 |
| typebot.io | H0 | 1 / 0 (1.00) | 1 / 1 (1.00) | 0.72 | 17/20 (0.003) | 0.82 |
| all | H0 | 1 / 0 (1.00) | 2 / 1 (1.00) | 0.74 | 31/40 (0.001) | 0.85 |
