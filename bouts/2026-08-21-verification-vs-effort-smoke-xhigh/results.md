# Bout results: 2026-08-21-verification-vs-effort-smoke-xhigh

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 15-rollup | claude-sonnet-5 | 1/1 | 3/3 | 37 | 0.12 | 4 | 3523 | 133561 |
| 15-rollup-verify | claude-sonnet-5 | 1/1 | 3/3 | 79 | 0.21 | 8 | 8497 | 218117 |

- **claude-sonnet-5**: 2/2 runs passed; per pass-through of all tasks: ~$0.33, ~116s wall

- served-model check: OK, all runs matched EXPECTED.json (served: claude-sonnet-5)

- env: `2.1.239 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
