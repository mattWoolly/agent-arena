# Mechanism-trace results

Corpus: 120 runs (72 Claude Code, 24 Codex, 24 Kimi Code).
Scorecard: 4/7 hypotheses hit.

- **H1: MISS** — 44/72 runs open with Bash (61%); threshold 80%
- **H2: MISS** — (a) TaskCreate-first in 15/24 Sol CC runs, task-mgmt 32% of its calls (thresholds 20, 25%); (b) planning calls/run: Codex 0.00 vs CC 7.8 (threshold <2)
- **H3: HIT** — 30/30 repair-task runs ran the checker before first tool-based modification (100%; threshold 90%); 4 runs had no tool-based modification (fixed via Bash), counted per pre-reg definition
- **H4: HIT** — re-read >=1 file: Sol 24/24 (>=16), Fable 0/24 (<=4); Kimi 0/24 for reference
- **H5: HIT** — Kimi lowest reads on 7/8 tasks (>=6, ties count); 7 passing code-task runs never Read a test file
- **H6: HIT** — Sol highest tool-call total on 8/8 tasks (threshold 7)
- **H7: MISS** — Fable median time-to-first-edit shorter on 3/8 tasks (threshold 7): {'01-bugfix': 'Fable 12s vs Sol 41s', '02-synthesis': 'Fable 22s vs Sol 18s', '03-refactor': 'Fable 13s vs Sol 46s', '04-terminal': 'Fable 35s vs Sol 42s', '05-review': 'n/a (a side has no tool-based modification)', '05-review-transplant': 'n/a (a side has no tool-based modification)', '06-instructions': 'n/a (a side has no tool-based modification)', '06-instructions-transplant': 'n/a (a side has no tool-based modification)'}

## Reads per task (Claude Code bout, sum over 3 runs)

| task | Fable 5 | Sol | Kimi K3 |
| --- | --- | --- | --- |
| 01-bugfix | 6 | 22 | 5 |
| 02-synthesis | 3 | 9 | 3 |
| 03-refactor | 18 | 40 | 20 |
| 04-terminal | 9 | 22 | 3 |
| 05-review | 12 | 18 | 12 |
| 05-review-transplant | 12 | 39 | 12 |
| 06-instructions | 0 | 8 | 0 |
| 06-instructions-transplant | 1 | 12 | 1 |

## Tool calls per task (Claude Code bout, sum over 3 runs)

| task | Fable 5 | Sol | Kimi K3 |
| --- | --- | --- | --- |
| 01-bugfix | 20 | 80 | 17 |
| 02-synthesis | 24 | 52 | 13 |
| 03-refactor | 36 | 96 | 40 |
| 04-terminal | 48 | 109 | 42 |
| 05-review | 21 | 27 | 19 |
| 05-review-transplant | 22 | 113 | 20 |
| 06-instructions | 13 | 46 | 15 |
| 06-instructions-transplant | 15 | 66 | 17 |

## First repo-touching call by task (Claude Code bout, 9 runs each)

- 01-bugfix: {'Bash': 9}
- 02-synthesis: {'Read': 9}
- 03-refactor: {'Bash': 9}
- 04-terminal: {'Bash': 9}
- 05-review: {'Read': 6, 'Bash': 3}
- 05-review-transplant: {'Read': 4, 'Bash': 4, 'Agent': 1}
- 06-instructions: {'Bash': 6, 'Read': 3}
- 06-instructions-transplant: {'Bash': 4, 'Read': 5}

## Notable runs

- bouts/2026-07-17-fable-sol-kimi/05-review-transplant/gpt-5.6-sol/run-2/transcript.jsonl: 97 calls including 4 Agent (subagent) spawns; counts {'TaskCreate': 3, 'TaskUpdate': 8, 'Agent': 4, 'Read': 27, 'Bash': 39, 'TaskList': 4, 'TaskGet': 3, 'TaskOutput': 1, 'SendMessage': 4, 'Write': 1, 'TaskStop': 3}

(runs at >=3x their cell mean: none)
