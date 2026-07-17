# Bout design: Fable 5 vs GPT-5.6 Sol vs Kimi K3 (pre-registered)

Committed before the first run. Hypotheses below are frozen; anything the
data does to them is reported, especially the misses.

## Question

When Fable 5 leaves the subscription plan, which cross-vendor challenger
replaces it in a Claude Code workflow? This measures the three models
as-you-can-actually-run-them in Claude Code today, not the models in the
abstract: Fable is native, Kimi K3 rides Moonshot's own Anthropic-compatible
endpoint, and GPT-5.6 Sol rides a local LiteLLM translation proxy. The
serving path is part of what's being bought, so it is part of what's
measured, and per-model differences in that path are disclosed, not hidden.

## Setup

- Models: `claude-fable-5` (native API), `kimi-k3` (api.moonshot.ai/anthropic,
  vendor shim), `gpt-5.6-sol` (LiteLLM 1.92.0 local proxy, config
  `env/litellm.gpt-5.6-sol.yaml`, per-request usage sidecar for true cost).
- Tasks: all eight (six core + two transplant variants), `-r 3 -s`
  (three repeats, strictly serialized, rotating model order).
- Effort pinned `xhigh` and recorded; Kimi and Sol likely ignore it (both
  reason by default). CLI version recorded per run.
- Run window: outside 12:00–18:00 Beijing time, so Kimi's serving is
  measured away from its launch-week afternoon peak.
- Judge: Opus 4.8, 3 samples, blind to model names, on the four rubric
  tasks. Unlike the previous bout, the judge is not a contestant.
- Cost sources: Fable CLI-priced; Kimi CLI-priced (near Moonshot's meter;
  cache asymmetry disclosed); Sol from `proxy_usage.jsonl`
  (LiteLLM `response_cost`, cache-aware, since the CLI cannot price it and
  the Anthropic-format translation drops cached-token counts).

## Hypotheses

- **H1 (correctness ties):** all three models pass 24/24 with full
  deterministic scores. The battery measures a floor; any miss by any model
  is the headline result.
- **H2 (wall-clock ordering):** per full pass-through, Fable < Sol < Kimi;
  point guesses Fable 550–700s, Sol 700–900s, Kimi 900–1200s.
- **H3 (cost):** with cache-aware pricing, Sol lands between $2.50 and
  $4.50 per pass-through: below Fable, above Kimi. Fable within ±20% of its
  measured $4.56, Kimi within ±20% of its measured $2.14.
- **H4 (judge stays flat):** total rubric spread across the three models is
  ≤4 points of 72, with every dimension except `interaction_synthesis` at
  full marks for all models.
- **H5 (transplant replication, second vendor):** the transplant prompt
  lifts Sol's 05-review `interaction_synthesis` medians relative to Sol's
  baseline-prompt runs, as it did for Opus, Fable, and Kimi.
- **H6 (retries):** zero API retries for Fable and Sol; Kimi at most 2
  retries total across its 24 runs in the off-peak window.
- **H7 (effort-shape convergence):** on 03-refactor, Sol's mean turn count
  is within ±3 turns of Fable's.
- **H8 (caching through the proxy):** at least 50% of Sol's input tokens
  bill at the cached rate across the bout, confirming OpenAI auto-caching
  functions at agentic cadence behind the translation layer.

## Disclosures pinned in advance

Home-field tooling (Claude Code) for one contestant; third-party translation
layer for Sol, so Sol tool-calling behavior is not attributable to the model
alone; effort-flag semantics differ per vendor; three different cache-billing
schemes; judge vendor is the harness vendor; Fable co-authors the harness
and the analysis; all Kimi cells are fresh runs in one window this time (the
published Kimi bout mixed launch-day and rerun cells for its clean numbers).

## Analysis plan

`summarize.py` table; per-model pass-through cost and wall sums; retry
counts extracted from transcripts; judge median table; H-by-H verdicts, each
marked hit or miss; comparison against the published Kimi bout with the
note that this bout's Kimi reliability numbers supersede launch-week ones.
