# repo-atlas: LLM benchmark

## Summary (v2.1 validation, 2026-10-11): Sonnet 5.5 (claude-sonnet-5-5), Claude Code 2.1.293, 1 repetition

Purpose: test the SKILL.md fix for the v2 accuracy loss on symptom questions. The fix: verify before answering
from merely nearby code; the lookup covers code only, so Grep for layouts, installers and configs.
Arms A (no skill) and S (fixed skill installed, no hint) are re-run together on the same CLI.

- **Held-out**: 20 new symptom questions on Open WebUI (Python + Svelte, ~278k code lines, monoliths up to
  6.7k lines with a 2.3k-line function). They were never used to tune the skill. Questions whose words name a
  gold file were dropped (14 of 34), so the set favours neither arm by name.
- **Regression**: the 36 v2 symptom questions (gPodder, Formbricks). The fix was written after reading their
  failures, so they are not a fair test of it.

| set | n | hit@3 A | hit@3 S | S won / lost (p) | tokens mean S/A | per-question ratio median | cost S/A | tool calls A → S | S invoked |
|---|---|---|---|---|---|---|---|---|---|
| Open WebUI (held-out) | 20 | 90% | 80% | 0 / 2 (0.50) | 0.81 | 0.82 | 0.87 | 5.4 → 3.5 | 65% |
| v2 questions | 36 | 81% | 81% | 3 / 3 (1.00) | 0.95 | 0.86 | 0.98 | 4.2 → 3.1 | 64% |
| all | 56 | 84% | 80% | 3 / 5 (0.73) | 0.89 | 0.84 | 0.94 | 4.7 → 3.3 | 64% |

Same 36 questions in v2, before the fix (CLI 2.1.288): A 89%, S 69%, 0 won / 7 lost (p = 0.016); tokens 0.80×, cost 0.85×.

Arm P (S + CLAUDE.md pointer) was run on the 20 Open WebUI questions afterwards, on the same day and CLI. It
reached hit@3 14/20 against A's 18/20 (0 won / 4 lost, p = 0.12), with tokens 0.83× and cost 0.92×. It invoked
the skill 20/20 times. In most lost questions the gold file was not among the lookup's results at all, and the
gold files were Svelte components ranked below backend files. That is a ranking failure, not a reading one,
and it led to v2.2.

### What this says

1. **The fix closed the accuracy gap on the questions it was built from**: 0/7 became 3/3. On the held-out set S
   is 2 questions behind, a difference that is not significant.
2. **It cost part of the saving.** On the v2 questions mean tokens went from 0.80× to 0.95× A: the extra
   verification step is the price. On the held-out big repo S still processes 19% fewer tokens (13% less cost).
3. **One repetition is noisy.** On the same questions A itself moved from 95% to 84% (gPodder) and from 82% to 76%
   (Formbricks) between rounds. Differences of 1–2 questions per repo are within that noise.
4. Both Open WebUI losses are the same pattern as before. The skill was invoked, and the model settled on an
   adjacent file: `automations.py` instead of `timers.py`, or the frontend instead of the backend.

### Incidents in this round

- Windows Storage Sense emptied the gPodder base copy in `%TEMP%`. 38 runs answered "no source files" and were
  discarded (not included in `results/`), the copy was rebuilt, and they were re-run. The runner now checks
  the copy before every round. Earlier rounds were checked and are not affected.
- The scorer did not recognise `.svelte` paths, which affected every Open WebUI answer. It is fixed, and all
  reports were re-scored.

## Results by arm

Each cell: mean ± std over runs (questions × repetitions). tokens_in = input + cache creation + cache read (everything the model processed). hit@3 = a gold file among the first 3 files named; recall@3 = fraction of gold files among them; func_hit = a gold function named in the answer. src KB = bytes returned by Read on source files (not .atlas/.claude).

| repo | arm | n | hit@3 | recall@3 | func_hit | tokens_in | tokens_out | tool calls | src KB | skill used |
|---|---|---|---|---|---|---|---|---|---|---|
| formbricks | A | 17 | 76% | 61% | 85% | 68456 ± 40043 | 1254 ± 627 | 4.4 ± 2.2 | 2.0 ± 3.1 | 0% |
| formbricks | S | 17 | 76% | 64% | 85% | 67697 ± 38410 | 1054 ± 621 | 3.4 ± 2.3 | 0.6 ± 1.9 | 82% |
| gpodder | A | 19 | 84% | 70% | 69% | 60855 ± 17062 | 1049 ± 403 | 4.1 ± 1.8 | 0.8 ± 1.6 | 0% |
| gpodder | S | 19 | 84% | 78% | 75% | 55260 ± 22660 | 858 ± 370 | 2.9 ± 1.3 | 0.3 ± 0.9 | 47% |
| open-webui | A | 20 | 90% | 86% | 64% | 78516 ± 36392 | 1460 ± 763 | 5.4 ± 3.3 | 2.8 ± 2.5 | 0% |
| open-webui | P | 20 | 70% | 63% | 57% | 64890 ± 42975 | 1024 ± 757 | 3.5 ± 3.2 | 2.0 ± 2.7 | 100% |
| open-webui | S | 20 | 80% | 76% | 50% | 63853 ± 26893 | 1031 ± 483 | 3.5 ± 1.8 | 2.1 ± 2.7 | 65% |

## Paired tests vs A (same question; exact sign / McNemar tests, two-sided)

| repo | arm | hit@3 arm-only / A-only (p) | func_hit arm-only / A-only (p) | tokens_in arm/A median | cheaper than A (p) | cost arm/A |
|---|---|---|---|---|---|---|
| formbricks | S | 1 / 1 (1.00) | 1 / 1 (1.00) | 0.89 | 9/17 (1.000) | 1.03 |
| gpodder | S | 2 / 2 (1.00) | 2 / 1 (1.00) | 0.83 | 12/19 (0.359) | 0.93 |
| open-webui | P | 0 / 4 (0.12) | 2 / 3 (1.00) | 0.79 | 12/20 (0.503) | 0.92 |
| open-webui | S | 0 / 2 (0.50) | 1 / 3 (0.62) | 0.82 | 11/20 (0.824) | 0.87 |
| all | P | 0 / 4 (0.12) | 2 / 3 (1.00) | 0.79 | 12/20 (0.503) | 0.92 |
| all | S | 3 / 5 (0.73) | 4 / 5 (1.00) | 0.84 | 32/56 (0.350) | 0.94 |
