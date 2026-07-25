# 04-terminal walkthrough results

Corpus: 19 runs, 7 configurations, 5 models, 3 harnesses. All 19 scored 4/4.
Scorecard: 3/7 hypotheses hit.

- **H1: HIT** — 15/19 runs ran the checker >=5 times (threshold 15); cycles: {'2026-07-17-fable-sol-kimi/claude-fable-5/run-1': 6, '2026-07-17-fable-sol-kimi/claude-fable-5/run-2': 3, '2026-07-17-fable-sol-kimi/claude-fable-5/run-3': 6, '2026-07-17-fable-sol-kimi/gpt-5.6-sol/run-1': 6, '2026-07-17-fable-sol-kimi/gpt-5.6-sol/run-2': 3, '2026-07-17-fable-sol-kimi/gpt-5.6-sol/run-3': 6, '2026-07-17-fable-sol-kimi/kimi-k3/run-1': 6, '2026-07-17-fable-sol-kimi/kimi-k3/run-2': 6, '2026-07-17-fable-sol-kimi/kimi-k3/run-3': 5, '2026-07-17-sol-codex-homegame/gpt-5.6-sol-codex/run-1': 6, '2026-07-17-sol-codex-homegame/gpt-5.6-sol-codex/run-2': 5, '2026-07-17-sol-codex-homegame/gpt-5.6-sol-codex/run-3': 4, '2026-07-18-kimi-homegame/kimi-k3-kimicode/run-1': 7, '2026-07-18-kimi-homegame/kimi-k3-kimicode/run-2': 6, '2026-07-18-kimi-homegame/kimi-k3-kimicode/run-3': 5, '2026-07-20-glm52/glm-5.2/run-1': 6, '2026-07-20-glm52/glm-5.2/run-2': 5, '2026-07-20-glm52/glm-5.2/run-3': 6, '2026-07-20-glm52/claude-opus-4-8/run-1': 2}
- **H2: MISS** — proactive fix/scan in 10/19 runs (threshold <=3): ['claude-fable-5/run-2', 'gpt-5.6-sol/run-2', 'kimi-k3/run-3', 'gpt-5.6-sol-codex/run-1', 'gpt-5.6-sol-codex/run-2', 'gpt-5.6-sol-codex/run-3', 'kimi-k3-kimicode/run-1', 'kimi-k3-kimicode/run-2', 'kimi-k3-kimicode/run-3', 'claude-opus-4-8/run-1']
- **H3: HIT** — Sol median wall: Codex 39s vs CC 107s (ratio 0.36, need <=0.5); Kimi: Kimi Code 340s vs CC 119s (ratio 2.85, need >=2.5)
- **H4: MISS** — Kimi median checker cycles: Kimi Code 6 vs CC 6 (ratio 1.00, need >=1.5)
- **H5: HIT** — 19/19 SOLUTION.md accurate (threshold 16); not accurate: none
- **H6: MISS** — 9/19 first repo-touching call is the checker (threshold 17); exceptions: ['claude-fable-5/run-1: Bash: ls -la /tmp/arena-ws.CiEj7j', 'claude-fable-5/run-2: Bash: ls -la /tmp/arena-ws.p1AHud && cat /tmp/arena-ws.p1AHud/Makefile', 'claude-fable-5/run-3: Bash: ls -la /tmp/arena-ws.oG46ql && cat /tmp/arena-ws.oG46ql/Makefile', 'kimi-k3/run-1: Bash: ls -la /tmp/arena-ws.TJYP5u && cat /tmp/arena-ws.TJYP5u/Makefile 2>/dev/null', 'kimi-k3/run-2: Bash: ls -la /tmp/arena-ws.4etEFD && cat /tmp/arena-ws.4etEFD/Makefile 2>/dev/null', 'kimi-k3/run-3: Bash: ls -la /tmp/arena-ws.PJnKlo && cat /tmp/arena-ws.PJnKlo/Makefile 2>/dev/null', 'glm-5.2/run-1: Bash: ls -la && echo "---MAKEFILE---" && cat Makefile 2>/dev/null | head -100', 'glm-5.2/run-2: Bash: ls -la && echo "---MAKEFILE---" && cat Makefile 2>/dev/null', 'glm-5.2/run-3: Bash: ls -la', 'claude-opus-4-8/run-1: Bash: ls -la']
- **H7: MISS** — fix-file set == ['Makefile', 'data/config.json', 'scripts/run_checks.sh'] in 18/19 runs; deviations: ["kimi-k3-kimicode/run-3: ['Makefile', '_pytest', 'data/config.json', 'iniconfig', 'pluggy', 'py', 'pytest', 'scripts/run_checks.sh']"]

## Per-configuration medians

| configuration | wall s | checker cycles | tool events | task-mgmt | inter-event gap s |
| --- | --- | --- | --- | --- | --- |
| Fable 5 / Claude Code (n=3) | 80 | 6 | 15 | 0 | 63 |
| Sol / Claude Code (n=3) | 107 | 6 | 36 | 13 | 97 |
| Kimi K3 / Claude Code (n=3) | 119 | 6 | 13 | 0 | 97 |
| Sol / Codex (n=3) | 39 | 5 | 12 | 0 | n/a (no timestamps) |
| Kimi K3 / Kimi Code (n=3) | 340 | 6 | 30 | 0 | n/a (no timestamps) |
| GLM-5.2 / Claude Code (n=3) | 145 | 6 | 18 | 0 | 124 |
| Opus 4.8 / Claude Code (n=1) | 77 | 2 | 12 | 0 | 59 |

## The fifth fault nobody planted

The task plants four faults. The Kimi Code driver's isolated HOME (auth isolation, bouts/2026-07-18-kimi-homegame/DESIGN.md) drops ~/.local from python3's user site-packages, so `python3 -m pytest` fails with `No module named pytest` in that harness only. Cost, from the driver's timestamped wire.jsonl (time from the first pytest-missing error to the first green pytest run; the four planted faults were already fixed when this error can first appear, since pytest is last in the make chain):

- bouts/2026-07-18-kimi-homegame/04-terminal/kimi-k3-kimicode/run-1/transcript.jsonl: planted faults done by t+122s; fifth-fault segment 335s of 511s wall (65%); also explains this run's published peek-check warning (site-packages paths contain /home/mwoolly).
- bouts/2026-07-18-kimi-homegame/04-terminal/kimi-k3-kimicode/run-2/transcript.jsonl: planted faults done by t+82s; fifth-fault segment 154s of 304s wall (51%); also explains this run's published peek-check warning (site-packages paths contain /home/mwoolly).
- bouts/2026-07-18-kimi-homegame/04-terminal/kimi-k3-kimicode/run-3/transcript.jsonl: planted faults done by t+68s; fifth-fault segment 201s of 338s wall (60%); also explains this run's published peek-check warning (site-packages paths contain /home/mwoolly).

For comparison, the same model's full walls in Claude Code on this task (all four planted faults, no fifth): 136s, 119s, 102s.

## Fault discovery order (per run)

- Fable 5 / Claude Code run-1: cycles=6, order=['F1', 'F2', 'F3', 'F4'], proactive_candidates=4
- Fable 5 / Claude Code run-2: cycles=3, order=['F1', 'F3'], proactive_candidates=4
- Fable 5 / Claude Code run-3: cycles=6, order=['F1', 'F2', 'F3', 'F4'], proactive_candidates=2
- Sol / Claude Code run-1: cycles=6, order=['F1', 'F2', 'F3', 'F4'], proactive_candidates=2
- Sol / Claude Code run-2: cycles=3, order=['F1'], proactive_candidates=3
- Sol / Claude Code run-3: cycles=6, order=['F1', 'F2', 'F3', 'F4'], proactive_candidates=2
- Kimi K3 / Claude Code run-1: cycles=6, order=['F1', 'F2', 'F3', 'F4'], proactive_candidates=2
- Kimi K3 / Claude Code run-2: cycles=6, order=['F1', 'F2', 'F3', 'F4'], proactive_candidates=2
- Kimi K3 / Claude Code run-3: cycles=5, order=['F1', 'F2', 'F3'], proactive_candidates=3
- Sol / Codex run-1: cycles=6, order=['F1', 'F2', 'F3'], proactive_candidates=2
- Sol / Codex run-2: cycles=5, order=['F1', 'F2', 'F3'], proactive_candidates=2
- Sol / Codex run-3: cycles=4, order=['F1', 'F2'], proactive_candidates=2
- Kimi K3 / Kimi Code run-1: cycles=7, order=['F1', 'F2', 'F3', 'F5'], proactive_candidates=2
- Kimi K3 / Kimi Code run-2: cycles=6, order=['F1', 'F3', 'F5'], proactive_candidates=3
- Kimi K3 / Kimi Code run-3: cycles=5, order=['F1', 'F5'], proactive_candidates=3
- GLM-5.2 / Claude Code run-1: cycles=6, order=['F1', 'F2', 'F3', 'F4'], proactive_candidates=4
- GLM-5.2 / Claude Code run-2: cycles=5, order=['F1', 'F2', 'F3', 'F4'], proactive_candidates=3
- GLM-5.2 / Claude Code run-3: cycles=6, order=['F1', 'F2', 'F3', 'F4'], proactive_candidates=3
- Opus 4.8 / Claude Code run-1: cycles=2, order=['F1'], proactive_candidates=4
