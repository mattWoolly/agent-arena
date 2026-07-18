# Bout results: 2026-07-17-sol-codex-homegame

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 01-bugfix | gpt-5.6-sol-codex | 3/3 | 3/3 | 21 ±2 | 0.12 ±0.01 | 1.0 ±0.0 | 841 ±103 | 52378 ±7579 |
| 02-synthesis | gpt-5.6-sol-codex | 3/3 | 6/6 | 50 ±9 | 0.19 ±0.01 | 1.0 ±0.0 | 2797 ±248 | 49584 ±751 |
| 03-refactor | gpt-5.6-sol-codex | 3/3 | 4/4 | 31 ±3 | 0.15 ±0.00 | 1.0 ±0.0 | 1497 ±44 | 61990 ±269 |
| 04-terminal | gpt-5.6-sol-codex | 3/3 | 4/4 | 39 ±1 | 0.19 ±0.01 | 1.0 ±0.0 | 1634 ±69 | 148731 ±12983 |
| 05-review | gpt-5.6-sol-codex | 3/3 | 6/6 | 33 ±8 | 0.12 ±0.01 | 1.0 ±0.0 | 1042 ±230 | 45385 ±7061 |
| 05-review-transplant | gpt-5.6-sol-codex | 3/3 | 6/6 | 45 ±2 | 0.14 ±0.00 | 1.0 ±0.0 | 1437 ±134 | 51453 ±894 |
| 06-instructions | gpt-5.6-sol-codex | 3/3 | 6/6 | 29 ±6 | 0.14 ±0.01 | 1.0 ±0.0 | 1509 ±205 | 57202 ±8256 |
| 06-instructions-transplant | gpt-5.6-sol-codex | 3/3 | 6/6 | 57 ±9 | 0.19 ±0.02 | 1.0 ±0.0 | 2745 ±581 | 65134 ±13034 |

- **gpt-5.6-sol-codex**: 24/24 runs passed; per pass-through of all tasks: ~$1.25, ~305s wall

- env: `codex-cli 0.144.4`, effort=`codex-default`, setting-sources=`none (--ignore-user-config, isolated CODEX_HOME)`
