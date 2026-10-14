# Keeping the map useful

`atlas` below means `bash "<skill dir>/scripts/atlas"`.

## What is generated (free, never edit)
`.atlas/_map.md` (bounded overview: brief, ranking, duplicates, names defined in several files, unreferenced files, generated/noise files, co-change), `_map.json`, `symbols.json`, `meta.json`. `atlas find` builds them on first use and rebuilds when many files changed; `atlas map` forces a rebuild. `atlas init` writes `.atlas/.gitignore` so only `notes.md` is committed.

## Notes: what is worth one line
Only what a search would miss next time:
- code in a non-obvious place ("YouTube support lives in `share/.../extensions/`, not `src/`") - the case where a map measurably helps;
- which copy is live among duplicates, dead code, traps (`!`), unverified guesses (`?`);
- in the words someone would use to ask for it (feature names, symptoms): `find` matches them.

Do not restate what the code or `_map.md` already says, and do not note code you did not read.

## How (one call, at the end)
```
atlas note "src/billing/invoice.py::total | VAT added here, not in cart.py" "! src/api/routes.js | auth checked per route, no middleware"
```
- Anchor = `path` or `path::Symbol` (`Class.method` or just `method` if unique). The symbol is resolved and its `~Lx-y` range filled in; unknown anchors are rejected with a reason.
- Optional prefix: `!` trap, `?` unverified, `x` dead, `→` flow step, `@` entry point.
- Notes go to `.atlas/notes.md` (≤ 200 lines; merge or drop stale lines by hand when it grows).

## Checking
`atlas check` reports notes whose file or symbol disappeared and line-hint drift; `atlas check --fix-lines` realigns the `~L` hints. If code and a note disagree, the code wins: fix or delete the note.

Format details: [format.md](format.md). Optional enforcement hook: [enforce.md](enforce.md).
