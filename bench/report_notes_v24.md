## Summary (v2.4 held-out round, 2026-10-11/12): Sonnet 5.5 (claude-sonnet-5-5), Claude Code 2.1.293, 1 repetition

Two large apps never used before, cloned with the last 400 commits. 20 symptom questions each, generated and not
read before the runs. Arms A / S / P interleaved. The round was interrupted overnight and resumed on the same CLI.

- **LibreChat**: JS/TS, React + Node, 6.2k files, monoliths up to 9.8k lines, 93 duplicate bodies.
- **Dify**: Python backend + Next.js frontend, 13k files, large generated type files, 208 duplicate bodies.

| repo | arm | hit@3 | won / lost vs A (p) | tokens mean vs A | per-question ratio median | cheaper than A | cost vs A | tool calls |
|---|---|---|---|---|---|---|---|---|
| LibreChat | A | 18/20 | | 117.4k | | | | 7.2 |
| | S | 15/20 | 0 / 3 (0.25) | 0.67× | 0.68 | 17/20 (p = 0.003) | 0.75× | 4.0 |
| | P | 16/20 | 0 / 2 (0.50) | 1.07× | 0.71 | 15/20 (p = 0.04) | 0.92× | 5.2 |
| Dify | A | 16/20 | | 88.8k | | | | 5.9 |
| | S | 17/20 | 2 / 1 (1.00) | 0.96× | 1.01 | 10/20 | 1.00× | 4.7 |
| | P | 17/20 | 2 / 1 (1.00) | 0.74× | 0.68 | 14/20 | 0.80× | 3.1 |

- LibreChat's mean for P is pulled up by one question that every arm failed. A used 475k tokens on it, S 426k and
  P 1.26M (42 tool calls). P's later lookups were refused in this headless mode because they were written as
  `cd … && bash …`, which is not the pre-approved form, so the model fell back to 30 Greps. SKILL.md now says to
  run the command exactly as written.
- On Dify, S does not save tokens, while P saves 26% of tokens and 20% of cost. With the pointer the skill is
  used consistently, and that is what pays off.
- In every LibreChat question the skill arms lost, the gold file was missing from the lookup's output. That is
  the ranking limit on vague questions.
- Cost of the round: $9.71.
