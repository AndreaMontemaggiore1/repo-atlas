#!/usr/bin/env python3
"""Build a localization benchmark from a repo's own git history (validation only).

Each case: question = commit subject (what changed), gold = source files and
functions the commit touched. Ground truth is free and repo-specific, like
SWE-bench localization. Only keeps commits touching 1-3 existing non-test files.

usage: make_localization_evals.py bench/repos/<name> [-n 40]   # writes bench/evals/<name>.json
Scored by score.py: hit@3 / recall@3 on gold files, func_hit on gold functions.
"""
import argparse, json, re, subprocess, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "repo-atlas" / "scripts"))
import skeleton as sk  # noqa: E402  (same symbol extraction as the map)

TEST = re.compile(r"(^|/)(tests?|spec|docs?|examples?|\.github)(/|$)|(_test|\.test|\.spec)\.|\.(md|rst|txt|lock|json|ya?ml|toml|cfg)$")
SKIP_MSG = re.compile(r"(?i)^(merge|bump|release|version|update (deps|dependencies)|typo|format|lint|pre-commit|revert)")


def git(args, root):
    return subprocess.run(["git"] + args, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def changed_symbols(root, sha, files):
    """Smallest symbols enclosing the lines a commit changed (new side), most-changed first."""
    hits = Counter()
    for f in files:
        src = git(["show", f"{sha}:{f}"], root)
        syms = sk.symbols(root, [f], {f: src})[f]
        diff = git(["show", "--format=", "-U0", sha, "--", f], root)
        for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff, re.M):
            start, n = int(m.group(1)), int(m.group(2) or 1)
            for ln in range(start, start + max(n, 1)):  # n == 0: pure deletion, use the deletion point
                enc = [(e - s, name) for name, s, e in syms if s <= ln <= e]
                if enc:
                    hits[min(enc)[1]] += 1
    return [n for n, _ in hits.most_common()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("-n", type=int, default=30)
    ap.add_argument("--out", help="default: bench/evals/<repo dir name>.json (never inside the benchmarked repo)")
    a = ap.parse_args()
    root = Path(a.repo).resolve()
    cases = []
    log = git(["log", "--no-merges", "--format=%H\t%s", "-n", "2000"], root)
    for line in log.splitlines():
        sha, _, msg = line.partition("\t")
        if SKIP_MSG.search(msg) or len(msg.split()) < 4:
            continue
        files = [f for f in git(["show", "--format=", "--name-only", sha], root).split()
                 if not TEST.search(f) and (root / f).is_file()]
        if not 1 <= len(files) <= 3:
            continue
        funcs = changed_symbols(root, sha, files)
        if not funcs:  # fallback: hunk-header heuristic (the function *before* the hunk, often wrong)
            diff = git(["show", "--format=", "-U0", sha, "--"] + files, root)
            heads = sorted({m.group(1).strip() for m in re.finditer(r"^@@[^@]+@@\s*(.+)$", diff, re.M)})
            heads = [re.sub(r"^(async\s+)?(def|func|function|class|fn)\s+", "", f).split("(")[0].strip().rstrip(":{ ")
                     for f in heads]
            funcs = [f for f in heads if f and not re.search(r"\bimport\b|=|\s", f)]
        cases.append({"id": len(cases) + 1, "commit": sha[:10],
                      "prompt": f"In this repo, where is the code I would change to: {msg}? "
                                f"Answer with file paths and function names only.",
                      "gold_files": files, "gold_functions": funcs[:6]})
        if len(cases) >= a.n:
            break
    out = Path(a.out) if a.out else Path(__file__).resolve().parent / "evals" / f"{root.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {"repo": re.sub(r"\.git$", "", git(["remote", "get-url", "origin"], root).strip()),
            "commit": git(["rev-parse", "HEAD"], root).strip()}
    out.write_text(json.dumps({**meta, "cases": cases}, indent=1) + "\n", "utf-8")
    print(f"{len(cases)} cases -> {out}")


if __name__ == "__main__":
    main()
