# repo-atlas: LLM benchmark

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

## Results by arm

Each cell: mean ± std over runs (questions × repetitions). tokens_in = input + cache creation + cache read (everything the model processed). hit@3 = a gold file among the first 3 files named; recall@3 = fraction of gold files among them; func_hit = a gold function named in the answer. src KB = bytes returned by Read on source files (not .atlas/.claude). hit_any = a gold file named anywhere in the answer. correct / +partial = judge.py verdict on the whole answer against the real commit.

| repo | arm | n | hit@3 | recall@3 | func_hit | hit_any | correct | correct+partial | tokens_in | tokens_out | tool calls | src KB | skill used |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| typebot.io | A | 60 | 72% | 60% | 78% | 75% | 20% | 80% | 44980 ± 14168 | 1197 ± 344 | 3.8 ± 1.5 | 2.7 ± 3.2 | 0% |
| typebot.io | H | 60 | 68% | 56% | 78% | 72% | 40% | 73% | 39152 ± 14878 | 818 ± 332 | 2.4 ± 1.6 | 1.1 ± 1.8 | 100% |

## Paired tests vs A (same question; exact sign / McNemar tests, two-sided)

With repetitions, each question counts once: its mean over the runs, and the arm wins it when that mean is higher. Cells: questions the arm won / questions A won (p).

| repo | arm | hit@3 arm-only / A-only (p) | func_hit arm-only / A-only (p) | correct arm-only / A-only (p) | tokens_in arm/A median | cheaper than A (p) | cost arm/A |
|---|---|---|---|---|---|---|---|
| typebot.io | H | 2 / 3 (1.00) | 3 / 3 (1.00) | 9 / 2 (0.07) | 0.81 | 14/20 (0.115) | 0.91 |
| all | H | 2 / 3 (1.00) | 3 / 3 (1.00) | 9 / 2 (0.07) | 0.81 | 14/20 (0.115) | 0.91 |

## Repetitions (3 runs per question and arm)

Each repetition is a full pass over the questions, arms interleaved. Per repetition: how many questions the arm got right. Unstable = questions where the same arm got the metric right in some repetitions and wrong in others.

| repo | arm | questions | hit@3 per repetition | unstable (hit@3) | func_hit per repetition | unstable (func_hit) | correct per repetition | unstable (correct) | tokens_in mean per repetition |
|---|---|---|---|---|---|---|---|---|---|
| typebot.io | A | 20 | 14, 14, 15 | 3 | 14, 12, 14 | 4 | 4, 3, 5 | 4 | 43648, 45933, 45359 |
| typebot.io | H | 20 | 13, 14, 14 | 2 | 13, 14, 13 | 1 | 8, 8, 8 | 6 | 37644, 38723, 41090 |

Difference to A with a bootstrap 95% interval: questions resampled with replacement, each keeping all its runs (4000 resamples). An interval that contains 0 (or 1.00 for the token ratio) means the difference is within the noise.

| repo | arm | questions | hit@3 arm − A (points) | func_hit arm − A (points) | correct arm − A (points) | tokens_in arm/A |
|---|---|---|---|---|---|---|
| typebot.io | H | 20 | -3 [-17, +8] | +0 [-18, +19] | +20 [+5, +35] | 0.87 [0.75, 1.02] |
| all | H | 20 | -3 [-17, +8] | +0 [-18, +19] | +20 [+5, +35] | 0.87 [0.75, 1.02] |
