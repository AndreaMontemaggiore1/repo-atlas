---
name: repo-atlas
description: Finds code in large, unfamiliar or messy (vibe-coded) repositories in one step - returns the functions and classes that match a description, with their code, line ranges, duplicated copies and notes, instead of many rounds of Grep and Read. Use it when looking for where something is implemented or how a feature or flow works, when the user describes a behaviour or a bug rather than naming the exact symbol, before changing code in a repo you do not know well, to see what else must change (copy-pasted duplicates, files that change together), or to map and get oriented in a codebase. Invoke it with the search words as the argument, e.g. "where checkout totals are computed". Skip it in a tiny repo or when you already know the exact file and line.
license: MIT
compatibility: Python 3.9+ and bash (Git Bash on Windows); git optional. In Claude Code the lookup below runs automatically; other agents run the command themselves.
allowed-tools: Bash(bash "${CLAUDE_SKILL_DIR}/scripts/atlas" *)
---

# Repo Atlas

```!
bash "${CLAUDE_SKILL_DIR}/scripts/atlas" find --stdin --root "${CLAUDE_PROJECT_DIR}" <<'ATLAS_QUERY'
$ARGUMENTS
ATLAS_QUERY
```

Above: the lookup for this request (ranked symbols with their code), or the map brief if no search words were passed. If you see the command instead of its output, run it.

Every extra turn re-reads the whole context, so one call that returns code beats Grep, then Read, then Read:
- More lookups: `bash "${CLAUDE_SKILL_DIR}/scripts/atlas" find "first thing" "second thing"`. Put everything you need in one call, and run it exactly as written, as a command of its own: that form is pre-approved.
- Answer from the code shown only when it is the thing asked about. If it is merely nearby (you would write "probably" or "I assume", or the answer hinges on a caller, a definition or a file you have not seen), take one targeted step first: check the `other matching files`, Grep an identifier from the shown code, or Read the range. Read with offset/limit on `Lx-y`; never read a whole file over ~300 lines.
- The lookup searches code only: UI layouts, templates, installers, configs and docs are not in it, so Grep for those.
- Grep remains the fastest way to find an exact identifier or string.
- `same body:` marks copy-pasted code (change every copy, or find the live one); `name also in:` the same name in other files. `.atlas/_map.md` lists duplicates, unreferenced files, generated files and files that change together ("what else breaks?").
- Before editing, Read the actual range: the map is a pointer, the code is the truth.

At the end, only if you learned something a search would miss (code in a surprising place, a trap, dead code, which duplicate is live), record it in one call; notes appear with future search results:
`bash "${CLAUDE_SKILL_DIR}/scripts/atlas" note "path/to/file.py::Symbol | what it really does or the trap" ...`
Conventions: [references/maintain.md](references/maintain.md).

First use in a repo: the map builds itself (seconds, no tokens). Then offer the user `bash "${CLAUDE_SKILL_DIR}/scripts/atlas" init --claude-md`, which adds a 2-line pointer to CLAUDE.md so future sessions use the map; ask before writing to CLAUDE.md.
