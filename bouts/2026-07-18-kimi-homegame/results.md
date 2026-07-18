# Bout results: 2026-07-18-kimi-homegame

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 01-bugfix | kimi-k3-kimicode | 3/3 | 3/3 | 110 ±5 | 0.13 ±0.02 | 9.0 ±2.0 | 1930 ±296 | 189440 ±43601 |
| 02-synthesis | kimi-k3-kimicode | 3/3 | 6/6 | 166 ±30 | 0.19 ±0.02 | 11.0 ±1.0 | 5050 ±722 | 240555 ±31497 |
| 03-refactor | kimi-k3-kimicode | 3/3 | 4/4 | 142 ±22 | 0.17 ±0.01 | 12.0 ±1.0 | 2928 ±282 | 263424 ±21668 |
| 04-terminal | kimi-k3-kimicode | 3/3 | 4/4 | 386 ±111 | 0.35 ±0.09 | 19.7 ±6.0 | 9426 ±2464 | 489643 ±162030 |
| 05-review | kimi-k3-kimicode | 3/3 | 6/6 | 144 ±18 | 0.11 ±0.01 | 3.0 ±0.0 | 3756 ±368 | 54272 ±0 |
| 05-review-transplant | kimi-k3-kimicode | 3/3 | 6/6 | 201 ±63 | 0.15 ±0.02 | 3.0 ±0.0 | 5577 ±1381 | 54357 ±296 |
| 06-instructions | kimi-k3-kimicode | 3/3 | 6/6 | 124 ±63 | 0.12 ±0.04 | 5.7 ±1.2 | 3409 ±2169 | 114005 ±26047 |
| 06-instructions-transplant | kimi-k3-kimicode | 3/3 | 6/6 | 312 ±89 | 0.26 ±0.07 | 10.7 ±3.2 | 8313 ±2422 | 261632 ±97334 |

- **kimi-k3-kimicode**: 24/24 runs passed; per pass-through of all tasks: ~$1.48, ~1586s wall

**⚠ peek-check warnings** (transcript referenced grader assets):
- 03-refactor/kimi-k3-kimicode/run-1: suspect: /home/mwoolly/projects/agent-arena
- 04-terminal/kimi-k3-kimicode/run-1: suspect: /home/mwoolly/projects/agent-arena
- 04-terminal/kimi-k3-kimicode/run-2: suspect: /home/mwoolly/projects/agent-arena
- 04-terminal/kimi-k3-kimicode/run-3: suspect: /home/mwoolly/projects/agent-arena

- env: `kimi-code 0.27.0`, effort=`max (kimi-code default for k3)`, setting-sources=`arena config.toml only`
