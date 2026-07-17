# Bout results: 2026-07-16-kimi3-vs-opus48-vs-fable5

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 01-bugfix | claude-fable-5 | 3/3 | 3/3 | 35 ±2 | 0.34 ±0.01 | 8.3 ±1.2 | 1650 ±141 | 132172 ±699 |
| 01-bugfix | claude-opus-4-8 | 3/3 | 3/3 | 38 ±2 | 0.18 ±0.01 | 7.3 ±0.6 | 2447 ±305 | 126467 ±911 |
| 01-bugfix | kimi-k3 | 3/3 | 3/3 | 64 ±6 | 0.25 ±0.07 | 7.0 ±1.0 | 1163 ±114 | 114432 ±13741 |
| 02-synthesis | claude-fable-5 | 3/3 | 6/6 | 83 ±10 | 0.69 ±0.04 | 9.3 ±0.6 | 6145 ±650 | 220511 ±13260 |
| 02-synthesis | claude-opus-4-8 | 3/3 | 6/6 | 92 ±18 | 0.34 ±0.06 | 4.7 ±0.6 | 8001 ±1524 | 103283 ±17593 |
| 02-synthesis | kimi-k3 | 3/3 | 6/6 | 131 ±55 | 0.25 ±0.05 | 6.3 ±4.0 | 3578 ±624 | 141995 ±110810 |
| 03-refactor | claude-fable-5 | 3/3 | 4/4 | 47 ±3 | 0.45 ±0.02 | 15.0 ±1.0 | 2969 ±366 | 159409 ±523 |
| 03-refactor | claude-opus-4-8 | 3/3 | 4/4 | 36 ±3 | 0.20 ±0.02 | 14.0 ±1.0 | 2603 ±301 | 150865 ±23644 |
| 03-refactor | kimi-k3 | 3/3 | 4/4 | 80 ±0 | 0.24 ±0.00 | 14.0 ±0.0 | 1852 ±55 | 123392 ±0 |
| 04-terminal | claude-fable-5 | 3/3 | 4/4 | 71 ±6 | 0.62 ±0.03 | 17.7 ±0.6 | 3722 ±153 | 271242 ±35273 |
| 04-terminal | claude-opus-4-8 | 3/3 | 4/4 | 87 ±7 | 0.38 ±0.03 | 16.7 ±1.2 | 5679 ±761 | 312963 ±73166 |
| 04-terminal | kimi-k3 | 3/3 | 4/4 | 150 ±19 | 0.36 ±0.07 | 19.7 ±4.5 | 2907 ±495 | 345941 ±56952 |
| 05-review | claude-fable-5 | 3/3 | 6/6 | 88 ±18 | 0.58 ±0.10 | 7.7 ±0.6 | 5964 ±1502 | 104475 ±17040 |
| 05-review | claude-opus-4-8 | 3/3 | 6/6 | 64 ±6 | 0.23 ±0.01 | 6.7 ±0.6 | 4464 ±188 | 82082 ±126 |
| 05-review | kimi-k3 | 3/3 | 6/6 | 153 ±40 | 0.23 ±0.06 | 7.3 ±0.6 | 3649 ±778 | 91904 ±12808 |
| 05-review-transplant | claude-fable-5 | 3/3 | 6/6 | 127 ±30 | 0.73 ±0.14 | 8.0 ±1.0 | 7629 ±851 | 95042 ±16751 |
| 05-review-transplant | claude-opus-4-8 | 3/3 | 6/6 | 95 ±4 | 0.32 ±0.01 | 7.7 ±0.6 | 6586 ±585 | 124628 ±49129 |
| 05-review-transplant | kimi-k3 | 3/3 | 6/6 | 210 ±14 | 0.32 ±0.02 | 8.3 ±0.6 | 5910 ±999 | 97451 ±15827 |
| 06-instructions | claude-fable-5 | 3/3 | 6/6 | 55 ±13 | 0.45 ±0.10 | 6.0 ±1.0 | 3761 ±1311 | 125120 ±16650 |
| 06-instructions | claude-opus-4-8 | 3/3 | 6/6 | 101 ±100 | 0.25 ±0.12 | 5.7 ±1.2 | 4610 ±3197 | 123826 ±36020 |
| 06-instructions | kimi-k3 | 3/3 | 6/6 | 103 ±40 | 0.22 ±0.06 | 6.0 ±1.0 | 2230 ±1207 | 120405 ±39879 |
| 06-instructions-transplant | claude-fable-5 | 3/3 | 6/6 | 103 ±20 | 0.70 ±0.11 | 6.3 ±0.6 | 7402 ±1492 | 146526 ±17670 |
| 06-instructions-transplant | claude-opus-4-8 | 3/3 | 6/6 | 108 ±26 | 0.37 ±0.07 | 6.7 ±0.6 | 7889 ±1909 | 154247 ±19272 |
| 06-instructions-transplant | kimi-k3 | 3/3 | 6/6 | 139 ±42 | 0.27 ±0.06 | 7.0 ±1.7 | 3358 ±1828 | 148224 ±28572 |

- **claude-fable-5**: 24/24 runs passed; per pass-through of all tasks: ~$4.56, ~609s wall
- **claude-opus-4-8**: 24/24 runs passed; per pass-through of all tasks: ~$2.27, ~621s wall
- **kimi-k3**: 24/24 runs passed; per pass-through of all tasks: ~$2.14, ~1031s wall

- env: `2.1.212 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
