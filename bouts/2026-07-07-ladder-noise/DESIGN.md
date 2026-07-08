# Bout design: 2026-07-07-ladder-noise (pre-registered)

This file is committed **before** the first run. Hypotheses below are fixed;
any deviation from this design is recorded in ANALYSIS.md, not edited here.

## Question

Two questions, one dataset:

1. **Noise floor** — how much do wall-clock, cost, and grades vary between
   *identical* runs of the same model on the same task? Every future claim of
   the form "model A was faster/cheaper than model B" needs this error bar.
2. **The ladder** — walking down Anthropic's price ladder (Fable 5 → Opus 4.8
   → Sonnet 5 → Haiku 4.5), where is the cheapest rung that still passes all
   six graded tasks?

## Design

- **Tasks:** all six existing tasks (01-bugfix … 06-instructions), unchanged
  from the 2026-07-06 bout. Graders self-tested via `bin/check-graders.sh`
  (12/12) before the run.
- **Models:** `claude-haiku-4-5`, `claude-sonnet-5`, `claude-opus-4-8`,
  `claude-fable-5`.
- **Repeats:** 5 per (task, model) cell → 120 runs total.
- **Execution:** serial (`-s`) — one run at a time, so no two runs ever share
  rate-limit headroom; model order rotates each repeat so no model
  systematically goes first.
- **Command:** `bin/run-bout.sh -r 5 -s 2026-07-07-ladder-noise
  claude-haiku-4-5 claude-sonnet-5 claude-opus-4-8 claude-fable-5`
- **Hermetic config** (harness v2, branch point 27a528b): workspaces are
  `mktemp` dirs outside the repo; `--setting-sources project` (no user-level
  config); `--effort xhigh` pinned; CLI version and full config recorded per
  run in `run_env.json`; post-run peek check on every transcript.

## Disclosed asymmetries and conditions

- **Haiku 4.5 does not support the effort parameter** at the API level. The
  CLI accepts the flag without error; Haiku runs at its native default while
  the other three models run at pinned `xhigh`. This is unavoidable and
  disclosed rather than hidden.
- **Sonnet 5 is billed at introductory pricing** ($2/$10 per MTok through
  2026-08-31; list $3/$15). Measured costs reflect the intro price; the
  analysis will report both measured cost and list-price-normalized cost.
- List prices at design time (per MTok in/out): Haiku 4.5 $1/$5, Sonnet 5
  $3/$15 (intro $2/$10), Opus 4.8 $5/$25, Fable 5 $10/$50.
- Single machine, single API account, runs spread over ~2 hours of one
  afternoon — time-of-day load effects are not controlled beyond
  serialization and order rotation.
- The harness author and analyst is Claude (Fable 5), one of the models under
  test. Correctness graders are deterministic scripts; this disclosure
  continues the practice from the 2026-07-06 bout.

## Pre-registered hypotheses

- **H1 (noise):** between identical runs, wall-clock varies with sd/mean in
  the 10–30% range; cost varies less (5–15%); Opus 4.8 and Fable 5 pass 5/5
  on every task (grades are stable even when latency isn't).
- **H2 (Sonnet):** Sonnet 5 passes all six tasks in all repeats.
- **H3 (Haiku):** Haiku 4.5 fails at least one task at least once; most
  likely 02-synthesis (hidden performance gate) or 04-terminal (CRLF
  forensics).
- **H4 (cost):** measured cost ratios between models track list-price ratios
  to within ±25%, as they did in the 2026-07-06 bout (2.17× measured vs 2×
  list).
- **H5 (interpretation guardrail):** if every model passes everything, the
  correct conclusion is that these six tasks lack discriminative power at
  this difficulty — not that the models are equivalent. This was the main
  limitation of the 2026-07-06 bout and motivates the harder v2 tasks
  regardless of outcome.

## Analysis commitments

- Publish every raw artifact (transcripts, diffs, grades, metrics, run env).
- Report per-cell N (5) and mean ±sd, never bare means.
- Hand-verify every failed grade before reporting it as a model failure
  (rule out fixture/grader flakiness; grader bugs are reported as such).
- Report peek-check results for all 120 runs.
- ANALYSIS.md answers each hypothesis explicitly, including the misses.
