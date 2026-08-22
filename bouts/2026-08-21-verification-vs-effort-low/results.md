# Bout results: 2026-08-21-verification-vs-effort-low

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 16-source-audit-verify | claude-sonnet-5 | 1/1 | 3/3 | 42 | 0.13 | 3 | 4050 | 96909 |

- **claude-sonnet-5**: 1/1 runs passed; per pass-through of all tasks: ~$0.13, ~42s wall

- served-model check: OK, all runs matched EXPECTED.json (served: claude-sonnet-5)

- env: `2.1.239 (Claude Code)`, effort=`low`, setting-sources=`project`
