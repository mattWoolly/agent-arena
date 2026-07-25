# Bout results: 2026-07-25-opus5-anchors

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 01-bugfix | claude-fable-5 | 3/3 | 3/3 | 44 ±6 | 0.42 ±0.09 | 7.3 ±0.6 | 1656 ±131 | 137959 ±20415 |
| 01-bugfix | claude-opus-4-8 | 3/3 | 3/3 | 38 ±2 | 0.19 ±0.00 | 7.0 ±0.0 | 2522 ±120 | 129977 ±222 |
| 04-terminal | claude-fable-5 | 3/3 | 4/4 | 86 ±7 | 0.65 ±0.01 | 17.7 ±1.2 | 3560 ±99 | 319716 ±13013 |
| 04-terminal | claude-opus-4-8 | 3/3 | 4/4 | 84 ±2 | 0.34 ±0.00 | 14.7 ±3.2 | 5681 ±168 | 224275 ±16499 |
| 06-instructions | claude-fable-5 | 3/3 | 6/6 | 44 ±2 | 0.35 ±0.01 | 5.0 ±0.0 | 2501 ±188 | 105989 ±168 |
| 06-instructions | claude-opus-4-8 | 3/3 | 6/6 | 44 ±8 | 0.20 ±0.02 | 6.0 ±1.0 | 3303 ±792 | 124089 ±22902 |

- **claude-fable-5**: 9/9 runs passed; per pass-through of all tasks: ~$1.42, ~174s wall
- **claude-opus-4-8**: 9/9 runs passed; per pass-through of all tasks: ~$0.73, ~167s wall

- env: `2.1.214 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
