#!/usr/bin/env python3
"""Real LLM benchmark: one fresh copy of the repo + one fresh headless `claude -p` session per run.

Arms:  A  no skill (baseline)
       S  skill installed in the copy, prebuilt map, no hint anywhere (what a new user gets)
       P  S + the 2-line CLAUDE.md pointer written by `atlas init --claude-md`
       H  the plugin as shipped (--plugin-dir: skill + SessionStart hook that adds the pointer), prebuilt map
       H0 the plugin on a repo it has never seen: no map, and a one-commit git snapshot (no history) so the hook
          can count the files; the first lookup builds the map
Copies have no .git (the answer would be in `git log`) and none of the repo's own CLAUDE.md/AGENTS.md/.claude.
Raw stream-json logs go to bench/<runs-dir>/<repo>/<arm>/<case>_<rep>.jsonl, one summary row per run to
bench/<runs-dir>/rows.jsonl. Finished runs are skipped, so an interrupted batch resumes where it stopped.

usage: run_llm.py --repos gpodder --arms A S --cases 101 102 --max-usd 5 [--model sonnet] [--dry-run]
       run_llm.py --trigger --repos gpodder --arms S --max-usd 2     # was the skill invoked?
Repos are clones under bench/repos/<name> (see bench/README.md).
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "skills" / "repo-atlas"
SCRIPTS = SKILL / "scripts"
CLAUDE = os.environ.get("CLAUDE_BIN") or os.environ.get("CLAUDE_CODE_EXECPATH") or shutil.which("claude")
RUNS = HERE / "runs"
# copies live OUTSIDE this project: no parent .git, and bench/evals (the answers) is not reachable
WORK = Path(os.environ.get("ATLAS_BENCH_WORK") or Path(tempfile.gettempdir()) / "atlas-bench")
BASE = WORK / "base"
ARMS = ("A", "S", "P", "H", "H0")
PLUGIN_ARMS = ("H", "H0")
PLUGIN = HERE.parent  # this repository is the plugin (.claude-plugin/, skills/, hooks/)
TOOLS = "Read,Grep,Glob,Bash,Skill"
# Read/Grep/Glob need no rule inside the working dir; a bare "Read" rule would allow reads anywhere
ALLOWED = ["Skill", "Bash(python *)", "Bash(python3 *)", "Bash(grep *)", "Bash(rg *)",
           "Bash(ls *)", "Bash(cat *)", "Bash(head *)", "Bash(tail *)", "Bash(sed *)", "Bash(find *)", "Bash(wc *)"]
REPO_CLAUDE_FILES = ["CLAUDE.md", "AGENTS.md", ".claude"]  # the repo's own agent context is removed


def sh(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


_checked = set()


def base_copy(repo):
    """WORK/base/<repo>: a local clone (git needed for churn and co-change). Zero model tokens."""
    dst = BASE / repo
    if dst.exists() and repo not in _checked:  # %TEMP% cleaners (Windows Storage Sense) delete old files, keep dirs
        _checked.add(repo)
        tracked = sh(["git", "ls-files", "-z"], HERE / "repos" / repo).stdout.split("\0")  # -z: non-ASCII names unquoted
        missing = [f for f in tracked if f and not (dst / f).exists()]
        if missing:
            print(f"base copy of {repo} lost {len(missing)} files (e.g. {missing[0]}); re-cloning", flush=True)
            shutil.rmtree(dst, onerror=lambda fn, p, e: (os.chmod(p, 0o700), fn(p)))
    if not dst.exists():
        sh(["git", "-c", "core.autocrlf=false", "clone", "-q", "--config", "core.autocrlf=false",
            str(HERE / "repos" / repo), str(dst)])
    return dst


def prebuilt_map(repo):
    """The map, built once per repo on the base clone and reused by every S/P run."""
    out = HERE / "work" / "_atlas" / repo
    if not out.exists():
        base = base_copy(repo)
        sys.path.insert(0, str(SCRIPTS))
        import skeleton
        skeleton.build(str(base))
        shutil.copytree(base / ".atlas", out)
    return out


def make_copy(repo, arm, dst):
    base = base_copy(repo)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(base, dst, ignore=shutil.ignore_patterns(".git", ".atlas"))
    for name in REPO_CLAUDE_FILES:
        p = dst / name
        shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)
    if arm == "A":
        return
    if arm == "H0":  # one commit, no history: the commit subjects (the answers) stay out of reach
        for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "snapshot"]):
            sh(["git", "-c", "core.autocrlf=false", "-c", "user.name=bench", "-c", "user.email=bench@localhost", *cmd], dst)
        return
    shutil.copytree(prebuilt_map(repo), dst / ".atlas")
    if arm == "H":  # the skill and the hook come from --plugin-dir
        return
    shutil.copytree(SKILL, dst / ".claude" / "skills" / "repo-atlas", ignore=shutil.ignore_patterns("__pycache__"))
    if arm == "P":
        sys.path.insert(0, str(SCRIPTS))
        import atlas
        atlas.init(str(dst), claude_md=True)


def claude_cmd(prompt, model, plugin=False):
    return [CLAUDE, "-p", prompt, "--model", model, "--output-format", "stream-json", "--verbose",
            "--no-session-persistence", "--setting-sources", "project,local", "--tools", TOOLS,
            "--permission-mode", "dontAsk", *(["--plugin-dir", str(PLUGIN)] if plugin else []),
            "--allowedTools", *ALLOWED]  # variadic: must stay last


def run_session(cmd, cwd, log, timeout):
    log.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as fh:
        try:
            p = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.PIPE,
                               timeout=timeout, text=True, encoding="utf-8", errors="replace")
            err = p.stderr[-2000:]
        except subprocess.TimeoutExpired:
            err = "TIMEOUT"
    return time.time() - t0, err


def parse_log(log):
    """Summary of one stream-json session: usage, tool calls, bytes read, skill use, answer."""
    events = []
    for line in Path(log).read_text("utf-8", "replace").splitlines():
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    res = next((e for e in reversed(events) if e.get("type") == "result"), {})
    calls, uses = {}, []
    src_bytes = tool_bytes = 0
    for e in events:
        msg = e.get("message")
        if not isinstance(msg, dict):  # e.g. system/permission_denied carries a string
            continue
        if e.get("parent_tool_use_id"):
            continue  # subagent traffic (Task is not enabled, kept for safety)
        content = msg.get("content")
        for b in content if isinstance(content, list) else []:
            if b.get("type") == "tool_use":
                calls[b["id"]] = b
                uses.append(b["name"])
            elif b.get("type") == "tool_result":
                c = b.get("content")
                text = c if isinstance(c, str) else "".join(x.get("text", "") for x in c or [] if isinstance(x, dict))
                n = len(text.encode("utf-8"))
                tool_bytes += n
                use = calls.get(b.get("tool_use_id"), {})
                path = str((use.get("input") or {}).get("file_path", "")).replace("\\", "/")
                if use.get("name") == "Read" and not re.search(r"/\.atlas/|/\.claude/", path):
                    src_bytes += n
    u = res.get("usage") or {}
    skills_used = [calls[k]["input"].get("skill") for k in calls if calls[k]["name"] == "Skill"]
    return {
        "skills_visible": any(s.split(":")[-1] == "repo-atlas" for s in init.get("skills") or []),  # plugin: repo-atlas:repo-atlas
        "model": init.get("model"),
        "cli": init.get("claude_code_version"),
        "input_tokens": u.get("input_tokens", 0), "cache_creation": u.get("cache_creation_input_tokens", 0),
        "cache_read": u.get("cache_read_input_tokens", 0), "output_tokens": u.get("output_tokens", 0),
        "cost_usd": res.get("total_cost_usd"), "num_turns": res.get("num_turns"),
        "tool_calls": len(uses), "tool_counts": {n: uses.count(n) for n in set(uses)},
        "src_bytes_read": src_bytes, "tool_output_bytes": tool_bytes,
        "skill_invoked": any(s and s.split(":")[-1] == "repo-atlas" for s in skills_used),
        "permission_denied": sum(e.get("subtype") == "permission_denied" for e in events),
        "hook_context": any(e.get("subtype") == "hook_response" and "repo-atlas" in json.dumps(e) for e in events),
        "is_error": res.get("is_error"), "answer": res.get("result", ""),
        **plan_usage(events),
    }


def plan_usage(events):
    """Last subscription rate-limit info seen in the stream (Pro/Max plans)."""
    rl = [e["rate_limit_info"] for e in events if e.get("type") == "rate_limit_event" and e.get("rate_limit_info")]
    last = rl[-1] if rl else {}
    win = last.get("unifiedWindows") or {}
    return {"rl_status": last.get("status"), "rl_resets_at": last.get("resetsAt"),
            "util_5h": (win.get("five_hour") or {}).get("utilization"),
            "reset_5h": (win.get("five_hour") or {}).get("resetsAt"),
            "util_7d": (win.get("seven_day") or {}).get("utilization")}


def is_limited(row):
    """The session was refused by the plan's usage limit (not a model/tool error)."""
    if not row.get("is_error"):
        return False
    return row.get("rl_status") not in (None, "allowed", "allowed_warning") or bool(
        re.search(r"usage limit|rate limit|limit reached|resets? at", row.get("answer") or "", re.I))


def wait_for_reset(row):
    until = (row.get("rl_resets_at") or time.time() + 1800) + 120
    print(f"plan limit reached ({row.get('rl_status')}); sleeping until {time.strftime('%H:%M', time.localtime(until))}",
          flush=True)
    time.sleep(max(60, until - time.time()))


def load_rows(path):
    return [json.loads(l) for l in path.read_text("utf-8").splitlines() if l.strip()] if path.exists() else []


def done_keys(path):
    return {(r["repo"], r["arm"], r["case"], r["rep"]) for r in load_rows(path)
            if not r.get("is_error") and r.get("err") != "TIMEOUT"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", nargs="+", required=True)
    ap.add_argument("--arms", nargs="+", default=list(ARMS), choices=ARMS)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--cases", nargs="*", type=int, help="case ids (default: all)")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--max-usd", type=float, required=True, help="stop when the cumulative cost in rows exceeds it")
    ap.add_argument("--max-week", type=float, default=None,
                    help="stop when the plan's 7-day utilization (0-1, from the stream) reaches it")
    ap.add_argument("--max-5h", type=float, default=None,
                    help="pause until the 5-hour window resets when its utilization reaches it (leaves room for interactive use)")
    ap.add_argument("--trigger", action="store_true", help="triggering eval (bench/trigger_prompts.json): skill invoked?")
    ap.add_argument("--dry-run", action="store_true", help="prepare one copy per arm and print the command")
    ap.add_argument("--runs-dir", default="runs", help="under bench/: a separate dir per benchmark round")
    a = ap.parse_args()
    global RUNS
    RUNS = HERE / a.runs_dir
    if not CLAUDE:
        raise SystemExit("claude binary not found (set CLAUDE_BIN)")
    rows_path = RUNS / ("trigger_rows.jsonl" if a.trigger else "rows.jsonl")
    triggers = json.loads((HERE / "trigger_prompts.json").read_text("utf-8")) if a.trigger else None
    done = done_keys(rows_path)
    for repo in a.repos:
        if a.trigger:
            cases = [{"id": i, "prompt": p["prompt"], "should": p["should"]} for i, p in enumerate(triggers[repo], 1)]
        else:
            cases = json.loads((HERE / "evals" / f"{repo}.json").read_text("utf-8"))["cases"]
        cases = [c for c in cases if not a.cases or c["id"] in a.cases]
        for rep in range(1, a.reps + 1):
            for c in cases:
                for arm in a.arms:  # arms interleaved per question: same CLI version, same time of day
                    if (repo, arm, c["id"], rep) in done:
                        continue
                    rows = load_rows(rows_path)
                    total = sum(r.get("cost_usd") or 0 for r in rows)
                    week = next((r["util_7d"] for r in reversed(rows) if r.get("util_7d") is not None), None)
                    if not a.dry_run and total > a.max_usd:
                        raise SystemExit(f"budget: spent ${total:.2f} > --max-usd {a.max_usd}; stopping")
                    if not a.dry_run and a.max_week is not None and week is not None and week >= a.max_week:
                        raise SystemExit(f"plan: 7-day utilization {week:.2f} >= --max-week {a.max_week}; stopping")
                    last = rows[-1] if rows else {}
                    if (not a.dry_run and a.max_5h is not None and (last.get("util_5h") or 0) >= a.max_5h
                            and (last.get("reset_5h") or 0) > time.time()):
                        wait_for_reset({"rl_status": f"5h utilization {last['util_5h']} >= --max-5h",
                                        "rl_resets_at": last["reset_5h"]})
                    run_dir = WORK / "runs" / f"{repo}_{arm}_{c['id']}_{rep}"
                    make_copy(repo, arm, run_dir)
                    cmd = claude_cmd(c["prompt"], a.model, plugin=arm in PLUGIN_ARMS)
                    if a.dry_run:
                        print(arm, run_dir, " ".join(cmd[:3]), "...")
                        continue
                    log = RUNS / repo / (f"T{arm}" if a.trigger else arm) / f"{c['id']}_{rep}.jsonl"
                    while True:
                        secs, err = run_session(cmd, run_dir, log, a.timeout)
                        row = dict(repo=repo, arm=arm, case=c["id"], rep=rep, kind=c.get("kind", "commit"),
                                   should=c.get("should"), secs=round(secs), err=err[-300:], **parse_log(log))
                        if not is_limited(row):
                            break
                        wait_for_reset(row)
                    if row["skills_visible"] != (arm != "A"):
                        row["is_error"] = True
                        row["err"] = f"skill visibility wrong for arm {arm}: {row['skills_visible']}"
                    with open(rows_path, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row) + "\n")
                    shutil.rmtree(run_dir, ignore_errors=True)
                    tot = row["input_tokens"] + row["cache_creation"] + row["cache_read"]
                    print(f"{repo} {arm} case{c['id']} rep{rep}: in={tot} out={row['output_tokens']} "
                          f"tools={row['tool_calls']} skill={row['skill_invoked']} ${row['cost_usd']} "
                          f"7d={row['util_7d']} {secs:.0f}s {row['err'][:80] if row['is_error'] else ''}", flush=True)


if __name__ == "__main__":
    main()
