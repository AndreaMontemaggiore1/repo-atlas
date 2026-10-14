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
