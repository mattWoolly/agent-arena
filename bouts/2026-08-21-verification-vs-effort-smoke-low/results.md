# Bout results: 2026-08-21-verification-vs-effort-smoke-low

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 15-rollup | claude-sonnet-5 | 1/1 | 3/3 | 19 | 0.09 | 3 | 1443 | 95143 |
| 15-rollup-verify | claude-sonnet-5 | 1/1 | 3/3 | 25 | 0.09 | 3 | 2064 | 95362 |

- **claude-sonnet-5**: 2/2 runs passed; per pass-through of all tasks: ~$0.18, ~44s wall

- served-model check: OK, all runs matched EXPECTED.json (served: claude-sonnet-5)

- env: `2.1.239 (Claude Code)`, effort=`low`, setting-sources=`project`
