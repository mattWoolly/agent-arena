# Bout results: 2026-08-21-verification-vs-effort-xhigh

| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |
|---|---|---|---|---|---|---|---|---|
| 16-source-audit | claude-sonnet-5 | 10/10 | 3/3 | 74 ±18 | 0.20 ±0.04 | 8.7 ±0.8 | 7710 ±2117 | 202048 ±36749 |
| 16-source-audit-verify | claude-sonnet-5 | 10/10 | 3/3 | 88 ±11 | 0.22 ±0.02 | 9.1 ±0.9 | 9062 ±1325 | 215006 ±32884 |

- **claude-sonnet-5**: 20/20 runs passed; per pass-through of all tasks: ~$0.41, ~162s wall

- served-model check: OK, all runs matched EXPECTED.json (served: claude-sonnet-5)

- env: `2.1.239 (Claude Code)`, effort=`xhigh`, setting-sources=`project`
