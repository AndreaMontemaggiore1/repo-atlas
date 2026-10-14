#!/usr/bin/env python3
"""PreToolUse hook: deny whole-file Reads of large source files, answer with their symbol ranges.

A Read without offset/limit of a code file over --max-lines lines is denied; the reason lists
the file's symbols with line ranges (from .atlas/symbols.json, else parsed), so the model can
re-issue a ranged Read in the same turn budget. Everything else passes untouched.

Install in .claude/settings.json of the project:
  {"hooks": {"PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command",
     "command": "python .claude/skills/repo-atlas/scripts/gate.py"}]}]}}
"""
import json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import skeleton as sk  # noqa: E402

MAX_LINES = int(os.environ.get("ATLAS_GATE_MAX_LINES", "300"))
MAX_LISTED = 60


def decide(event, root):
    """None to allow, else the deny reason."""
    if event.get("tool_name") != "Read":
        return None
    inp = event.get("tool_input") or {}
    if inp.get("offset") or inp.get("limit"):
        return None
    path = Path(inp.get("file_path", ""))
    if sk.LANG.get(path.suffix.lower()) not in sk.CODE:
        return None
    try:
        rel = path.resolve().relative_to(Path(root).resolve()).as_posix()
        n = len(path.read_bytes().splitlines())
    except (OSError, ValueError):
        return None  # outside the project or unreadable: not ours to judge
    if n <= MAX_LINES:
        return None
    try:
        syms = json.loads(Path(root, ".atlas", "symbols.json").read_text("utf-8")).get(rel)
    except (OSError, ValueError):
        syms = None
    if syms is None:
        syms = sk.symbols(root, [rel])[rel]
    listed = ", ".join(f"{name} {s}-{e}" for name, s, e in syms[:MAX_LISTED])
    more = f" …+{len(syms) - MAX_LISTED}" if len(syms) > MAX_LISTED else ""
    return (f"{rel} has {n} lines: read only the symbol you need with offset/limit "
            f"(offset = start line, limit = end - start + 1). Symbols: {listed}{more}"
            if syms else f"{rel} has {n} lines: Grep for what you need, then Read with offset/limit around the hit.")


def main():
    event = json.load(sys.stdin)
    root = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or "."
    reason = decide(event, root)
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "permissionDecision": "deny",
                                                 "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
