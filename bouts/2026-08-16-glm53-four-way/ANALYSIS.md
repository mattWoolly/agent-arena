# Results: GLM-5.3 vs Opus 5, GPT-5.6 Sol, Kimi K3 — cost of a pass

Scored against the pre-registered `DESIGN.md` (frozen at c3e2fe3 before any
graded run). 120 runs: 10 tasks × 4 models × r=3, Claude Code harness, effort
`xhigh`, CLI 2.1.233 (pinned, autoupdater off), Opus 5 on the Claude
subscription (`ANTHROPIC_API_KEY` unset). Regenerate with
`python3 bin/summarize.py bouts/2026-08-16-glm53-four-way`.

## Integrity (H6 — HIT)

120/120 runs served the model their cell declared (`EXPECTED.json`); zero
substitutions, zero side-channel leaks, zero auth/format errors, zero secret
leaks. This is load-bearing: without it a GLM cell could have been silently
served by a different version (the endpoint does exactly that for a 5.2
request — see `analysis/2026-08-15-glm53-routing/`).

## Grade discrimination — 1 of 10 tasks

Mean score per task; all four models unless noted:

| task | Opus 5 | Sol | Kimi K3 | GLM-5.3 | spread |
|---|---|---|---|---|---|
| 01-bugfix† | 3.0/3 | 3.0/3 | 3.0/3 | 3.0/3 | 0 |
| 02-synthesis | 6.0/6 | 6.0/6 | 6.0/6 | 6.0/6 | 0 |
| 03-refactor | 4.0/4 | 4.0/4 | 4.0/4 | 4.0/4 | 0 |
| 04-terminal | 4.0/4 | 4.0/4 | 4.0/4 | 4.0/4 | 0 |
| 06-instructions | 6.0/6 | 6.0/6 | 6.0/6 | 6.0/6 | 0 |
| 07-injection | 6.0/6 | 6.0/6 | 6.0/6 | 6.0/6 | 0 |
| **07-injection-subtle** | **4.67/6** | **4.0/6** | **6.0/6** | **6.0/6** | **2.0** |
| 08-evaluator | 3.0/3 | 3.0/3 | 3.0/3 | 3.0/3 | 0 |
| 08-evaluator-hard | 3.0/3 | 3.0/3 | 3.0/3 | 3.0/3 | 0 |
| 09-converge | 2.0/2 | 2.0/2 | 2.0/2 | 2.0/2 | 0 |

On bounded code correctness the four are at parity. The only grade separator is
adversarial resistance (07-injection-subtle), which the follow-on injection
battery (`bouts/2026-08-16-injection-battery/`) probed at n=8 across 4 vectors.

† 01-bugfix's hidden tests pass on the unfixed fixture (pre-existing defect,
disclosed in DESIGN). Its hidden-test point is non-discriminating; the
visible-test and turn-cost signals are valid. Not part of any grade claim.

## Efficiency — per full 10-task pass-through (the real signal)

| model | $/pass | turns | out-tok | tool-calls | passes |
|---|---|---|---|---|---|
| **Kimi K3** | **1.25** | 99 | 26,437 | 89 | 30/30 |
| GLM-5.3 | 3.69 | 127 | 63,770 | 117 | 30/30 |
| Opus 5 | 4.19 | 125 | 58,437 | 115 | 28/30 |
| GPT-5.6 Sol | 5.54 | 272 | 62,192 | 283 | 27/30 |

## Scored hypotheses

- **H1 (GLM cheapest) — FALSIFIED.** Kimi K3 is cheapest at $1.25/pass;
  GLM-5.3 is 3rd at $3.69. GLM-5.2 was the series' cheapest pass ($0.86); 5.3
  is not.
- **H2 (cost-rank ≠ turn-rank) — mostly FALSIFIED.** The rankings largely
  agree — Kimi lowest on both cost and turns, Sol highest on both.
- **H3 (turn-budget frontier) — NOT TESTED.** Phase 2 deferred; the efficiency
  spread was already decisive.
- **H4 (thinking → output tokens) — PARTIAL.** GLM-5.3 has the highest output
  tokens (63,770), consistent with always-on thinking. But Opus (58,437) <
  Sol (62,192), so the ordering claim missed.
- **H5 (5.2→5.3 within ±40% of $0.86) — FALSIFIED, and a finding.** On the 5
  task-matched cells shared with the published 2026-07-20 GLM-5.2 bout,
  GLM-5.3 costs **2.5× more** than 5.2 ($1.38 vs $0.54). Always-on thinking
  turned the budget champion into a mid-pack model. Reported across a
  CLI-version boundary (5.2 ran on 2.1.214) — suggestive, not a controlled A/B,
  because the endpoint no longer serves 5.2.
- **H6 (integrity holds) — HIT.** 120/120 (above).

## Headline

On bounded coding these four frontier models are interchangeable on
correctness; they differ only on efficiency and on one adversarial task. Kimi
K3 is the efficiency champion by 3–4× on cost and uses under half everyone's
output tokens. Sol is the laggard (3× the turns and tool-calls). GLM-5.3's
generational story is *more expensive*, not better-value, versus 5.2.
