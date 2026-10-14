## Repetitions and end result (2026-10-14): Claude Code 2.1.300, Sonnet 5.5, 3 repetitions

The final Typebot set (20 held-out symptom questions), A (no skill) against H (the plugin, prebuilt map), each
question run 3 times per arm, arms interleaved. Two questions from a reader of the earlier rounds: is a 12 vs 13
out of 20 more than noise, and is the final answer still right, not just the first three paths?

| metric | A | H | H − A, bootstrap 95% interval | questions H won / A won (sign test) |
|---|---|---|---|---|
| hit@3 per repetition (of 20) | 14, 14, 15 | 13, 14, 14 | −3 points [−17, +8] | 2 / 3 (p = 1.00) |
| answer graded correct per repetition (of 20) | 4, 3, 5 | 8, 8, 8 | +20 points [+5, +35] | 9 / 2 (p = 0.07) |
| answer graded correct or partial | 80% | 73% | | |
| tokens_in, mean | 44,980 | 39,152 | 0.87× [0.75, 1.02] | cheaper on 14/20 (p = 0.12) |
| tool calls, mean | 3.8 | 2.4 | | |
| cost (API-equivalent) | | | 0.91× | |

- **Noise.** The same arm moves by one question between repetitions (14–15 for A, 13–14 for H), and 2–3
  questions per arm flip between hit and miss. A one- or two-question gap in a single run, like the 12 → 13 and
  12 → 14 of earlier rounds, is inside that noise. On hit@3 the two arms are the same.
- **End result.** `judge.py` graded every answer against the commit that resolved the question, blind to the
  arm. H's answers were graded correct about twice as often (40% vs 20%). A's answers more often name the right
  place among many hedged candidates (partial), so correct-or-partial is about the same (80% vs 73%). The
  grader rewards a short, committed answer, and H's answers are shorter (818 vs 1,197 output tokens), so read this
  as "no loss in answer quality, maybe a gain", not as proof of a gain.
- **Tokens.** On this CLI the baseline itself got cheaper (A: 61k tokens per question on 2.1.295, 45k now), and
  the saving shrank to 13% (0.87×), with an interval that reaches 1.02. On this set and CLI the saving is not
  significant. The earlier rounds (0.63–0.69× on 2.1.295) are not reproduced here.
- Cost of the round: $5.28 for the 120 runs and $2.14 for grading.
