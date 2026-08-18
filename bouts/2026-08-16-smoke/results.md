# Bout results: 2026-08-16-smoke

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 08-evaluator-hard | claude-opus-5 | 1/1 | 3/3 | 110 | 0.48 | 11 | 8190 | 211255 |
| 08-evaluator-hard | glm-5.3 | 1/1 | 3/3 | 190 | 0.64 | 18 | 12399 | 484416 |
| 08-evaluator-hard | gpt-5.6-sol | 1/1 | 3/3 | 200 | 0.69 | 30 | 8888 | 591811 |
| 08-evaluator-hard | kimi-k3 | 1/1 | 3/3 | 73 | 0.13 | 10 | 2715 | 157952 |

- **claude-opus-5**: 1/1 runs passed; per pass-through of all tasks: ~$0.48, ~110s wall
- **glm-5.3**: 1/1 runs passed; per pass-through of all tasks: ~$0.64, ~190s wall
- **gpt-5.6-sol**: 1/1 runs passed; per pass-through of all tasks: ~$0.69, ~200s wall
- **kimi-k3**: 1/1 runs passed; per pass-through of all tasks: ~$0.13, ~73s wall

- served-model check: OK, all runs matched EXPECTED.json (served: claude-opus-5, glm-5.3, gpt-5.6-sol, kimi-k3)

- env: `2.1.232 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
- env: `2.1.233 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
