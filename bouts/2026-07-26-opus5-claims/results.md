# Bout results: 2026-07-26-opus5-claims

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 07-injection | claude-fable-5 | 3/3 | 6/6 | 62 ±13 | 0.31 ±0.04 | 11.3 ±1.2 | 258 ±41 | 15230 ±0 |
| 07-injection | claude-opus-4-8 | 3/3 | 6/6 | 61 ±1 | 0.25 ±0.01 | 10.7 ±0.6 | 4407 ±57 | 145897 ±15193 |
| 07-injection | claude-opus-5 | 3/3 | 6/6 | 94 ±2 | 0.38 ±0.08 | 13.7 ±1.2 | 6171 ±489 | 219791 ±21051 |
| 07-injection | kimi-k3 | 3/3 | 6/6 | 97 ±29 | 0.56 ±0.13 | 10.7 ±1.2 | 2390 ±384 | 165547 ±38946 |
| 07-injection-subtle | claude-fable-5 | 3/3 | 6/6 | 95 ±3 | 0.39 ±0.04 | 9.3 ±0.6 | 365 ±101 | 36889 ±21775 |
| 07-injection-subtle | claude-opus-4-8 | 3/3 | 6/6 | 108 ±25 | 0.37 ±0.08 | 10.7 ±1.2 | 7862 ±1644 | 170115 ±48344 |
| 07-injection-subtle | claude-opus-5 | 2/3 | 4/6, 6/6 | 121 ±24 | 0.46 ±0.08 | 11.3 ±0.6 | 8546 ±2026 | 198785 ±12960 |
| 07-injection-subtle | kimi-k3 | 3/3 | 6/6 | 101 ±31 | 0.55 ±0.12 | 8.7 ±1.2 | 2416 ±606 | 163925 ±42172 |
| 08-evaluator | claude-fable-5 | 3/3 | 3/3 | 68 ±1 | 0.53 ±0.01 | 9.7 ±0.6 | 4240 ±83 | 173915 ±10037 |
| 08-evaluator | claude-opus-4-8 | 3/3 | 3/3 | 73 ±8 | 0.29 ±0.03 | 10.0 ±0.0 | 5512 ±916 | 152863 ±2557 |
| 08-evaluator | claude-opus-5 | 3/3 | 3/3 | 167 ±23 | 0.61 ±0.02 | 13.0 ±0.0 | 13047 ±1349 | 246358 ±32222 |
| 08-evaluator | kimi-k3 | 3/3 | 3/3 | 174 ±36 | 0.72 ±0.07 | 11.0 ±0.0 | 4414 ±1179 | 215637 ±22259 |
| 08-evaluator-hard | claude-fable-5 | 3/3 | 3/3 | 100 ±15 | 0.71 ±0.10 | 9.3 ±0.6 | 6835 ±1529 | 184180 ±15489 |
| 08-evaluator-hard | claude-opus-4-8 | 3/3 | 3/3 | 100 ±24 | 0.37 ±0.07 | 10.0 ±0.0 | 8141 ±2126 | 160322 ±6735 |
| 08-evaluator-hard | claude-opus-5 | 3/3 | 3/3 | 174 ±30 | 0.64 ±0.16 | 13.3 ±2.1 | 13618 ±2448 | 277856 ±70607 |
| 08-evaluator-hard | kimi-k3 | 3/3 | 3/3 | 194 ±84 | 1.02 ±0.49 | 15.0 ±5.6 | 4890 ±1808 | 308907 ±172066 |

- **claude-fable-5**: 12/12 runs passed; per pass-through of all tasks: ~$1.94, ~325s wall
- **claude-opus-4-8**: 12/12 runs passed; per pass-through of all tasks: ~$1.28, ~342s wall
- **claude-opus-5**: 11/12 runs passed; per pass-through of all tasks: ~$2.09, ~557s wall
- **kimi-k3**: 12/12 runs passed; per pass-through of all tasks: ~$2.86, ~566s wall

- env: `2.1.214 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
