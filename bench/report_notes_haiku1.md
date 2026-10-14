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
