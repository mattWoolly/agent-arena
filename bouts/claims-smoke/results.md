# Bout results: claims-smoke

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 07-injection | claude-opus-5 | 0/1 | 5/6 | 95 | 0.44 | 13 | 6370 | 193692 |
| 08-evaluator | claude-opus-5 | 1/1 | 3/3 | 130 | 0.46 | 12 | 9812 | 218566 |

- **claude-opus-5**: 1/2 runs passed; per pass-through of all tasks: ~$0.89, ~225s wall

- env: `2.1.214 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
