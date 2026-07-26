# Bout results: 2026-07-25-opus5-succession

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 01-bugfix | claude-opus-5 | 3/3 | 3/3 | 62 ±0 | 0.27 ±0.02 | 11.0 ±1.7 | 4214 ±253 | 175351 ±16373 |
| 02-synthesis | claude-opus-5 | 3/3 | 6/6 | 146 ±14 | 0.57 ±0.09 | 13.7 ±4.0 | 11029 ±849 | 354583 ±106356 |
| 03-refactor | claude-opus-5 | 3/3 | 4/4 | 79 ±18 | 0.34 ±0.07 | 19.7 ±3.5 | 5411 ±1634 | 226575 ±34809 |
| 04-terminal | claude-opus-5 | 3/3 | 4/4 | 116 ±26 | 0.51 ±0.12 | 23.3 ±4.5 | 7090 ±1206 | 451011 ±166488 |
| 05-review | claude-opus-5 | 3/3 | 6/6 | 96 ±24 | 0.32 ±0.04 | 9.3 ±0.6 | 6432 ±1598 | 151410 ±12912 |
| 05-review-transplant | claude-opus-5 | 3/3 | 6/6 | 150 ±16 | 0.48 ±0.06 | 12.3 ±0.6 | 10776 ±1460 | 203288 ±6551 |
| 06-instructions | claude-opus-5 | 3/3 | 6/6 | 110 ±21 | 0.41 ±0.07 | 8.7 ±1.5 | 8427 ±1525 | 203877 ±45161 |
| 06-instructions-transplant | claude-opus-5 | 3/3 | 6/6 | 116 ±8 | 0.43 ±0.02 | 8.7 ±0.6 | 8975 ±590 | 204972 ±15147 |

- **claude-opus-5**: 24/24 runs passed; per pass-through of all tasks: ~$3.33, ~875s wall

- env: `2.1.214 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
