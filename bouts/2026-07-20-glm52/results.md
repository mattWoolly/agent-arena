# Bout results: 2026-07-20-glm52

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 01-bugfix | claude-opus-4-8 | 1/1 | 3/3 | 43 | 0.19 | 8 | 2513 | 127428 |
| 01-bugfix | glm-5.2 | 3/3 | 3/3 | 74 ±11 | 0.08 ±0.02 | 9.0 ±0.0 | 2558 ±304 | 194752 ±40264 |
| 02-synthesis | claude-opus-4-8 | 1/1 | 6/6 | 102 | 0.40 | 10 | 7622 | 240743 |
| 02-synthesis | glm-5.2 | 3/3 | 6/6 | 182 ±38 | 0.14 ±0.06 | 8.3 ±6.7 | 9857 ±1337 | 243157 ±236211 |
| 03-refactor | claude-opus-4-8 | 1/1 | 4/4 | 39 | 0.18 | 13 | 2259 | 126237 |
| 03-refactor | glm-5.2 | 3/3 | 4/4 | 84 ±17 | 0.08 ±0.03 | 15.0 ±2.0 | 3060 ±411 | 210688 ±84085 |
| 04-terminal | claude-opus-4-8 | 1/1 | 4/4 | 77 | 0.30 | 13 | 4846 | 204999 |
| 04-terminal | glm-5.2 | 3/3 | 4/4 | 140 ±10 | 0.16 ±0.01 | 20.3 ±4.2 | 3628 ±772 | 474091 ±29256 |
| 05-review | claude-opus-4-8 | 1/1 | 6/6 | 65 | 0.22 | 7 | 4428 | 80922 |
| 05-review | glm-5.2 | 3/3 | 6/6 | 162 ±24 | 0.08 ±0.01 | 8.0 ±1.0 | 6622 ±963 | 151595 ±53849 |
| 05-review-transplant | claude-opus-4-8 | 1/1 | 6/6 | 166 | 0.46 | 8 | 11432 | 113287 |
| 05-review-transplant | glm-5.2 | 3/3 | 6/6 | 206 ±21 | 0.10 ±0.01 | 8.3 ±0.6 | 8328 ±1047 | 132715 ±14440 |
| 06-instructions | claude-opus-4-8 | 1/1 | 6/6 | 53 | 0.22 | 7 | 3298 | 151888 |
| 06-instructions | glm-5.2 | 3/3 | 6/6 | 110 ±72 | 0.08 ±0.04 | 6.3 ±1.5 | 5160 ±4471 | 161173 ±45069 |
| 06-instructions-transplant | claude-opus-4-8 | 1/1 | 6/6 | 117 | 0.41 | 8 | 8681 | 182333 |
| 06-instructions-transplant | glm-5.2 | 3/3 | 6/6 | 195 ±148 | 0.13 ±0.05 | 8.7 ±2.5 | 8900 ±5859 | 239168 ±106159 |

- **claude-opus-4-8**: 8/8 runs passed; per pass-through of all tasks: ~$2.38, ~661s wall
- **glm-5.2**: 24/24 runs passed; per pass-through of all tasks: ~$0.86, ~1153s wall

- env: `2.1.214 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
