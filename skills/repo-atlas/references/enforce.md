# Optional: block whole-file reads of big files

A `PreToolUse` hook that denies a `Read` without offset/limit of a code file over 300 lines and replies, in the same turn, with that file's symbols and their line ranges, so the model re-reads only the part it needs. Everything else passes. It works without invoking the skill, which makes it useful in repos with huge files.

Add to the project's `.claude/settings.json` (adjust the path if the skill is installed in `~/.claude/skills`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read",
        "hooks": [{ "type": "command", "command": "bash .claude/skills/repo-atlas/scripts/atlas gate" }]
      }
    ]
  }
}
```

Threshold: environment variable `ATLAS_GATE_MAX_LINES` (default 300). The hook never blocks anything outside the project, non-code files, or ranged reads.
