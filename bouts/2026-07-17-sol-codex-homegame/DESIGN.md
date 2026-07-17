# Bout design: GPT-5.6 Sol's home game (Codex driver), pre-registered

Committed before the first graded run. This bout answers the objection the
away-game bout earned: Sol's numbers all came from inside Claude Code,
through a translation proxy, against a competitor's tooling. Here the same
model runs the same eight tasks driven by its own vendor's CLI (codex exec),
native API, no proxy. Nothing else re-runs: the graders only ever see the
finished workspace, so these 24 new cells compare directly against the
published away-game cells.

## Setup

- Model: `gpt-5.6-sol` under codex-cli 0.144.4 (`codex exec --json`,
  workspace-write sandbox with approvals bypassed, the parity choice for
  Claude Code's `--dangerously-skip-permissions`), isolated API-key
  CODEX_HOME, `--ignore-user-config`.
- Tasks: all eight, byte-identical PROMPT.md, same hidden graders, r=3,
  serial. Judge: Opus 4.8 on the four rubric tasks, blind, 3 samples
  (disclosure stands: an Anthropic judge scoring an OpenAI model's prose).
- Cost: computed from codex's per-turn usage events (it reports
  `cached_input_tokens` natively) against `env/prices.json`.
- Semantics caveat, pinned now: codex "turns" are whole prompt→completion
  cycles, not assistant messages, so cross-driver effort shape is compared
  on tool calls, token volumes, wall clock, and cost, never on turn counts.

## Baseline (published away-game numbers being tested)

Sol under Claude Code: 24/24, $4.46 and 1085s per pass-through, ~32 tool
calls on 03-refactor (Fable 12, Kimi 13), 9.7M input tokens at 93% cached,
judge 60/72 with quantification 1/1/1 and baseline interaction_synthesis
1/0/0.

## Hypotheses

- **H1 (grades don't move):** 24/24, full deterministic scores. Capability
  floor is harness-independent.
- **H2 (the driving style is the model's, not the harness's):** Sol under
  Codex still makes at least 2× Fable's away-game tool calls on 03-refactor
  (i.e. ≥24 against Fable's 12).
- **H3 (home is faster):** pass-through wall under 1085s; point guess
  700–950s.
- **H4 (cost roughly holds):** $3.10–5.80 per pass-through (±30% of the
  away game's $4.46); codex's heavier system context offset by native
  caching.
- **H5 (prompt-dominance, the load-bearing call):** the judge total moves
  by at most 4 points from the away game's 60/72. The transplant experiment
  says depth lives in the prompt, not the harness; if home-field tooling
  rescues Sol's depth scores, this hypothesis dies and the away-game
  article's fairness is materially weakened. We would rather learn that
  before publishing than after.
- **H6 (clean serving):** zero API retries across 24 runs.
- **H7 (native caching):** at least 60% of input tokens cached.

## Analysis plan

summarize.py table merging the codex cells with the away-game bout for
side-by-side reading; H-by-H verdicts, hits and misses both reported; judge
medians per dimension against the away-game medians; the result feeds the
"Sol's weakness" article either as its strongest caveat resolved or as its
correction.
