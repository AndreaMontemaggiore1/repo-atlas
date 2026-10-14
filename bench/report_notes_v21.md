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
