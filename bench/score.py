#!/usr/bin/env python3
"""Score bench/<runs-dir>/rows.jsonl -> bench/<out> (markdown).

Per run: hit@3 (a gold file among the first 3 files the answer names), recall@3, func_hit (a gold function
named), tokens_in (input + cache creation + cache read: everything the model processed), tool calls, source
bytes read. Aggregates per repo and arm; by question kind; paired exact sign / McNemar tests vs arm A on the
same question; triggering table. A hand-written interpretation is put on top if it exists:
report_v2.md -> report_notes_v2.md.

usage: score.py --runs-dir results/v2 --out report_v2.md
"""
import argparse, json, re, statistics as st
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
    return {"hit3": bool(found), "recall3": len(found) / len(gold), "func_hit": func, "files": files,
            "tokens_in": row["input_tokens"] + row["cache_creation"] + row["cache_read"]}


def sign_p(k, n):
    """Two-sided exact binomial (sign / exact McNemar) test, p = 0.5."""
    if n == 0:
        return 1.0
    k = min(k, n - k)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def ms(xs, fmt="{:.0f}"):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "n/a"
    sd = st.stdev(xs) if len(xs) > 1 else 0
    return f"{fmt.format(st.mean(xs))} ± {fmt.format(sd)}"


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
    by = defaultdict(list)
    for r in rows:
        r.update(score_row(r, cases[(r["repo"], r["case"])]))
        by[(r["repo"], r["arm"])].append(r)
    repos = sorted({r["repo"] for r in rows})
    arms = sorted({r["arm"] for r in rows})

    notes = HERE / (Path(a.out).stem.replace("report", "report_notes", 1) + ".md")
    L = ["# repo-atlas: LLM benchmark", ""] + ([notes.read_text("utf-8").rstrip(), ""] if notes.exists() else []) + [
         "## Results by arm", "",
         "Each cell: mean ± std over runs (questions × repetitions). tokens_in = input + cache creation + cache read "
         "(everything the model processed). hit@3 = a gold file among the first 3 files named; recall@3 = fraction of "
         "gold files among them; func_hit = a gold function named in the answer. src KB = bytes returned by Read on "
         "source files (not .atlas/.claude).", ""]
    hdr = "| repo | arm | n | hit@3 | recall@3 | func_hit | tokens_in | tokens_out | tool calls | src KB | skill used |"
    L += [hdr, "|" + "---|" * (hdr.count("|") - 1)]
    for repo in repos:
        for arm in arms:
            g = by.get((repo, arm), [])
            if not g:
                continue
            fh = [r["func_hit"] for r in g if r["func_hit"] is not None]
            L.append(f"| {repo} | {arm} | {len(g)} | {100 * st.mean(r['hit3'] for r in g):.0f}% | "
                     f"{100 * st.mean(r['recall3'] for r in g):.0f}% | {100 * st.mean(fh) if fh else 0:.0f}% | "
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
    L += ["", "## Paired tests vs A (same question; exact sign / McNemar tests, two-sided)", "",
          "| repo | arm | hit@3 arm-only / A-only (p) | func_hit arm-only / A-only (p) | tokens_in arm/A median | cheaper than A (p) | cost arm/A |",
          "|---|---|---|---|---|---|---|"]
    keyed = {(r["repo"], r["arm"], r["case"]): r for r in rows if r["rep"] == 1}
    for repo in repos + ["all"]:
        qs = [(rp, c) for (rp, a_, c) in keyed if a_ == "A" and (repo == "all" or rp == repo)]
        for arm in [x for x in arms if x != "A"]:
            pq = [(keyed[(rp, "A", c)], keyed[(rp, arm, c)]) for rp, c in qs if (rp, arm, c) in keyed]
            if not pq:
                continue
            cell = []
            for m in ("hit3", "func_hit"):
                pr = [(a[m], b[m]) for a, b in pq if a[m] is not None]
                x = sum(1 for a, b in pr if b and not a); y = sum(1 for a, b in pr if a and not b)
                cell.append(f"{x} / {y} ({sign_p(x, x + y):.2f})")
            ratio = [b["tokens_in"] / a["tokens_in"] for a, b in pq]
            ch = sum(v < 1 for v in ratio)
            cost = sum(b["cost_usd"] or 0 for a, b in pq) / (sum(a["cost_usd"] or 0 for a, b in pq) or 1)
            L.append(f"| {repo} | {arm} | {cell[0]} | {cell[1]} | {st.median(ratio):.2f} | {ch}/{len(pq)} ({sign_p(ch, len(pq)):.3f}) | {cost:.2f} |")
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
