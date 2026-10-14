#!/usr/bin/env python3
"""Add 'symptom' questions to bench/evals/<repo>.json: commit subjects rewritten by an LLM as a
product owner would ask (behaviour, symptom, feature), with no code identifiers. Gold = the commit's.

One headless session per repo, no tools, in an empty directory: the model sees only the subjects,
never the code. Questions that still contain identifiers, gold names or file stems are dropped.
Cases get id 100 + original id and kind "symptom".

usage: make_symptom_questions.py gpodder formbricks [-n 20] [--model sonnet]
"""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_llm  # noqa: E402  (claude binary, plan-limit handling)

HERE = Path(__file__).resolve().parent
TEMPLATE = "In this repo, where is the code I would change for this request: {q} Answer with file paths and function names only."
INSTRUCTIONS = """You rewrite software change requests as questions a non-technical product owner would ask a developer.
For each numbered commit subject below, write ONE question that describes the user-visible behaviour, symptom
or feature in plain words, as if you had never seen the code. Rules: no function, class, variable, file,
package or library names; no camelCase or snake_case words; no code syntax; everyday product words only;
keep the meaning; 8 to 25 words. If a subject has no user-visible meaning (refactor, lint, typing, CI,
dependencies, formatting), answer exactly SKIP for it.

"""
SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
    "id": {"type": "integer"}, "question": {"type": "string"}}, "required": ["id", "question"]}}}, "required": ["items"]}


def leaks(q, case):
    """True if the question still names code: identifiers, gold function names or file stems."""
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", q)
    if any("_" in w or re.search(r"[a-z][A-Z]", w) or re.search(r"\w\.\w", w) for w in words):
        return True
    names = {f.split(".")[-1].lower() for f in case["gold_functions"]} | {Path(f).stem.lower() for f in case["gold_files"]}
    low = {w.lower() for w in words}
    return bool({n for n in names if len(n) >= 4} & low)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="+")
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--model", default="sonnet")
    a = ap.parse_args()
    for repo in a.repos:
        path = HERE / "evals" / f"{repo}.json"
        data = json.loads(path.read_text("utf-8"))
        commit_cases = [c for c in data["cases"] if c.get("kind", "commit") == "commit"]
        if any(c.get("kind") == "symptom" for c in data["cases"]):
            print(f"{repo}: symptom questions already present, skipping")
            continue
        subjects = "\n".join(f"{c['id']}. {c['prompt'].split('change to: ', 1)[1].rsplit('?', 1)[0]}" for c in commit_cases)
        with tempfile.TemporaryDirectory() as empty:
            cmd = [run_llm.CLAUDE, "-p", INSTRUCTIONS + subjects, "--model", a.model, "--output-format", "json",
                   "--no-session-persistence", "--setting-sources", "project,local", "--tools", "",
                   "--json-schema", json.dumps(SCHEMA)]
            out = subprocess.run(cmd, cwd=empty, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=600).stdout
        res = json.loads(out)
        payload = res.get("structured_output") or res.get("result")
        items = (payload if isinstance(payload, dict) else json.loads(payload))["items"]
        by_id = {c["id"]: c for c in commit_cases}
        added, dropped = [], []
        for it in items:
            c, q = by_id.get(it["id"]), it["question"].strip()
            if not c or q.upper().startswith("SKIP"):
                continue
            if leaks(q, c):
                dropped.append(q)
                continue
            added.append({**{k: c[k] for k in ("commit", "gold_files", "gold_functions")}, "id": 100 + c["id"],
                          "kind": "symptom", "question": q, "prompt": TEMPLATE.format(q=q.rstrip("?") + "?")})
        data["cases"] += added[:a.n]
        data.setdefault("symptom_generation", {}).update(
            {"model": a.model, "cost_usd": res.get("total_cost_usd"), "kept": len(added[:a.n]), "dropped_leaky": dropped})
        path.write_text(json.dumps(data, indent=1), "utf-8")
        print(f"{repo}: +{len(added[:a.n])} symptom questions, {len(dropped)} dropped (leaky), ${res.get('total_cost_usd')}")


if __name__ == "__main__":
    main()
