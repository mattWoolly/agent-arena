# Bout results: 2026-07-25-opus5-sweep-high

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 01-bugfix | claude-opus-5 | 3/3 | 3/3 | 44 ±1 | 0.24 ±0.05 | 9.3 ±0.6 | 2751 ±325 | 149133 ±8917 |
| 04-terminal | claude-opus-5 | 3/3 | 4/4 | 87 ±22 | 0.42 ±0.09 | 20.0 ±2.6 | 5581 ±1139 | 383657 ±105741 |
| 06-instructions | claude-opus-5 | 3/3 | 6/6 | 100 ±32 | 0.41 ±0.11 | 11.3 ±2.1 | 7297 ±2449 | 269977 ±62051 |

- **claude-opus-5**: 9/9 runs passed; per pass-through of all tasks: ~$1.07, ~232s wall

- env: `2.1.214 (Claude Code)`, effort=`high`, setting-sources=`project`
