# Bout results: 2026-07-07-transplant

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 05-review-transplant | claude-opus-4-8 | 5/5 | 6/6 | 117 ±19 | 0.36 ±0.03 | 7.6 ±0.5 | 8010 ±986 | 95662 ±16179 |
| 06-instructions-transplant | claude-opus-4-8 | 5/5 | 6/6 | 102 ±17 | 0.38 ±0.06 | 7.6 ±1.5 | 7755 ±1278 | 172296 ±46301 |

- **claude-opus-4-8**: 10/10 runs passed; per pass-through of all tasks: ~$0.74, ~220s wall

- env: `2.1.203 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
