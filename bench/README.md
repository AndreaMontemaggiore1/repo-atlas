# Benchmark

Does the skill lower the tokens Claude Code spends finding code, without lowering accuracy? Each run is one
fresh headless `claude -p` session on a fresh copy of a public repo. Every run gets the same question, the
same tools and the same CLI version, and the arms are interleaved question by question.

- **Questions.** `make_localization_evals.py` turns recent commits into questions ("where is the code I would
  change to: <commit subject>?"). The gold answer is the files and functions the commit touched.
  `make_symptom_questions.py` rewrites the subjects as a product owner would ask them, with no identifiers, in
  one tool-less session that never sees the code. Questions that still name a gold file or function are dropped.
- **Arms.** A: no skill. S: skill installed with a prebuilt map, no hint anywhere. P: S plus the 2-line
  CLAUDE.md pointer written by `atlas init --claude-md`.
- **Metrics.** hit@3: a gold file among the first three files the answer names. func_hit: a gold function is
  named. hit_any: a gold file named anywhere in the answer. tokens_in: input + cache creation + cache read,
  everything the model processed. API-equivalent cost (`total_cost_usd`). Paired exact sign / McNemar tests
  against A on the same question.
- **End result.** hit@3 only reads the first three paths. `judge.py` grades the whole answer: a tool-less
  `claude -p` session sees the question, the commit that resolved it and the answer (arm hidden, mentions of the
  map redacted, shuffled order) and says correct, partial or wrong: would following the answer lead to the code
  the commit changed?
- **Repetitions.** `--reps N` runs every question N times per arm. The report then shows each metric per
  repetition, how many questions flip between repetitions of the same arm, and bootstrap 95% intervals (questions
  resampled) for the difference to A, so a 12 vs 13 out of 20 can be told apart from noise.

## Reproduce

```bash
mkdir -p bench/repos
git clone https://github.com/gpodder/gpodder bench/repos/gpodder && git -C bench/repos/gpodder checkout 357161a6136585232fd47ae183ed22a9f342fc97
git clone https://github.com/formbricks/formbricks bench/repos/formbricks && git -C bench/repos/formbricks checkout 6fdf37a623020a348e8816964c1ffc4466d4537c
git clone https://github.com/open-webui/open-webui bench/repos/open-webui && git -C bench/repos/open-webui checkout 8bd8b4fac5e059578ac0c74b3c18d11139f88b7d
git clone https://github.com/baptisteArno/typebot.io bench/repos/typebot.io && git -C bench/repos/typebot.io checkout b19de808de32d5f4f376b3c5750676b5f4a656aa
git clone --depth 400 https://github.com/danny-avila/LibreChat bench/repos/librechat && git -C bench/repos/librechat checkout e1dfc10449ff713faffacd60273fddcfe2c0a698
git clone --depth 400 https://github.com/langgenius/dify bench/repos/dify && git -C bench/repos/dify checkout 5fe7f018764e94aefa06f098a23e28a55d6b4e18

python bench/run_llm.py --repos open-webui --arms A S H --cases $(seq 141 180) --max-usd 10 --runs-dir runs/mine
python bench/judge.py --runs-dir runs/mine --max-usd 2      # optional: end-result verdicts
python bench/score.py --runs-dir runs/mine --out report_mine.md
```

`run_llm.py` never modifies `bench/repos/`. It works on copies in the system temp directory (`ATLAS_BENCH_WORK`
overrides it) and stops at `--max-usd`. On a Pro/Max plan, `--max-week` and `--max-5h` keep it within the plan's
usage windows. Re-running the same command resumes and skips finished runs. Raw session logs stay in
`bench/runs/`, which is not committed.

## Results in this repo

| round | date | CLI | questions | arms | report |
|---|---|---|---|---|---|
| v2 | 2026-10-07 | 2.1.288 | gPodder + Formbricks, 60 commit + 36 symptom | A, S, P | [report_v2.md](report_v2.md) |
| v2.1 | 2026-10-11 | 2.1.293 | 20 held-out symptom (Open WebUI) + the 36 v2 symptom | A, S (+ P on Open WebUI) | [report_v21.md](report_v21.md) |
| v2.2 | 2026-10-11 | 2.1.293 | 20 new held-out symptom (Open WebUI, older commits) | A, S, P | [report_v22.md](report_v22.md) |
| v2.3 | 2026-10-11 | 2.1.293 | 20 held-out symptom (Typebot) + re-test of the v2.1 Open WebUI set | A, S, P | [report_v23.md](report_v23.md) |
| H | 2026-10-11 | 2.1.293 | Typebot + Open WebUI v2.2 sets: the plugin as shipped (skill + hook) | H (+ the A, S, P rows of those rounds) | [report_h1.md](report_h1.md) |
| Haiku | 2026-10-11/12 | 2.1.293 | Typebot + Open WebUI v2.2 sets, Haiku 5.5 | A, S, H | [report_haiku1.md](report_haiku1.md) |
| v2.4 | 2026-10-11/12 | 2.1.293 | 20 + 20 held-out symptom (LibreChat, Dify) | A, S, P | [report_v24.md](report_v24.md) |
| description | 2026-10-12 | 2.1.293 | 20 triggering prompts: current vs shorter description | S, S-short | [report_desc.md](report_desc.md) |
| final | 2026-10-12 | 2.1.295 | 20 new held-out symptom (Typebot, older commits) | A, H | [report_final.md](report_final.md) |
| Opus | 2026-10-12 | 2.1.295 | 10 of the final questions, Opus 5.5 | A, H | [report_opus1.md](report_opus1.md) |
| re-check | 2026-10-14 | 2.1.295 (new build) | final Typebot + Open WebUI v2.2 sets; triggering prompts | A, H (S for triggering) | [report_recheck.md](report_recheck.md) |
| H0 | 2026-10-14 | 2.1.295 (new build) | same sets: the plugin on a repo with no map yet | H0 (+ the re-check's A rows) | [report_h0.md](report_h0.md) |
| re-check Haiku / Opus | 2026-10-14 | 2.1.295 (new build) | final Typebot set (Opus: 10 questions) | A, H | [Haiku](report_recheck_haiku.md), [Opus](report_recheck_opus.md) |

Arm H is the plugin loaded with `--plugin-dir`: the skill plus the SessionStart hook. H0 is the same plugin on a
copy with no map and a one-commit git snapshot (no history), so the first lookup builds the map. Model: Sonnet 5.5
(`claude-sonnet-5-5`) unless the round says Haiku 5.5 (`claude-haiku-5-5`); each row records the model id.

`results/<round>/rows.jsonl` holds one row per run: answer, tokens, tools, cost and plan usage. Local paths are
removed. `score.py --runs-dir results/v2 --out report_v2.md` regenerates a report from the rows.

Known limits: 1 repetition per question, LLM-written symptom questions, and Opus not tested. A gold answer comes
from a single commit, so another valid place counts as a miss for every arm alike.
