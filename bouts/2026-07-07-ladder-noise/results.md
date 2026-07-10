# Bout results: 2026-07-07-ladder-noise

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 01-bugfix | claude-fable-5 | 5/5 | 3/3 | 47 ±3 | 0.35 ±0.00 | 7.2 ±0.4 | 1555 ±48 | 127923 ±422 |
| 01-bugfix | claude-haiku-4-5 | 5/5 | 3/3 | 22 ±1 | 0.04 ±0.00 | 10.6 ±1.1 | 1858 ±142 | 175352 ±22663 |
| 01-bugfix | claude-opus-4-8 | 5/5 | 3/3 | 39 ±3 | 0.20 ±0.01 | 7.8 ±0.8 | 2587 ±310 | 123344 ±650 |
| 01-bugfix | claude-sonnet-5 | 5/5 | 3/3 | 34 ±3 | 0.15 ±0.00 | 10.4 ±0.5 | 2349 ±195 | 228123 ±484 |
| 02-synthesis | claude-fable-5 | 5/5 | 6/6 | 87 ±14 | 0.61 ±0.07 | 8.0 ±2.2 | 5037 ±387 | 179860 ±55072 |
| 02-synthesis | claude-haiku-4-5 | 5/5 | 6/6 | 63 ±15 | 0.10 ±0.02 | 13.8 ±3.0 | 7241 ±2132 | 380939 ±99575 |
| 02-synthesis | claude-opus-4-8 | 5/5 | 6/6 | 118 ±42 | 0.33 ±0.03 | 4.2 ±0.4 | 7712 ±865 | 86333 ±12797 |
| 02-synthesis | claude-sonnet-5 | 5/5 | 6/6 | 70 ±6 | 0.25 ±0.02 | 6.6 ±0.9 | 7171 ±847 | 231489 ±36057 |
| 03-refactor | claude-fable-5 | 5/5 | 4/4 | 54 ±3 | 0.44 ±0.03 | 13.2 ±1.1 | 2544 ±213 | 149387 ±11433 |
| 03-refactor | claude-haiku-4-5 | 5/5 | 4/4 | 36 ±5 | 0.06 ±0.00 | 14.0 ±1.0 | 2899 ±150 | 252623 ±19221 |
| 03-refactor | claude-opus-4-8 | 5/5 | 4/4 | 44 ±6 | 0.22 ±0.02 | 13.4 ±0.5 | 2542 ±253 | 156219 ±13520 |
| 03-refactor | claude-sonnet-5 | 5/5 | 4/4 | 32 ±4 | 0.16 ±0.01 | 13.6 ±0.5 | 2254 ±257 | 250104 ±19816 |
| 04-terminal | claude-fable-5 | 5/5 | 4/4 | 93 ±11 | 0.72 ±0.07 | 17.4 ±0.5 | 4046 ±404 | 331606 ±48353 |
| 04-terminal | claude-haiku-4-5 | 5/5 | 4/4 | 42 ±3 | 0.08 ±0.01 | 20.6 ±1.8 | 2739 ±157 | 476025 ±67844 |
| 04-terminal | claude-opus-4-8 | 5/5 | 4/4 | 92 ±12 | 0.40 ±0.05 | 16.4 ±4.3 | 5334 ±409 | 332374 ±79537 |
| 04-terminal | claude-sonnet-5 | 5/5 | 4/4 | 62 ±9 | 0.31 ±0.04 | 22.0 ±1.9 | 3875 ±220 | 629062 ±98096 |
| 05-review | claude-fable-5 | 5/5 | 6/6 | 94 ±16 | 0.59 ±0.08 | 7.6 ±0.5 | 5804 ±1227 | 98605 ±15962 |
| 05-review | claude-haiku-4-5 | 5/5 | 6/6 | 17 ±3 | 0.03 ±0.00 | 7.6 ±0.9 | 1340 ±199 | 114625 ±35365 |
| 05-review | claude-opus-4-8 | 5/5 | 6/6 | 97 ±44 | 0.29 ±0.02 | 7.6 ±0.5 | 5670 ±363 | 99067 ±22425 |
| 05-review | claude-sonnet-5 | 5/5 | 6/6 | 83 ±15 | 0.23 ±0.02 | 8.6 ±0.5 | 7021 ±1202 | 173507 ±19507 |
| 06-instructions | claude-fable-5 | 5/5 | 6/6 | 54 ±4 | 0.40 ±0.04 | 5.4 ±0.5 | 2842 ±496 | 112328 ±12981 |
| 06-instructions | claude-haiku-4-5 | 3/5 | 4/6, 6/6 | 18 ±4 | 0.03 ±0.01 | 4.6 ±0.5 | 1582 ±671 | 99539 ±14534 |
| 06-instructions | claude-opus-4-8 | 5/5 | 6/6 | 91 ±25 | 0.29 ±0.10 | 7.2 ±2.4 | 5120 ±2002 | 151600 ±68212 |
| 06-instructions | claude-sonnet-5 | 5/5 | 6/6 | 47 ±12 | 0.20 ±0.03 | 8.2 ±1.3 | 3931 ±929 | 272682 ±50008 |

- **claude-fable-5**: 30/30 runs passed; per pass-through of all tasks: ~$3.13, ~430s wall
- **claude-haiku-4-5**: 28/30 runs passed; per pass-through of all tasks: ~$0.35, ~196s wall
- **claude-opus-4-8**: 30/30 runs passed; per pass-through of all tasks: ~$1.72, ~482s wall
- **claude-sonnet-5**: 30/30 runs passed; per pass-through of all tasks: ~$1.30, ~328s wall

- env: `2.1.202 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
- env: `2.1.203 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
