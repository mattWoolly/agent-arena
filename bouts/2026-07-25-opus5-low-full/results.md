# Bout results: 2026-07-25-opus5-low-full

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 01-bugfix | claude-opus-5 | 3/3 | 3/3 | 22 ±0 | 0.14 ±0.00 | 6.0 ±0.0 | 1082 ±63 | 124576 ±82 |
| 02-synthesis | claude-opus-5 | 3/3 | 6/6 | 44 ±6 | 0.23 ±0.05 | 8.0 ±3.5 | 3397 ±388 | 170983 ±79428 |
| 03-refactor | claude-opus-5 | 3/3 | 4/4 | 38 ±1 | 0.22 ±0.02 | 11.0 ±2.0 | 2359 ±195 | 197694 ±44791 |
| 04-terminal | claude-opus-5 | 3/3 | 4/4 | 35 ±3 | 0.19 ±0.01 | 8.3 ±0.6 | 1812 ±217 | 177182 ±13150 |
| 05-review | claude-opus-5 | 3/3 | 6/6 | 26 ±2 | 0.16 ±0.00 | 7.0 ±0.0 | 1256 ±174 | 144767 ±9 |
| 05-review-transplant | claude-opus-5 | 3/3 | 6/6 | 36 ±2 | 0.16 ±0.02 | 6.0 ±1.7 | 2191 ±142 | 101532 ±38712 |
| 06-instructions | claude-opus-5 | 3/3 | 6/6 | 28 ±3 | 0.14 ±0.01 | 5.3 ±0.6 | 1781 ±249 | 99960 ±1100 |
| 06-instructions-transplant | claude-opus-5 | 3/3 | 6/6 | 56 ±6 | 0.24 ±0.03 | 8.0 ±2.0 | 3656 ±209 | 172749 ±49306 |

- **claude-opus-5**: 24/24 runs passed; per pass-through of all tasks: ~$1.48, ~286s wall

- env: `2.1.214 (Claude Code)`, effort=`low`, setting-sources=`project`
