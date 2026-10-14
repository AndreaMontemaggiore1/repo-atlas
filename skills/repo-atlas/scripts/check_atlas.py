#!/usr/bin/env python3
"""Validate .atlas/ annotations against the code.

Reports: broken anchors (file/symbol gone), line-hint drift, entries on files
changed since last sync, top-ranked files with no annotation, budget overruns.

usage: check_atlas.py <repo> [--fix-lines] [--sync]
  --fix-lines  rewrite ~L hints to the symbol's current range (no model tokens)
  --sync       record HEAD as the commit the annotations reflect
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import skeleton as sk  # reuse symbol extraction

ANCHOR = re.compile(r"(?<![\w/])([\w.\-/]+\.[A-Za-z]{1,6})(?:::([\w.#]+))?(?:\s+~L(\d+)-(\d+))?")
BUDGET = {"INDEX.md": 60, "notes.md": 200}
AREA_BUDGET = 120


def git(args, root):
    return subprocess.run(["git"] + args, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def symbols_of(root, f, cache):
    if f not in cache:
        cache[f] = {n: (s, e) for n, s, e in sk.symbols(root, [f])[f]}
    return cache[f]


def resolve_name(names, sym):
    """Exact name, else a unique `Type.sym` suffix match (anchors may omit the type)."""
    if sym in names:
        return sym
    cands = [n for n in names if n.endswith("." + sym)]
    return cands[0] if len(cands) == 1 else None


def resolve(table, sym):
    n = resolve_name(table, sym)
    return table[n] if n else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--fix-lines", action="store_true")
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--drift", type=int, default=15)
    a = ap.parse_args(argv)
    root = Path(a.repo).resolve()
    atlas = root / ".atlas"
    if not atlas.exists():
        print("no .atlas/ yet: run `atlas map` (or `atlas find`, which builds it)"); return 1
    meta_p = atlas / "meta.json"
    meta = json.loads(meta_p.read_text("utf-8")) if meta_p.exists() else {}
    synced = meta.get("synced_commit")
    changed = set()
    if synced:
        changed = set(git(["diff", "--name-only", synced, "HEAD"], root).split())
    changed |= set(git(["diff", "--name-only"], root).split())

    cache, broken, drift, stale, annotated, over = {}, [], [], [], set(), []
    total_anchors = 0
    for md in sorted(atlas.glob("*.md")):
        if md.name.startswith("_"):
            continue
        text = md.read_text("utf-8")
        n = text.count("\n")
        lim = BUDGET.get(md.name, AREA_BUDGET)
        if n > lim:
            over.append(f"{md.name}: {n} lines > {lim}")
        new_lines = []
        for ln_no, line in enumerate(text.splitlines(), 1):
            def repl(m):
                nonlocal total_anchors
                f, sym, s, e = m.groups()
                if not (root / f).is_file():
                    if "/" in f:
                        total_anchors += 1
                        broken.append(f"{md.name}:{ln_no} file missing: {f}")
                    return m.group(0)
                total_anchors += 1
                annotated.add(f)
                if f in changed:
                    stale.append(f"{md.name}:{ln_no} {f}{'::' + sym if sym else ''}")
                if not sym:
                    return m.group(0)
                rng = resolve(symbols_of(root, f, cache), sym)
                if rng is None:
                    broken.append(f"{md.name}:{ln_no} symbol not found: {f}::{sym}")
                    return m.group(0)
                rs, re_ = rng
                if s and (abs(int(s) - rs) > a.drift or abs(int(e) - re_) > a.drift):
                    drift.append(f"{md.name}:{ln_no} {f}::{sym} ~L{s}-{e} -> {rs}-{re_}")
                if a.fix_lines and s:
                    return f"{f}::{sym} ~L{rs}-{re_}"
                return m.group(0)
            new_lines.append(ANCHOR.sub(repl, line))
        if a.fix_lines:
            sk.write_text(md, "\n".join(new_lines) + ("\n" if text.endswith("\n") else ""))

    uncovered = []
    skel = atlas / "_map.md"
    if skel.exists():
        sec = skel.read_text("utf-8").split("## ranking", 1)[-1].split("\n## ", 1)[0]
        for line in sec.splitlines()[1:11]:
            parts = line.split()
            if len(parts) > 1 and parts[1] not in annotated:
                uncovered.append(parts[1])

    def show(title, items):
        if items:
            print(f"\n{title} ({len(items)})")
            for i in items[:40]:
                print("  " + i)
    print(f"anchors={total_anchors} broken={len(broken)} drift={len(drift)} "
          f"stale={len(stale)} synced={synced[:10] if synced else 'never'}")
    show("BROKEN (fix or remove)", broken)
    show("DRIFT" + (" (fixed)" if a.fix_lines else " (run --fix-lines)"), drift)
    show("STALE: file changed since sync, re-verify before trusting", stale)
    show("HIGH-RANK FILES WITHOUT ANNOTATION", uncovered)
    show("OVER BUDGET", over)
    if total_anchors:
        print(f"\nanchor health: {100 * (total_anchors - len(broken)) / total_anchors:.0f}%")
    if a.sync:
        meta["synced_commit"] = git(["rev-parse", "HEAD"], root).strip() or None
        sk.write_text(meta_p, json.dumps(meta, indent=1))
        print("synced ->", meta["synced_commit"])
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
