#!/usr/bin/env python3
"""Score bench/<runs-dir>/rows.jsonl -> bench/<out> (markdown).

Per run: hit@3 (a gold file among the first 3 files the answer names), recall@3, func_hit (a gold function
named), tokens_in (input + cache creation + cache read: everything the model processed), tool calls, source
bytes read; hit_any (a gold file named anywhere in the answer); the end-result verdict of judge.py when
bench/<runs-dir>/judgments.jsonl exists. Aggregates per repo and arm; by question kind; paired exact sign tests vs
arm A on the same question (with repetitions, on each question's mean over its runs); with repetitions, the spread
between them and bootstrap 95% intervals over questions; triggering table. A hand-written interpretation is put on top if it exists:
report_v2.md -> report_notes_v2.md.

usage: score.py --runs-dir results/v2 --out report_v2.md
"""
import argparse, hashlib, json, random, re, statistics as st
from math import comb
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXT = r"(?:py|pyi|js|jsx|ts|tsx|mjs|cjs|mts|cts|svelte|vue|astro|go|sql|sh|ui|nsi|rs|java|kt|swift|scala|rb|php|cs|cpp|hpp|c|h)"
PATH_RX = re.compile(r"((?:[\w@()\[\].-]+/)*[\w@()\[\]-][\w@()\[\].-]*\." + EXT + r")(?![\w])")


def answer_files(text):
    text = text.replace("\\", "/")
    text = re.sub(r"[A-Za-z]:/\S*?/runs/[^/\s]+/", "", text)  # absolute paths into the run copy
    out = []
    for m in PATH_RX.finditer(text):
        p = m.group(1).lstrip("./") if m.group(1).startswith("./") else m.group(1)
        if p not in out:
            out.append(p)
    return out


def same_file(p, gold):
    return p == gold or gold.endswith("/" + p) or p.endswith("/" + gold)


def score_row(row, case):
    files = answer_files(row.get("answer") or "")[:3]
    gold = case["gold_files"]
    found = [g for g in gold if any(same_file(p, g) for p in files)]
    names = {n for f in case["gold_functions"] for n in (f, f.split(".")[-1])}
    text = row.get("answer") or ""
    func = any(re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", text) for n in names) if names else None
    anywhere = any(same_file(p, g) for p in answer_files(text) for g in gold)
    return {"hit3": bool(found), "recall3": len(found) / len(gold), "func_hit": func, "files": files,
            "hit_any": anywhere,
            "tokens_in": row["input_tokens"] + row["cache_creation"] + row["cache_read"]}


def sign_p(k, n):
    """Two-sided exact binomial (sign / exact McNemar) test, p = 0.5."""
    if n == 0:
        return 1.0
    k = min(k, n - k)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


KEY = {"hit@3": "hit3"}  # display name -> row key


def bootstrap(qs, stat, n=4000, seed=0):
    """95% percentile interval of stat(sample) over resamples of the questions (each keeps all its runs)."""
    rng = random.Random(seed)
    vals = sorted(stat([rng.choice(qs) for _ in qs]) for _ in range(n))
    return vals[int(0.025 * n)], vals[int(0.975 * n) - 1]


def qmean(rs, m):
    m = KEY.get(m, m)
    xs = [r[m] for r in rs if r.get(m) is not None]
    return st.mean(xs) if xs else None


def ms(xs, fmt="{:.0f}"):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "n/a"
    sd = st.stdev(xs) if len(xs) > 1 else 0
    return f"{fmt.format(st.mean(xs))} ± {fmt.format(sd)}"


def pct(g, m):
    xs = [r[m] for r in g if r.get(m) is not None]
    return f"{100 * st.mean(xs):.0f}%" if xs else "n/a"


def repetitions(rows, perq, repos, arms, metrics):
    """How much the same arm moves between repetitions, and whether the gap to A is larger than that."""
    reps = sorted({r["rep"] for r in rows})
    L = ["", f"## Repetitions ({len(reps)} runs per question and arm)", "",
         "Each repetition is a full pass over the questions, arms interleaved. Per repetition: how many questions "
         "the arm got right. Unstable = questions where the same arm got the metric right in some repetitions and "
         "wrong in others.", "",
         "| repo | arm | questions | " + " | ".join(f"{m} per repetition | unstable ({m})" for m in metrics)
         + " | tokens_in mean per repetition |",
         "|---|---|---|" + "---|---|" * len(metrics) + "---|"]
    for repo in repos:
        for arm in arms:
            qs = [k for k in perq if k[0] == repo and k[1] == arm]
            if not qs:
                continue
            cells = []
            for m in metrics:
                per = [sum(1 for r in rows if r["repo"] == repo and r["arm"] == arm and r["rep"] == k and r.get(KEY.get(m, m)))
                       for k in reps]
                unstable = sum(1 for k in qs if len({bool(r[KEY.get(m, m)]) for r in perq[k]
                                                    if r.get(KEY.get(m, m)) is not None}) > 1)
                cells.append(f"{', '.join(map(str, per))} | {unstable}")
            tok = [st.mean(r["tokens_in"] for r in rows if r["repo"] == repo and r["arm"] == arm and r["rep"] == k)
                   for k in reps if any(r["repo"] == repo and r["arm"] == arm and r["rep"] == k for r in rows)]
            L.append(f"| {repo} | {arm} | {len(qs)} | {' | '.join(cells)} | {', '.join(f'{t:.0f}' for t in tok)} |")
    L += ["", "Difference to A with a bootstrap 95% interval: questions resampled with replacement, each keeping all "
          "its runs (4000 resamples). An interval that contains 0 (or 1.00 for the token ratio) means the "
          "difference is within the noise.", "",
          "| repo | arm | questions | " + " | ".join(f"{m} arm − A (points)" for m in metrics)
          + " | tokens_in arm/A |", "|---|---|---|" + "---|" * (len(metrics) + 1)]
    for repo in repos + ["all"]:
        for arm in [x for x in arms if x != "A"]:
            qs = sorted((rp, c) for (rp, a_, c) in perq if a_ == "A" and (repo == "all" or rp == repo)
                        and (rp, arm, c) in perq)
            if not qs:
                continue
            pairs = {q: (perq[(q[0], "A", q[1])], perq[(q[0], arm, q[1])]) for q in qs}
            cells = []
            for m in metrics:
                def diff(sample, m=m):
                    d = [(qmean(b, m), qmean(a, m)) for a, b in (pairs[q] for q in sample)]
                    d = [x - y for x, y in d if x is not None and y is not None]
                    return 100 * st.mean(d) if d else 0.0
                lo, hi = bootstrap(qs, diff)
                cells.append(f"{diff(qs):+.0f} [{lo:+.0f}, {hi:+.0f}]")

            def tok(sample):
                return (sum(qmean(pairs[q][1], "tokens_in") for q in sample)
                        / sum(qmean(pairs[q][0], "tokens_in") for q in sample))
            lo, hi = bootstrap(qs, tok)
            L.append(f"| {repo} | {arm} | {len(qs)} | {' | '.join(cells)} | {tok(qs):.2f} [{lo:.2f}, {hi:.2f}] |")
    return L


def load_jsonl(p):
    return [json.loads(l) for l in p.read_text("utf-8").splitlines() if l.strip()] if p.exists() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", default="runs", help="under bench/ (e.g. results/v2)")
    ap.add_argument("--out", default="report.md", help="under bench/")
    a = ap.parse_args()
    runs = HERE / a.runs_dir
    all_rows = [r for p in sorted(runs.glob("rows*.jsonl")) for r in load_jsonl(p)]  # rows.jsonl (+ rows-2.jsonl...)
    rows = [r for r in all_rows if not r.get("is_error") and r.get("err") != "TIMEOUT"]
    errors = [r for r in all_rows if r.get("is_error") or r.get("err") == "TIMEOUT"]
    cases = {}
    for f in (HERE / "evals").glob("*.json"):
        for c in json.loads(f.read_text("utf-8"))["cases"]:
            cases[(f.stem, c["id"])] = c
    verdicts = {(j["repo"], j["arm"], j["case"], j["rep"], j["answer_sha"]): j["verdict"]
                for j in load_jsonl(runs / "judgments.jsonl") if j.get("verdict")}
    by = defaultdict(list)
    for r in rows:
        r.update(score_row(r, cases[(r["repo"], r["case"])]))
        sha = hashlib.sha1((r.get("answer") or "").encode("utf-8")).hexdigest()[:12]
        v = verdicts.get((r["repo"], r["arm"], r["case"], r["rep"], sha))
        r["verdict"] = v
        r["correct"] = None if v is None else v == "correct"
        r["correct_or_partial"] = None if v is None else v != "wrong"
        by[(r["repo"], r["arm"])].append(r)
    judged = any(r["verdict"] for r in rows)
    reps = max((r["rep"] for r in rows), default=1)
    repos = sorted({r["repo"] for r in rows})
    arms = sorted({r["arm"] for r in rows})

    notes = HERE / (Path(a.out).stem.replace("report", "report_notes", 1) + ".md")
    L = ["# repo-atlas: LLM benchmark", ""] + ([notes.read_text("utf-8").rstrip(), ""] if notes.exists() else []) + [
         "## Results by arm", "",
         "Each cell: mean ± std over runs (questions × repetitions). tokens_in = input + cache creation + cache read "
         "(everything the model processed). hit@3 = a gold file among the first 3 files named; recall@3 = fraction of "
         "gold files among them; func_hit = a gold function named in the answer. src KB = bytes returned by Read on "
         "source files (not .atlas/.claude). hit_any = a gold file named anywhere in the answer."
         + (" correct / +partial = judge.py verdict on the whole answer against the real commit." if judged else ""), ""]
    hdr = ("| repo | arm | n | hit@3 | recall@3 | func_hit | hit_any |" + (" correct | correct+partial |" if judged else "")
           + " tokens_in | tokens_out | tool calls | src KB | skill used |")
    L += [hdr, "|" + "---|" * (hdr.count("|") - 1)]
    for repo in repos:
        for arm in arms:
            g = by.get((repo, arm), [])
            if not g:
                continue
            fh = [r["func_hit"] for r in g if r["func_hit"] is not None]
            L.append(f"| {repo} | {arm} | {len(g)} | {100 * st.mean(r['hit3'] for r in g):.0f}% | "
                     f"{100 * st.mean(r['recall3'] for r in g):.0f}% | {100 * st.mean(fh) if fh else 0:.0f}% | "
                     f"{100 * st.mean(r['hit_any'] for r in g):.0f}% | " + (
                         f"{pct(g, 'correct')} | {pct(g, 'correct_or_partial')} | " if judged else "") +
                     f"{ms([r['tokens_in'] for r in g])} | {ms([r['output_tokens'] for r in g])} | "
                     f"{ms([r['tool_calls'] for r in g], '{:.1f}')} | {ms([r['src_bytes_read'] / 1024 for r in g], '{:.1f}')} | "
                     f"{100 * st.mean(r['skill_invoked'] for r in g):.0f}% |")
    kinds = sorted({r.get("kind", "commit") for r in rows})
    if len(kinds) > 1:
        L += ["", "## By question kind (commit = commit subject; symptom = rewritten without identifiers)", "",
              "| repo | kind | arm | n | hit@3 | func_hit | tokens_in median | tokens_in mean | tool calls | skill used |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for repo in repos:
            for kind in kinds:
                for arm in arms:
                    g = [r for r in by.get((repo, arm), []) if r.get("kind", "commit") == kind]
                    if not g:
                        continue
                    fh = [r["func_hit"] for r in g if r["func_hit"] is not None]
                    L.append(f"| {repo} | {kind} | {arm} | {len(g)} | {100 * st.mean(r['hit3'] for r in g):.0f}% | "
                             f"{100 * st.mean(fh) if fh else 0:.0f}% | {st.median(r['tokens_in'] for r in g):.0f} | "
                             f"{st.mean(r['tokens_in'] for r in g):.0f} | {st.mean(r['tool_calls'] for r in g):.1f} | "
                             f"{100 * st.mean(r['skill_invoked'] for r in g):.0f}% |")
    metrics = ["hit@3", "func_hit"] + (["correct"] if judged else [])
    L += ["", "## Paired tests vs A (same question; exact sign / McNemar tests, two-sided)", "",
          ("With repetitions, each question counts once: its mean over the runs, and the arm wins it when that mean "
           "is higher. " if reps > 1 else "")
          + "Cells: questions the arm won / questions A won (p).", "",
          "| repo | arm | " + " | ".join(f"{m} arm-only / A-only (p)" for m in metrics)
          + " | tokens_in arm/A median | cheaper than A (p) | cost arm/A |",
          "|---|---|" + "---|" * (len(metrics) + 3)]
    perq = defaultdict(list)  # (repo, arm, case) -> its runs
    for r in rows:
        perq[(r["repo"], r["arm"], r["case"])].append(r)
    for repo in repos + ["all"]:
        qs = sorted((rp, c) for (rp, a_, c) in perq if a_ == "A" and (repo == "all" or rp == repo))
        for arm in [x for x in arms if x != "A"]:
            pq = [(perq[(rp, "A", c)], perq[(rp, arm, c)]) for rp, c in qs if (rp, arm, c) in perq]
            if not pq:
                continue
            cell = []
            for m in metrics:
                pr = [(qmean(a, m), qmean(b, m)) for a, b in pq]
                pr = [(x, y) for x, y in pr if x is not None and y is not None]
                x = sum(1 for a, b in pr if b > a); y = sum(1 for a, b in pr if a > b)
                cell.append(f"{x} / {y} ({sign_p(x, x + y):.2f})")
            ratio = [qmean(b, "tokens_in") / qmean(a, "tokens_in") for a, b in pq]
            ch = sum(v < 1 for v in ratio)
            cost = (sum(qmean(b, "cost_usd") or 0 for a, b in pq) / (sum(qmean(a, "cost_usd") or 0 for a, b in pq) or 1))
            L.append(f"| {repo} | {arm} | {' | '.join(cell)} | {st.median(ratio):.2f} | {ch}/{len(pq)} "
                     f"({sign_p(ch, len(pq)):.3f}) | {cost:.2f} |")
    if reps > 1:
        L += repetitions(rows, perq, repos, arms, metrics)
    if errors:
        L += ["", f"## Excluded runs: {len(errors)} (errors/timeouts)", ""]
        L += [f"- {r['repo']} {r['arm']} case{r['case']} rep{r['rep']}: {str(r.get('err'))[:120]}" for r in errors[:30]]
    trig = [r for r in load_jsonl(runs / "trigger_rows.jsonl") if not r.get("is_error")]
    if trig:
        L += ["", "## Triggering (skill installed, no hint): was it invoked?", "",
              "| repo | arm | should invoke: invoked | should not: invoked |", "|---|---|---|---|"]
        for repo in sorted({r["repo"] for r in trig}):
            for arm in sorted({r["arm"] for r in trig if r["repo"] == repo}):
                g = [r for r in trig if r["repo"] == repo and r["arm"] == arm]
                yes = [r for r in g if r.get("should")]; no = [r for r in g if r.get("should") is False]
                L.append(f"| {repo} | {arm} | {sum(r['skill_invoked'] for r in yes)}/{len(yes)} | "
                         f"{sum(r['skill_invoked'] for r in no)}/{len(no)} |")
    (HERE / a.out).write_text("\n".join(L) + "\n", "utf-8", newline="\n")
    print(f"wrote {HERE / a.out}")


if __name__ == "__main__":
    main()
