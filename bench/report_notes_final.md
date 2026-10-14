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
