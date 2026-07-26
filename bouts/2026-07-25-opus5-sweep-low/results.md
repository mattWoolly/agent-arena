# Bout results: 2026-07-25-opus5-sweep-low

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 01-bugfix | claude-opus-5 | 3/3 | 3/3 | 23 ±1 | 0.17 ±0.05 | 6.0 ±0.0 | 1022 ±71 | 119578 ±8632 |
| 04-terminal | claude-opus-5 | 3/3 | 4/4 | 54 ±15 | 0.23 ±0.07 | 9.7 ±2.9 | 2457 ±1034 | 208980 ±68338 |
| 06-instructions | claude-opus-5 | 3/3 | 6/6 | 27 ±1 | 0.13 ±0.00 | 5.0 ±0.0 | 1530 ±108 | 99324 ±123 |

- **claude-opus-5**: 9/9 runs passed; per pass-through of all tasks: ~$0.53, ~104s wall

- env: `2.1.214 (Claude Code)`, effort=`low`, setting-sources=`project`
