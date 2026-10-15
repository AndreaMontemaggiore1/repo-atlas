# Changelog

## Unreleased

- Benchmark: `--reps` is now scored. The report shows each metric per repetition, how many questions flip between
  runs of the same arm, and bootstrap 95% intervals for the difference to A. New `hit_any` metric.
- Benchmark: `bench/judge.py` grades the final answer against the commit that resolved the question (correct,
  partial or wrong), blind to the arm.
- Measured on CLI 2.1.300 with 3 repetitions (Typebot, Sonnet 5.5): hit@3 equal within noise, answers graded
  correct 40% with the plugin vs 20% without, tokens 0.87× (95% interval 0.75–1.02). The 23–30% saving of 0.3.0
  was measured on 2.1.295 and did not reproduce here.

## 0.3.0

- Plugin: a `SessionStart` hook (`atlas session-start`) tells Claude that the map exists, in repos that already
  have one, or in git repos with at least 200 tracked code files, so the first lookup happens in a repo it has
  never seen (the map then builds in seconds). No file is edited, and folders without git get nothing. Measured
  as arm H: 23–30% fewer tokens than no skill with Sonnet 5.5, and about half with Haiku 5.5.
- `find` names the next 4 distinct matching files after its ranked results.
- The map is built 4× faster on repos with Go code: a 13k-file repo went from 86 s to 21 s, within the 2-minute
  limit of the first invocation.
- `.atlas/.gitignore` is written on the first automatic build.
- Very large repos (over 30,000 code files): the first map is built by a detached background process, because the
  skill's injected command has a 2-minute limit. Until the map is ready, the lookup tells Claude to use Grep.
- SKILL.md: check before answering from merely nearby code; run follow-up lookups exactly as written, because a
  `cd … &&` form is not pre-approved.
- Tried and dropped: a description of about 84 tokens instead of 188, to save tokens on every call. On the same
  CLI, the skill fired on 5/10 prompts that should use it, against 8/10 with the current description. The first
  use in a repo depends on the description, so it stays.

## 0.2.1

- First public version: the skill invocation runs the lookup itself (one turn); map with ranking, duplicates,
  co-change, unreferenced and generated files; notes; benchmark.
