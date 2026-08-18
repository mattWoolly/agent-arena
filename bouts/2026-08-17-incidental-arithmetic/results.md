# Bout results: 2026-08-17-incidental-arithmetic

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 13-ledger | claude-opus-5 | 3/3 | 5/5 | 120 ±13 | 0.54 ±0.01 | 8.3 ±0.6 | 8848 ±233 | 229718 ±19026 |
| 13-ledger | claude-sonnet-5 | 3/3 | 5/5 | 63 ±9 | 0.28 ±0.03 | 7.7 ±1.2 | 5790 ±884 | 279335 ±46180 |
| 13-ledger | glm-5.3 | 3/3 | 5/5 | 121 ±48 | 0.39 ±0.09 | 10.0 ±3.0 | 6745 ±2627 | 224811 ±105702 |
| 13-ledger | gpt-5.6-sol | 3/3 | 5/5 | 87 ±45 | 0.43 ±0.19 | 16.3 ±9.2 | 5094 ±2123 | 272539 ±226342 |
| 13-ledger | kimi-k3 | 3/3 | 5/5 | 77 ±11 | 0.11 ±0.01 | 5.0 ±1.7 | 2787 ±591 | 86613 ±18327 |
| 13-ledger-explicit | claude-opus-5 | 3/3 | 2/2 | 63 ±17 | 0.35 ±0.07 | 6.3 ±1.2 | 4853 ±1247 | 157372 ±34571 |
| 13-ledger-explicit | claude-sonnet-5 | 3/3 | 2/2 | 33 ±1 | 0.22 ±0.02 | 8.3 ±1.5 | 2656 ±98 | 278580 ±27242 |
| 13-ledger-explicit | glm-5.3 | 3/3 | 2/2 | 38 ±4 | 0.19 ±0.07 | 5.3 ±1.2 | 1608 ±78 | 86720 ±13275 |
| 13-ledger-explicit | gpt-5.6-sol | 3/3 | 2/2 | 41 ±5 | 0.26 ±0.03 | 10.7 ±1.2 | 2375 ±590 | 122741 ±16330 |
| 13-ledger-explicit | kimi-k3 | 3/3 | 2/2 | 37 ±4 | 0.10 ±0.04 | 4.7 ±1.5 | 1338 ±122 | 57259 ±22832 |
| 14-schedule | claude-opus-5 | 3/3 | 5/5 | 56 ±11 | 0.29 ±0.05 | 4.7 ±1.2 | 3879 ±746 | 108946 ±33747 |
| 14-schedule | claude-sonnet-5 | 3/3 | 5/5 | 33 ±3 | 0.17 ±0.01 | 4.7 ±0.6 | 2656 ±344 | 144931 ±21776 |
| 14-schedule | glm-5.3 | 3/3 | 5/5 | 45 ±7 | 0.18 ±0.04 | 5.0 ±0.0 | 2547 ±736 | 93547 ±15337 |
| 14-schedule | gpt-5.6-sol | 3/3 | 5/5 | 27 ±3 | 0.18 ±0.00 | 6.0 ±0.0 | 1482 ±99 | 61880 ±597 |
| 14-schedule | kimi-k3 | 3/3 | 5/5 | 45 ±3 | 0.09 ±0.01 | 5.0 ±0.0 | 1580 ±45 | 77483 ±4067 |
| 14-schedule-explicit | claude-opus-5 | 3/3 | 2/2 | 35 ±3 | 0.23 ±0.01 | 4.0 ±0.0 | 2702 ±432 | 90076 ±937 |
| 14-schedule-explicit | claude-sonnet-5 | 3/3 | 2/2 | 29 ±10 | 0.17 ±0.04 | 4.7 ±1.5 | 2708 ±1269 | 156652 ±56365 |
| 14-schedule-explicit | glm-5.3 | 3/3 | 2/2 | 48 ±14 | 0.17 ±0.07 | 4.7 ±0.6 | 2592 ±438 | 85483 ±14604 |
| 14-schedule-explicit | gpt-5.6-sol | 3/3 | 2/2 | 35 ±8 | 0.21 ±0.03 | 7.3 ±1.2 | 1892 ±500 | 90022 ±24201 |
| 14-schedule-explicit | kimi-k3 | 3/3 | 2/2 | 44 ±8 | 0.06 ±0.02 | 4.0 ±0.0 | 1687 ±252 | 61355 ±7395 |
| 15-rollup | claude-opus-5 | 3/3 | 3/3 | 70 ±2 | 0.34 ±0.01 | 6.3 ±0.6 | 4978 ±539 | 154886 ±14261 |
| 15-rollup | claude-sonnet-5 | 3/3 | 3/3 | 34 ±2 | 0.17 ±0.01 | 3.7 ±0.6 | 2944 ±174 | 120358 ±21600 |
| 15-rollup | glm-5.3 | 3/3 | 3/3 | 58 ±8 | 0.22 ±0.04 | 7.0 ±1.0 | 3591 ±256 | 122240 ±40399 |
| 15-rollup | gpt-5.6-sol | 3/3 | 3/3 | 40 ±7 | 0.22 ±0.02 | 10.3 ±1.2 | 1676 ±238 | 111587 ±24451 |
| 15-rollup | kimi-k3 | 3/3 | 3/3 | 58 ±19 | 0.08 ±0.00 | 6.0 ±0.0 | 2135 ±857 | 81067 ±1478 |
| 15-rollup-explicit | claude-opus-5 | 3/3 | 2/2 | 49 ±4 | 0.30 ±0.02 | 6.3 ±0.6 | 3681 ±201 | 152176 ±16590 |
| 15-rollup-explicit | claude-sonnet-5 | 3/3 | 2/2 | 34 ±9 | 0.17 ±0.02 | 3.3 ±0.6 | 3090 ±1058 | 107848 ±22756 |
| 15-rollup-explicit | glm-5.3 | 3/3 | 2/2 | 65 ±5 | 0.20 ±0.02 | 7.3 ±0.6 | 3533 ±767 | 139072 ±16310 |
| 15-rollup-explicit | gpt-5.6-sol | 3/3 | 2/2 | 48 ±10 | 0.24 ±0.03 | 11.3 ±0.6 | 2083 ±708 | 133439 ±13435 |
| 15-rollup-explicit | kimi-k3 | 3/3 | 2/2 | 56 ±7 | 0.09 ±0.01 | 6.3 ±0.6 | 1850 ±483 | 89429 ±14357 |

- **claude-opus-5**: 18/18 runs passed; per pass-through of all tasks: ~$2.03, ~392s wall
- **claude-sonnet-5**: 18/18 runs passed; per pass-through of all tasks: ~$1.19, ~226s wall
- **glm-5.3**: 18/18 runs passed; per pass-through of all tasks: ~$1.36, ~375s wall
- **gpt-5.6-sol**: 18/18 runs passed; per pass-through of all tasks: ~$1.54, ~278s wall
- **kimi-k3**: 18/18 runs passed; per pass-through of all tasks: ~$0.54, ~317s wall

- served-model check: OK, all runs matched EXPECTED.json (served: claude-opus-5, claude-sonnet-5, glm-5.3, gpt-5.6-sol, kimi-k3)

- env: `2.1.234 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
