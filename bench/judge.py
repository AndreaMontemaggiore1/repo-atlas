#!/usr/bin/env python3
"""End-result check: would the answer have led to the change the real commit made?

hit@3 only looks at the first three file paths in the answer. This grader reads the whole answer next to the
question and the commit that resolved it, and gives a verdict:
  correct   following the answer, a developer lands on the code the commit changed (its main file and function,
            given as the main suggestion or one of a few clearly ranked ones)
  partial   the right place is in the answer but buried, hedged among many places, or the right file with the
            wrong function
  wrong     the answer does not lead to the code the commit changed
One headless `claude -p` session per answer, no tools, no project settings. The grader never sees the arm, and
the answers are graded in a shuffled order, with
mentions of the map or the skill redacted. Verdicts go to bench/<runs-dir>/judgments.jsonl, keyed by run and
by a hash of the answer; finished ones are skipped, so an interrupted batch resumes. score.py adds them to the
report.

usage: judge.py --runs-dir results/reps --max-usd 3 [--model sonnet]
Needs the clones under bench/repos/<name> (see bench/README.md) for the commit diffs.
"""
import argparse, hashlib, json, random, re, subprocess, tempfile
from pathlib import Path

import run_llm

HERE = Path(__file__).resolve().parent
DIFF_CHARS = 14000
VERDICTS = ("correct", "partial", "wrong")

PROMPT = """You grade answers to a code localization question asked about a software repository.

The question:
<question>
{question}
</question>

The commit that actually resolved it (subject, changed files, and diff; the diff may be cut):
<commit>
{commit}
</commit>

The answer to grade:
<answer>
{answer}
</answer>

Would a developer who follows this answer end up changing the code this commit changed?
- correct: the answer's main suggestion, or one of a few clearly ranked suggestions, is the file the commit
  mainly changed, and it points at the function or component the commit changed (or one that obviously contains
  the changed lines).
- partial: the right file or function appears, but only buried in a long list or hedged among many places, or
  the right file is named with the wrong function.
- wrong: the answer does not lead to the code the commit changed.
Only the commit's own changes count as the right place. Ignore tests, snapshots, lockfiles and translations in
the commit unless they are all it changed. Judge only where the answer points, not its style or length.

Reply with one line of JSON and nothing else: {{"verdict": "correct" | "partial" | "wrong", "reason": "<one sentence>"}}"""


def sh(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


_diffs = {}


def commit_text(repo, commit):
    """Subject, stat and diff of the gold commit, from the local clone."""
    if (repo, commit) not in _diffs:
        clone = HERE / "repos" / repo
        p = sh(["git", "show", "--no-color", "--format=%s%n", "--stat=200", "-p", commit], clone)
        if p.returncode:
            raise SystemExit(f"git show {commit} failed in {clone}: {p.stderr.strip()[:200]} (see bench/README.md)")
        text = p.stdout
        _diffs[(repo, commit)] = text if len(text) <= DIFF_CHARS else text[:DIFF_CHARS] + "\n[... diff cut ...]"
    return _diffs[(repo, commit)]


def answer_hash(answer):
    return hashlib.sha1((answer or "").encode("utf-8")).hexdigest()[:12]


def redact(answer):
    """Hide the arm: an answer can mention the map or the skill it used."""
    return re.sub(r"[\w./-]*\.atlas[\w./-]*|repo-atlas|\batlas\b", "[tool]", answer or "", flags=re.I)


def parse_verdict(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        v = json.loads(m.group(0)) if m else {}
    except ValueError:
        v = {}
    verdict = str(v.get("verdict", "")).strip().lower()
    return (verdict if verdict in VERDICTS else None), str(v.get("reason", ""))[:300]


def grade(prompt, model, cwd):
    cmd = [run_llm.CLAUDE, "-p", prompt, "--model", model, "--output-format", "json", "--no-session-persistence",
           "--setting-sources", "", "--tools", "", "--permission-mode", "dontAsk"]
    p = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    try:
        res = json.loads(p.stdout)
    except ValueError:
        return None, f"no JSON from claude: {(p.stderr or p.stdout)[-200:]}", 0.0, None
    verdict, reason = parse_verdict(res.get("result", ""))
    model_id = next(iter(res.get("modelUsage") or {}), None)
    return verdict, reason, res.get("total_cost_usd") or 0.0, model_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True, help="under bench/ (e.g. results/reps)")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--max-usd", type=float, required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    if not run_llm.CLAUDE:
        raise SystemExit("claude binary not found (set CLAUDE_BIN)")
    runs = HERE / a.runs_dir
    rows = [r for p in sorted(runs.glob("rows*.jsonl")) for r in run_llm.load_rows(p)
            if not r.get("is_error") and r.get("err") != "TIMEOUT"]
    cases = {(f.stem, c["id"]): c for f in (HERE / "evals").glob("*.json")
             for c in json.loads(f.read_text("utf-8"))["cases"]}
    out = runs / "judgments.jsonl"
    done = run_llm.load_rows(out)
    seen = {(j["repo"], j["arm"], j["case"], j["rep"], j["answer_sha"]) for j in done if j.get("verdict")}
    spent = sum(j.get("cost_usd") or 0 for j in done)
    todo = [r for r in rows if (r["repo"], r["arm"], r["case"], r["rep"], answer_hash(r.get("answer"))) not in seen]
    random.Random(a.seed).shuffle(todo)  # the grader sees answers in no particular arm order
    with tempfile.TemporaryDirectory() as cwd:  # empty dir: no repo, no CLAUDE.md
        for r in todo:
            if spent > a.max_usd:
                raise SystemExit(f"budget: spent ${spent:.2f} > --max-usd {a.max_usd}; stopping")
            c = cases[(r["repo"], r["case"])]
            prompt = PROMPT.format(question=c.get("question") or c["prompt"],
                                   commit=commit_text(r["repo"], c["commit"]), answer=redact(r.get("answer")))
            verdict, reason, cost, model_id = grade(prompt, a.model, cwd)
            spent += cost
            j = dict(repo=r["repo"], arm=r["arm"], case=r["case"], rep=r["rep"],
                     answer_sha=answer_hash(r.get("answer")), verdict=verdict, reason=reason,
                     judge_model=model_id, cost_usd=cost)
            with open(out, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(j) + "\n")
            print(f"{r['repo']} case{r['case']} rep{r['rep']}: {verdict} ${cost:.3f}", flush=True)


if __name__ == "__main__":
    main()
