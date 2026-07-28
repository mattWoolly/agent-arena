# Bout results: 2026-07-27-k3-effort-dial

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 01-bugfix | kimi-k3-high-kimicode | 3/3 | 3/3 | 54 ±4 | 0.08 ±0.00 | 5.0 ±0.0 | 949 ±72 | 97877 ±1646 |
| 01-bugfix | kimi-k3-low-kimicode | 3/3 | 3/3 | 50 ±4 | 0.07 ±0.01 | 5.7 ±0.6 | 812 ±20 | 112981 ±12398 |
| 01-bugfix | kimi-k3-max-kimicode | 3/3 | 3/3 | 53 ±5 | 0.07 ±0.01 | 5.3 ±0.6 | 1013 ±38 | 110336 ±9755 |
| 02-synthesis | kimi-k3-high-kimicode | 3/3 | 6/6 | 156 ±40 | 0.16 ±0.04 | 9.3 ±3.8 | 3765 ±842 | 202581 ±90191 |
| 02-synthesis | kimi-k3-low-kimicode | 3/3 | 6/6 | 75 ±11 | 0.09 ±0.01 | 3.7 ±0.6 | 2038 ±123 | 67840 ±12643 |
| 02-synthesis | kimi-k3-max-kimicode | 3/3 | 6/6 | 170 ±40 | 0.14 ±0.03 | 8.0 ±3.6 | 4203 ±1012 | 175275 ±83852 |
| 03-refactor | kimi-k3-high-kimicode | 3/3 | 4/4 | 82 ±4 | 0.09 ±0.00 | 5.7 ±0.6 | 1363 ±56 | 113408 ±12859 |
| 03-refactor | kimi-k3-low-kimicode | 3/3 | 4/4 | 50 ±11 | 0.08 ±0.01 | 5.3 ±1.5 | 996 ±39 | 106837 ±36110 |
| 03-refactor | kimi-k3-max-kimicode | 3/3 | 4/4 | 81 ±8 | 0.10 ±0.01 | 7.0 ±0.0 | 1745 ±281 | 146347 ±4225 |
| 04-terminal | kimi-k3-high-kimicode | 3/3 | 4/4 | 87 ±10 | 0.12 ±0.01 | 9.7 ±1.5 | 1571 ±167 | 200192 ±32467 |
| 04-terminal | kimi-k3-low-kimicode | 3/3 | 4/4 | 87 ±8 | 0.13 ±0.00 | 12.0 ±1.0 | 1193 ±77 | 246187 ±22464 |
| 04-terminal | kimi-k3-max-kimicode | 3/3 | 4/4 | 123 ±42 | 0.16 ±0.04 | 13.0 ±5.0 | 2436 ±481 | 282880 ±114821 |
| 05-review | kimi-k3-high-kimicode | 3/3 | 6/6 | 77 ±8 | 0.08 ±0.00 | 3.3 ±0.6 | 1595 ±250 | 61184 ±11972 |
| 05-review | kimi-k3-low-kimicode | 3/3 | 6/6 | 49 ±9 | 0.07 ±0.01 | 3.3 ±0.6 | 942 ±133 | 61184 ±12643 |
| 05-review | kimi-k3-max-kimicode | 3/3 | 6/6 | 143 ±8 | 0.11 ±0.02 | 3.7 ±1.2 | 3503 ±416 | 71083 ±24906 |
| 06-instructions | kimi-k3-high-kimicode | 3/3 | 6/6 | 57 ±3 | 0.07 ±0.01 | 5.0 ±0.0 | 1252 ±130 | 101291 ±4362 |
| 06-instructions | kimi-k3-low-kimicode | 3/3 | 6/6 | 47 ±3 | 0.06 ±0.01 | 4.3 ±0.6 | 912 ±61 | 82859 ±11282 |
| 06-instructions | kimi-k3-max-kimicode | 3/3 | 6/6 | 118 ±33 | 0.11 ±0.01 | 5.0 ±0.0 | 3250 ±644 | 102059 ±4832 |

- **kimi-k3-high-kimicode**: 18/18 runs passed; per pass-through of all tasks: ~$0.59, ~512s wall
- **kimi-k3-low-kimicode**: 18/18 runs passed; per pass-through of all tasks: ~$0.50, ~358s wall
- **kimi-k3-max-kimicode**: 18/18 runs passed; per pass-through of all tasks: ~$0.69, ~688s wall

- env: `kimi-code 0.27.0`, effort=`high`, setting-sources=`arena config.toml only`
- env: `kimi-code 0.27.0`, effort=`low`, setting-sources=`arena config.toml only`
- env: `kimi-code 0.27.0`, effort=`max`, setting-sources=`arena config.toml only`
