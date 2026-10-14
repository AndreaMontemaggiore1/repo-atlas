## Description length vs triggering (2026-10-12): Sonnet 5.5, Claude Code 2.1.293, 1 repetition

The 20 gPodder triggering prompts (10 that should use the skill, 10 that should not), skill installed with no
hint. Both descriptions ran on the same day and CLI. S is the current description (about 188 tokens). S-short is
a description trimmed to about 84 tokens, on the principle that an always-loaded description should be pruned
hard.

- The short one fired on 5/10 prompts that should use the skill, the current one on 8/10. Neither fired on the
  prompts that should not.
- The four prompts the short one always missed ask "where is the code that…" or "how does the app…". The
  current description covers them ("where something is implemented or how a feature or flow works"). In a
  partial second repetition of the current description, those four fired every time.
- The first use in a repo, which builds the map that the plugin's hook relies on, depends on the description. So
  the current description stays, at about 100 tokens more per call.
