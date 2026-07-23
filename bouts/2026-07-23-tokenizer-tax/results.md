# Bout results: 2026-07-23-tokenizer-tax

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 01-bugfix | claude-sonnet-4-6 | 2/2 | 3/3 | 30 ±0 | 0.11 ±0.00 | 7.0 ±1.4 | 1398 ±68 | 145996 ±2162 |
| 02-synthesis | claude-sonnet-4-6 | 1/2 | 0/6, 6/6 | 58 ±79 | 0.08 ±0.11 | 2.0 ±1.4 | 7968 | 40418 |
| 03-refactor | claude-sonnet-4-6 | 0/2 | 2/4 | 2 ±0 | 0.00 ±0.00 | 1.0 ±0.0 | — | — |
| 04-terminal | claude-sonnet-4-6 | 0/2 | 2/4 | 2 ±0 | 0.00 ±0.00 | 1.0 ±0.0 | — | — |
| 05-review | claude-sonnet-4-6 | 0/2 | 0/6 | 2 ±0 | 0.00 ±0.00 | 1.0 ±0.0 | — | — |
| 05-review-transplant | claude-sonnet-4-6 | 0/2 | 0/6 | 2 ±0 | 0.00 ±0.00 | 1.0 ±0.0 | — | — |
| 06-instructions | claude-sonnet-4-6 | 0/2 | 1/6 | 2 ±0 | 0.00 ±0.00 | 1.0 ±0.0 | — | — |
| 06-instructions-transplant | claude-sonnet-4-6 | 0/2 | 1/6 | 2 ±0 | 0.00 ±0.00 | 1.0 ±0.0 | — | — |

- **claude-sonnet-4-6**: 3/16 runs passed; per pass-through of all tasks: ~$0.19, ~98s wall

- env: `2.1.214 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
