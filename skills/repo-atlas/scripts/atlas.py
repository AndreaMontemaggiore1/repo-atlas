#!/usr/bin/env python3
"""repo-atlas: one entry point. Every command prints compact text and exits 0 (a failing command
would abort the skill invocation that injected it).

  find [query ...]    ranked symbols WITH their code, in one call (one query per argument; --stdin: per line).
                      No query: the map brief. Builds the map on first use.
  map                 rebuild .atlas/ (zero model tokens)
  note "path::Symbol | text" ...   add notes to .atlas/notes.md in one call (anchors validated)
  check [--fix-lines] [--sync]     validate notes against the code
  init [--claude-md]  .atlas/.gitignore; with --claude-md also a 2-line pointer in CLAUDE.md
  gate                optional PreToolUse hook: deny whole-file Reads of big code files (references/enforce.md)
  session-start       plugin SessionStart hook: the CLAUDE.md pointer as context, in repos that have a map

Options: --root DIR (default: git top level, else the current directory).
"""
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import skeleton as sk  # noqa: E402
import locate  # noqa: E402
import check_atlas  # noqa: E402

BUDGET_LINES = 120   # code lines printed by one find call, shared by its queries
CODE_CAPS = (50, 25, 12)  # per result rank; later results show only their best line
MAX_QUERIES = 4
MORE_FILES = 4       # next distinct files after the results, paths only
REBUILD_AFTER = 50   # changed code files since the map was built -> full rebuild
BACKGROUND_FILES = 30000  # code files: above this the map is built in the background (~1.6 ms/file measured)
BUILD_LOCK_TTL = 1800     # s: an older .atlas/building lock is taken for a dead build
GENERATED = ("_map.md", "_map.json", "symbols.json", "meta.json", "building")
BIG_REPO_FILES = 200  # code files: from here the plugin hook suggests the skill even before the first map
BIG_REPO_POINTER = ("This is a large repo. To find code by what it does, invoke the repo-atlas skill with your search "
                    "words as its argument: on first use it builds a local code map in seconds, then returns ranked "
                    "symbols with their code in one step. Use Grep only for exact identifiers.")
POINTER = ("<!-- repo-atlas -->\n"
           "This repo has an `.atlas/` code map. To find code by what it does, invoke the repo-atlas skill with "
           "your search words as its argument: it returns ranked symbols with their code in one step. "
           "Use Grep only for exact identifiers.\n"
           "<!-- /repo-atlas -->\n")


def repo_root(arg):
    if arg and arg.strip() and Path(arg.strip()).is_dir():
        return str(Path(arg.strip()).resolve())
    top = sk.run(["git", "rev-parse", "--show-toplevel"], os.getcwd()).strip()
    return str(Path(top).resolve()) if top else os.getcwd()


def ensure_map(root):
    """Build .atlas/ if missing or far behind HEAD; small drifts are handled per query by locate.
    Returns (message, ready). In a very large repo the build goes to the background: the skill's injected
    command has a 2-minute limit, and a failed invocation would cost the user a turn and an error."""
    atlas = Path(root, ".atlas")
    try:
        meta = json.loads((atlas / "meta.json").read_text("utf-8"))
        has_map = ok = (atlas / "_map.json").exists() and (atlas / "symbols.json").exists()
    except (OSError, ValueError):
        meta, has_map, ok = {}, False, False
    if ok:
        head = sk.run(["git", "rev-parse", "HEAD"], root).strip()
        changed = locate.changed_files(root, meta.get("skeleton_commit")) if head and head != meta.get("skeleton_commit") else set()
        ok = sum(1 for f in changed if sk.LANG.get(Path(f).suffix.lower()) in sk.CODE) <= REBUILD_AFTER
    if ok:
        return "", True
    n = sum(1 for f in sk.list_files(root) if sk.LANG[Path(f).suffix.lower()] in sk.CODE)
    if n > int(os.environ.get("ATLAS_BACKGROUND_FILES") or BACKGROUND_FILES):
        building = start_background_build(root)
        if has_map:  # far behind HEAD: keep answering from the old map meanwhile
            return "(large repo: the map is being refreshed in the background; changed files are still re-read)", True
        return (f"repo-atlas: this repo is large ({n} code files), so its map is being built in the background"
                f"{'' if building else ' (already started)'}, about {max(1, round(n * 0.002 / 60))} min. Until it is "
                "ready, use Grep and Read as usual; run the lookup again later."), False
    t0 = time.time()
    sk.build(root)
    if not (atlas / ".gitignore").exists():  # keep generated files out of `git status` from the first use
        write_gitignore(root)
    return f"(map built in {time.time() - t0:.1f}s)", True


def start_background_build(root):
    """Start `atlas map` as a detached process unless one is already running; True if started now."""
    lock = Path(root, ".atlas", "building")
    try:
        if time.time() - lock.stat().st_mtime < BUILD_LOCK_TTL:
            return False
    except OSError:
        pass
    lock.parent.mkdir(exist_ok=True)
    lock.write_text(str(os.getpid()), "utf-8")
    detach = ({"creationflags": 0x00000008 | 0x00000200} if os.name == "nt"  # DETACHED_PROCESS | NEW_PROCESS_GROUP
              else {"start_new_session": True})
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "map", "--root", root], cwd=root,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **detach)
    return True


def write_gitignore(root):
    atlas = Path(root, ".atlas"); atlas.mkdir(exist_ok=True)
    sk.write_text(atlas / ".gitignore", "# generated by repo-atlas (rebuilt for free); notes.md is worth committing\n"
                  + "\n".join(GENERATED) + "\n")


def load_map(root):
    try:
        return json.loads(Path(root, ".atlas", "_map.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def notes_count(root):
    try:
        text = Path(root, ".atlas", "notes.md").read_text("utf-8")
    except OSError:
        return 0
    return sum(1 for l in text.splitlines() if check_atlas.ANCHOR.search(l))


def brief(root):
    try:
        text = Path(root, ".atlas", "_map.md").read_text("utf-8")
    except OSError:
        return "no map"
    head = text.split(sk.BRIEF_END)[0].rstrip()
    n = notes_count(root)
    return (head + (f"\nnotes: {n} in .atlas/notes.md (find shows the relevant ones)" if n else "")
            + "\nmore: .atlas/_map.md (ranking, duplicates, unreferenced, noise, co-change)")


def numbered(lines, s, e):
    return [f"{i:>6}| {lines[i - 1][:160]}" for i in range(s, e + 1) if 0 < i <= len(lines)]


def window(s, e, best, cap):
    """The whole symbol if it fits in cap lines, else cap lines centred on the best matching line."""
    if e - s + 1 <= cap:
        return s, e
    a = max(s, min(best - cap // 2, e - cap + 1))
    return a, a + cap - 1


def find(root, queries, k=5):
    data = load_map(root)
    dupes = {}
    for g in data.get("dupes", []):
        for f, n, _, _ in g:
            dupes[(f, n)] = [f"{f2}::{n2}" for f2, n2, _, _ in g if (f2, n2) != (f, n)]
    clashes = data.get("clashes", {})
    noisy = {f for f, _, _ in data.get("noise", [])}
    files = [f for f in sk.list_files(root) if sk.LANG[Path(f).suffix.lower()] in sk.CODE]
    syms = locate.load_symbols(root, files)
    notes = locate.annotation_lines(root, syms)
    caps = [max(4, c // len(queries)) for c in CODE_CAPS]
    budget = BUDGET_LINES
    out = []
    for q in queries:
        terms, ranked = locate.locate(root, q, k + 30)
        ranked = sorted(ranked, key=lambda r: -r[0] * (0.3 if r[1] in noisy else 1.0))  # generated code last
        res = ranked[:k]
        shown_files = {r[1] for r in res}
        more = [f for f in dict.fromkeys(r[1] for r in ranked[k:]) if f not in shown_files][:MORE_FILES]
        out.append(f"## {q.strip()[:100]}" + (f"  (terms: {' '.join(terms)})" if terms else ""))
        if not res:
            out.append("no match: try other words or Grep for an identifier")
            continue
        for rank, (score, f, n, s, e, src, (ln, best)) in enumerate(res):
            label = f"{f}::{n}" if n else f
            extra = []
            if (f, n) in dupes:
                extra.append("same body: " + ", ".join(dupes[(f, n)][:3]))
            elif n and "." not in n and n in clashes:
                extra.append("name also in: " + ", ".join(x for x in clashes[n] if x != f)[:120])
            if f in noisy:
                extra.append("generated/noise file")
            out.append(f"{rank + 1}. {label} L{s}-{e} [{src}]" + (f"  ({'; '.join(extra)})" if extra else ""))
            for _, line in notes.get((f, n), [])[:2] + (notes.get((f, None), [])[:1] if n else []):
                out.append(f"   note: {line[:200]}")
            cap = min(caps[rank], budget) if rank < len(caps) else 0
            if cap >= 4:
                lines = (sk.read_src(root, f) or "").splitlines()
                a, b = window(s, e, ln, cap)
                code = numbered(lines, a, b)
                budget -= len(code)
                out += code + ([f"   … {label} continues to L{e}"] if b < e else [])
            else:
                out.append(f"   L{ln}: {best.strip()[:160]}")
        if more:  # the 5 results often come from 2-3 files; name the next candidates too
            out.append("other matching files: " + ", ".join(more))
    out.append("(read more of a symbol with Read offset/limit; several searches: find \"q1\" \"q2\")")
    return "\n".join(out)


def note(root, items):
    """Validate and append notes; returns a summary. Anchor = path[::Symbol]; text after '|'."""
    path = Path(root, ".atlas", "notes.md")
    path.parent.mkdir(exist_ok=True)
    try:
        text = path.read_text("utf-8")
    except OSError:
        text = "# notes (repo-atlas: one line per fact; `!` trap, `?` unverified, `x` dead, `→` flow)\n"
    existing = set(text.splitlines())
    added, problems = [], []
    for raw in items:
        raw = raw.strip()
        if not raw:
            continue
        prefix = raw[0] if raw[0] in "!?x→@" and len(raw) > 1 and raw[1] == " " else ""
        body = raw[2:] if prefix else raw
        m = check_atlas.ANCHOR.match(body)
        if not m or "|" not in body:
            problems.append(f"skipped (need 'path[::Symbol] | text'): {raw[:80]}")
            continue
        f, sym = m.group(1), m.group(2)
        msg = body.split("|", 1)[1].strip()
        if not Path(root, f).is_file():
            problems.append(f"skipped, no such file: {f}")
            continue
        anchor = f
        if sym:
            table = {n: (s, e) for n, s, e in sk.symbols(root, [f])[f]}
            name = check_atlas.resolve_name(table, sym)
            if not name:
                near = [n for n in table if sym.lower() in n.lower()][:3]
                problems.append(f"skipped, {f}::{sym} not found" + (f" (did you mean {', '.join(near)}?)" if near else ""))
                continue
            anchor = f"{f}::{name} ~L{table[name][0]}-{table[name][1]}"
        line = f"{prefix + ' ' if prefix else ''}{anchor} | {msg}"
        if line in existing:
            problems.append(f"already there: {anchor}")
            continue
        existing.add(line)
        added.append(line)
    if added:
        sk.write_text(path, text.rstrip("\n") + "\n" + "\n".join(added) + "\n")
        meta_p = Path(root, ".atlas", "meta.json")
        try:
            meta = json.loads(meta_p.read_text("utf-8"))
        except (OSError, ValueError):
            meta = {}
        meta["synced_commit"] = sk.run(["git", "rev-parse", "HEAD"], root).strip() or None
        sk.write_text(meta_p, json.dumps(meta, indent=1))
    n = len(path.read_text("utf-8").splitlines()) if path.exists() else 0
    over = f"\nnotes.md has {n} lines (budget 200): merge or drop stale lines" if n > 200 else ""
    return f"added {len(added)} note(s) to .atlas/notes.md" + "".join("\n" + p for p in problems) + over


def init(root, claude_md):
    write_gitignore(root)
    msg = ["wrote .atlas/.gitignore"]
    if claude_md:
        p = Path(root, "CLAUDE.md")
        old = p.read_text("utf-8") if p.exists() else ""
        if "<!-- repo-atlas -->" in old:
            msg.append("CLAUDE.md already has the repo-atlas pointer")
        else:
            sk.write_text(p, old.rstrip("\n") + ("\n\n" if old.strip() else "") + POINTER)
            msg.append("added a 2-line repo-atlas pointer to CLAUDE.md")
    return "\n".join(msg)


def session_start(root):
    """The pointer for the session context, unless CLAUDE.md already has it: in repos with a map, or with at least
    BIG_REPO_FILES git-tracked code files (the first lookup then builds the map). Else "".
    A SessionStart hook's stdout goes straight into the context, so errors print nothing too."""
    try:
        md = Path(root, "CLAUDE.md")
        if md.exists() and POINTER.splitlines()[0] in md.read_text("utf-8", "replace"):
            return ""
        if Path(root, ".atlas", "_map.json").exists():
            return POINTER.splitlines()[1]
        if code_files_at_least(root, BIG_REPO_FILES):
            return BIG_REPO_POINTER
    except OSError:
        pass
    return ""


def code_files_at_least(root, n):
    """True if git tracks >= n code files here. No git, no suggestion: a session opened in a plain folder
    (a home directory, say) must not be pushed to map everything below it."""
    tracked = sk.run(["git", "ls-files"], root).splitlines()
    return sum(1 for f in tracked if sk.LANG.get(os.path.splitext(f)[1].lower()) in sk.CODE) >= n


def main(argv=None):
    ap = argparse.ArgumentParser(prog="atlas", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["find", "map", "note", "check", "init", "gate", "session-start"])
    ap.add_argument("items", nargs="*")
    ap.add_argument("--root", default="")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--fix-lines", action="store_true")
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--claude-md", action="store_true")
    ap.add_argument("--stdin", action="store_true", help="also read items from stdin, one per line (the skill's injected heredoc)")
    a = ap.parse_args(argv)
    if a.cmd == "gate":  # PreToolUse hook (references/enforce.md): JSON in on stdin, JSON decision out
        import gate
        return gate.main()
    root = repo_root(a.root)
    if a.cmd == "session-start":
        line = session_start(root)
        if line:
            print(line)
        return 0
    items = list(a.items)
    if a.stdin:  # never read stdin implicitly: an open pipe would block until the Bash timeout
        items += [l for l in sys.stdin.read().splitlines() if l.strip() and l.strip() != "$ARGUMENTS"]
    if a.cmd == "find":
        built, ready = ensure_map(root)
        queries = [q for q in items if q.strip()][:MAX_QUERIES]
        print(built if not ready else (built + "\n" if built else "") + (find(root, queries, a.k) if queries else brief(root)))
    elif a.cmd == "map":
        t0 = time.time()
        try:
            sk.build(root)
            if not Path(root, ".atlas", ".gitignore").exists():
                write_gitignore(root)
        finally:
            Path(root, ".atlas", "building").unlink(missing_ok=True)  # a background build is done (or dead)
        print(f"map rebuilt in {time.time() - t0:.1f}s\n" + brief(root))
    elif a.cmd == "note":
        print(note(root, items))
    elif a.cmd == "check":
        check_atlas.main([root] + (["--fix-lines"] if a.fix_lines else []) + (["--sync"] if a.sync else []))
    elif a.cmd == "init":
        print(init(root, a.claude_md))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # code snippets are arbitrary Unicode
    except (AttributeError, ValueError):
        pass
    try:
        main()
    except SystemExit as e:  # argparse errors / --help: still exit 0
        sys.exit(0 if e.code in (None, 0, 2) else 0)
    except Exception as e:  # never fail: a non-zero exit aborts the skill invocation
        print(f"repo-atlas: error: {type(e).__name__}: {e}. Fall back to Grep/Read.")
    sys.exit(0)
