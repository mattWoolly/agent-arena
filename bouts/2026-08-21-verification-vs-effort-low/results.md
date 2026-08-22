# Bout results: 2026-08-21-verification-vs-effort-low

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 16-source-audit | claude-sonnet-5 | 10/10 | 3/3 | 38 ±12 | 0.12 ±0.01 | 6.6 ±1.7 | 3117 ±451 | 161062 ±24161 |
| 16-source-audit-verify | claude-sonnet-5 | 10/10 | 3/3 | 38 ±5 | 0.13 ±0.01 | 6.2 ±2.1 | 3596 ±558 | 146758 ±25354 |

- **claude-sonnet-5**: 20/20 runs passed; per pass-through of all tasks: ~$0.25, ~76s wall

- served-model check: OK, all runs matched EXPECTED.json (served: claude-sonnet-5)

- env: `2.1.239 (Claude Code)`, effort=`low`, setting-sources=`project`
