# Excursion forensics results

Target: `bouts/2026-07-17-fable-sol-kimi/05-review-transplant/gpt-5.6-sol/run-2` (97 tool calls, 4 subagent spawns).
Scorecard: 5/6 hypotheses hit.

- **H1: MISS** — 6/6 lifetime pairs overlap (hit requires 0); spawns and completions in excursion.json
- **H2: HIT** — real cost $3.48 vs sibling median $0.34 (10.2x, threshold 5x); wall 829s vs 121s (6.9x, threshold 3x)
- **H3: HIT** — 3 cross-subagent disagreements adjudicated (hit requires >=1)
- **H4: HIT** — 3 subagent findings absent from final findings.md (hit requires >=1)
- **H5: HIT** — siblings at judge ceiling: True; findings count target 7 vs sibling max 7 (hit requires ceiling and target <= max)
- **H6: HIT** — src files: ['__init__.py', 'db.py', 'report.py', 'sync.py']; Read by main thread: ['__init__.py', 'db.py', 'report.py', 'sync.py']; not Read: [] (hit requires none missed)

## Panel timeline

- 2026-07-17T19:48:25.063Z -> 2026-07-17T19:51:27.952000+00:00 | Review diff for defects (model=opus, round 1)
- 2026-07-17T19:59:17.023Z -> 2026-07-17T20:00:03.513000+00:00 | Review diff for defects (model=opus, round 2)
- 2026-07-17T19:48:37.173Z -> 2026-07-17T19:50:18.754000+00:00 | Audit database invariants (model=sonnet, round 1)
- 2026-07-17T19:48:42.324Z -> 2026-07-17T19:52:12.123000+00:00 | Audit fetch and reporting (model=sonnet, round 1)
- 2026-07-17T19:59:19.007Z -> 2026-07-17T20:00:35.259000+00:00 | Audit fetch and reporting (model=sonnet, round 2)
- 2026-07-17T19:48:48.026Z -> 2026-07-17T19:49:11.995000+00:00 | Inspect tests for expectations (model=haiku, round 1)
- 2026-07-17T19:59:21.983Z -> 2026-07-17T19:59:24.883000+00:00 | Inspect tests for expectations (model=haiku, round 2)

## Cost table (real = metered proxy usage; cli = harness display)

| run | real $ | cli $ | wall s | calls | out-tok |
| --- | --- | --- | --- | --- | --- |
| 05-review-transplant/gpt-5.6-sol/run-2 | 3.4823 | 3.48 | 829 | 97 | 72830 |
| 05-review-transplant/gpt-5.6-sol/run-1 | 0.3391 | 0.34 | 117 | 8 | 5854 |
| 05-review-transplant/gpt-5.6-sol/run-3 | 0.3443 | 0.34 | 125 | 8 | 6447 |
| 05-review-transplant/claude-fable-5/run-1 | n/a (native) | 0.60 | 140 | 8 | 5213 |
| 05-review-transplant/claude-fable-5/run-2 | n/a (native) | 0.94 | 170 | 7 | 11397 |
| 05-review-transplant/claude-fable-5/run-3 | n/a (native) | 1.06 | 202 | 7 | 13389 |
| 05-review-transplant/kimi-k3/run-1 | n/a (native) | 0.21 | 59 | 6 | 1801 |
| 05-review-transplant/kimi-k3/run-2 | n/a (native) | 0.22 | 148 | 7 | 4583 |
| 05-review-transplant/kimi-k3/run-3 | n/a (native) | 0.27 | 159 | 7 | 5115 |
