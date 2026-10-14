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
