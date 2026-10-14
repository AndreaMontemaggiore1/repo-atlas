## Re-check on the updated build (2026-10-14): Claude Code 2.1.295 (new build), 1 repetition

After a Claude Code update, the published checks were re-run on the same questions: the final Typebot set
(older commits) and the Open WebUI v2.2 set, both held out. A (no skill) and H (the plugin, prebuilt map) were
interleaved. Models are the latest aliases: `claude-sonnet-5-5`, `claude-haiku-5-5` and `claude-opus-5-5`.

| model, set | n | hit@3 A → H | H won / lost | tokens vs A | per-question ratio median | cheaper than A | cost vs A | tool calls A → H |
|---|---|---|---|---|---|---|---|---|
| Sonnet 5.5, Typebot | 20 | 12 → 13 | 2 / 1 | 0.63× | 0.69 | 16/20 (p = 0.012) | 0.81× | 4.0 → 1.6 |
| Sonnet 5.5, Open WebUI | 20 | 20 → 18 | 0 / 2 | 0.69× | 0.72 | 14/20 | 0.81× | 5.9 → 3.0 |
| Haiku 5.5, Typebot | 20 | 16 → 13 | 0 / 3 | 0.70× | 0.68 | 16/20 (p = 0.012) | 0.69× | 6.5 → 3.2 |
| Opus 5.5, Typebot | 10 | 7 → 7 | 0 / 0 | 0.79× | 0.76 | 8/10 | 0.79× | 5.8 → 3.7 |

Triggering (gPodder prompts, skill alone, prebuilt map): 6/10 should-trigger prompts fired and 0/10 should-not.
The same description fired on 10/10 with CLI 2.1.288 (2026-10-07) and 8/10 with 2.1.293 (2026-10-12). The model
reaches for Grep more often on "where is the code that…" questions. This is why the plugin's hook now also
suggests the skill in big git repos without a map (see report_h0.md).

Cost of the re-check: $11.11 including H0.
