## Summary (v2.2 held-out round, 2026-10-11): Sonnet 5.5 (claude-sonnet-5-5), Claude Code 2.1.293, 1 repetition

Change under test: `find` also names the next 4 distinct matching files after its 5 ranked results, and SKILL.md
says to check them when the shown code is only nearby. On a zero-token proxy it put the gold file somewhere in the
output for 111 of 156 questions instead of 92, across three repos.

Questions: 20 new symptom questions on Open WebUI, made from commits 41–80 (older than the v2.1 set). They were
generated after the change and not read before the runs.

| arm | hit@3 | won / lost vs A (p) | tokens mean | vs A | per-question ratio median | cheaper than A | cost vs A | tool calls | skill invoked |
|---|---|---|---|---|---|---|---|---|---|
| A | 20/20 | | 91.0k | | | | | 6.1 | |
| S | 20/20 | 0 / 0 | 77.7k | 0.85× | 0.85 | 12/20 | 0.90× | 4.7 | 11/20 |
| P | 19/20 | 0 / 1 (1.00) | 65.6k | 0.72× | 0.81 | 14/20 (p = 0.12) | 0.83× | 3.6 | 20/20 |

- Every arm found a gold file in almost every question. The set is easier than the v2.1 one, where A had 18/20,
  so it cannot show an accuracy gain. It does show no accuracy loss at lower cost.
- P, with the CLAUDE.md pointer, saves the most: 28% fewer tokens, 17% lower cost, 2.5 fewer tool calls.
- S invoked the skill on its own in 11/20 questions. When it did not, it behaved like A.
