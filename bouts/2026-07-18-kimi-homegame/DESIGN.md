# Bout design: Kimi K3 under Kimi Code (its own CLI), pre-registered

Committed before the first graded run. The published three-way note ends by
saying we have no basis for assuming Kimi K3 wouldn't improve under its own
CLI the way GPT-5.6 Sol did under Codex. This bout tests that. Same eight
tasks, byte-identical PROMPT.md, same hidden graders, r=3; 24 new cells
compared against the published Claude Code cells. Nothing re-runs.

## Setup

- Model: `kimi-k3` via Kimi Code 0.27.0 (`kimi -p --output-format
  stream-json`; prompt mode auto-approves, the CLI's non-interactive parity
  for our other drivers' permission-bypass flags).
- Auth: isolated `HOME` at `.kimi-arena/` (gitignored) whose config points
  at Moonshot's metered platform API (`api.moonshot.ai/v1`), not the user's
  device-code subscription login. Thinking effort: the CLI's `max` default
  for K3, recorded per run.
- Cost: per-turn `usage.record` events from the session's `wire.jsonl`
  (inputOther / inputCacheRead / inputCacheCreation / output), priced at
  Moonshot list: $3 input, $15 output, $0.30 cache reads per million.
- Judge: Opus 4.8, 3 samples, blind, four rubric tasks. Standing
  disclosure: an Anthropic judge, and an Anthropic model co-authoring the
  harness and analysis.

## Baseline (published Claude Code cells being tested)

Kimi K3 in Claude Code: 24/24, $2.04 and 891s per pass-through, 13 tool
calls on 03-refactor, 33 whole-file Writes vs 10 in-place Edits across the
bout, fewest output tokens of the Claude Code configurations on seven of
eight tasks, judge 66/72.

## Hypotheses

- **H1 (grades don't move):** 24/24, full deterministic scores.
- **H2 (faster at home, less than Sol's factor):** pass-through wall
  500–800s. Sol's 3.6× came partly from shedding a translation proxy; Kimi's
  away runs had no proxy, so the harness effect should be smaller.
- **H3 (cheaper at home):** $1.00–2.50 per pass-through.
- **H4 (prompt-dominance holds):** judge total within ±4 of the away 66/72,
  and the transplant variant again lifts review interaction_synthesis
  relative to the plain prompt.
- **H5 (the rewrite habit is the model's):** whole-file writes exceed
  in-place edits in Kimi Code's tool logs too. This is the working-styles
  claim from the published note put at risk on purpose: Sol's turn-count
  style flipped with the harness, so styles may be harness artifacts. If
  the Write-over-Edit ratio also flips, the note's Kimi paragraph needs a
  correction.
- **H6 (clean serving):** zero API retries across 24 runs.
- **H7 (caching):** at least 50% of input tokens billed at the cached rate.

## Analysis plan

summarize.py table beside the published bouts; H-by-H verdicts, misses
reported first; tool-composition comparison across drivers; judge medians
against away medians; result feeds a follow-up note either confirming the
working-styles analysis cross-harness or correcting it.
