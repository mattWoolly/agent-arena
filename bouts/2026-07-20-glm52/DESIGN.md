# Bout design: GLM-5.2 under Claude Code, the guest that trained for the home harness (pre-registered)

Committed and pushed before the first graded run. Hypotheses are frozen;
anything the data does to them is reported, misses first.

## Question

Z.ai ships GLM-5.2 with an Anthropic-compatible gateway and markets Claude
Code as a first-class way to run it. That makes it a new case for this
series' harness-pairing storyline: not a model dragged into Claude Code
through a translation proxy (Sol), and not a vendor shim added after launch
(Kimi K3), but an open-weight model whose vendor chose the rival's harness
as a primary serving surface. If "built to slot into Claude Code" is real,
it should show up in the tool grammar, the cache economics, and the bill,
not just the marketing page. This bout measures that against the published
07-16/07-17 cells.

## Setup

- Model: `glm-5.2` via Z.ai's Anthropic-compatible endpoint
  (`https://api.z.ai/api/anthropic`), env file `env/glm-5.2.env` per the
  README convention (all internal model slots pinned to `glm-5.2`). No
  proxy, no translation layer. Endpoint verified live 2026-07-20 with a
  one-shot Messages ping; usage envelope includes
  `cache_read_input_tokens`.
- Anchor arm: `claude-opus-4-8`, all eight tasks, r=1, same session. The
  published comparison cells ran on Claude Code 2.1.212; today's CLI is
  newer. The anchor turns CLI drift from a disclosure into a measurement.
- Tasks: all eight (six core + two transplant variants), `-r 3 -s` for
  GLM (24 runs, strictly serialized; wall-clock is a claim), `-r 1 -s`
  for the anchor (8 runs).
- Effort pinned `xhigh` (recorded per run). Whether Z.ai's gateway maps
  effort to anything is unknown and disclosed as such.
- Run window: outside 12:00-18:00 Beijing (run starts ~20:15 Beijing).
- Judge: Opus 4.8, 3 samples, blind, on the four rubric tasks, GLM cells
  only (published judge baselines cover the incumbents). Standing
  disclosures apply: the judge is an Anthropic model, Claude Code is
  Anthropic's harness (home field for Anthropic models), and Fable 5
  co-authors the harness and the analysis.
- Cost: `metrics.py` reprices from transcript usage via `env/prices.json`
  (Z.ai list, primary source docs.z.ai pricing page, 2026-07-20: $1.40 in,
  $4.40 out, $0.26 cache read per 1M; no cache-write charge, storage
  "limited-time free" as of today). CLI figure preserved as
  `total_cost_usd_cli`.

## Published baselines under test (Claude Code cells, CLI 2.1.212)

- Kimi K3: 24/24, ~$2.04 and ~891s per pass-through, judge 66/72,
  33 whole-file Writes vs 10 in-place Edits across its bout.
- Fable 5: 24/24, ~$4.62, ~690s. Opus 4.8 (07-16 bout): 24/24, ~$2.27,
  ~621s per pass-through.
- Mechanism markers (analysis/2026-07-19-mechanism-trace, same analyze.py
  definitions reused verbatim): re-read of an already-open file, Sol 24/24
  runs vs Fable 0/24 and Kimi 0/24; task-management calls, Sol ~7.8/run vs
  near zero for Fable and Kimi.

## Hypotheses (frozen)

- **H1 (the ceiling holds):** GLM-5.2 passes 24/24 with full deterministic
  scores. The battery has an all-pass ceiling for frontier-class models;
  a failure anywhere is the bigger story and gets reported as such.
- **H2 (cheapest seat in the house):** per pass-through cost below Kimi's
  $2.04; predicted range $0.90-1.60. Open-weight list prices plus working
  cache reads should make GLM the cheapest Claude Code configuration
  published in this series.
- **H3 (the Pacific tax):** per pass-through wall between 800 and 1100s,
  i.e. Kimi-like, slower than the Anthropic natives, cross-Pacific serving
  being part of what you buy.
- **H4 (trained for the house grammar):** three pre-registered markers,
  computed with the mechanism-trace analyze.py, GLM vs published cells:
  - (a) re-reads an already-open file in at most 4 of 24 runs
    (native-style economy; Sol did it in 24/24);
  - (b) in-place Edit calls >= whole-file Write calls across the bout
    (Kimi, the other open-weight, went 33 Writes to 10 Edits; if GLM
    shares the rewrite habit despite the Claude Code tuning, this misses);
  - (c) fewer than 2 task-management calls per run on average
    (Sol-in-Claude-Code averaged 7.8).
- **H5 (the cache is real):** at least 50% of GLM's billed input tokens
  price at the cache-read rate across the bout. If Z.ai's cache does not
  hold under Claude Code's incremental-context pattern, the $1.40 sticker
  is fiction and the effective bill says so.
- **H6 (month-two serving is clean):** zero 429/5xx retries across the 24
  GLM runs (contrast: Kimi's launch-day 429 cells).
- **H7 (anchor stability):** Opus 4.8 anchor passes 8/8 and lands within
  $1.60-3.00 per pass-through (published $2.27). If the anchor drifts,
  every new-vs-published comparison in this bout gets the drift caveat in
  print.
- **H8 (depth is average, not native):** GLM judge total on the four
  rubric tasks within +/-6 of Kimi's 66/72, i.e. 60-72 of 72.

## Budget

Estimate: GLM arm ~$3-5 (24 runs at roughly half Kimi token rates), anchor
~$2.30, judge ~$1-3. Ceiling ~$10, inside the pipeline's $25 target. Actual
spend recorded in the results and pipeline state.

## Protocol notes

- Smoke one cell (01-bugfix, r=1) after this file is pushed, before the
  full grid. Smoke stays in `bouts/glm52-smoke` per house convention.
- Serial mode throughout; leak scan before every push; peek_check must be
  clean on all published runs (the auth token lives in the agent's
  environment on native-endpoint runs, same exposure class as Kimi K3).
- If Z.ai serving fails hard (H6 catastrophically wrong), stop the grid,
  publish what ran with the failure documented, and fall back to the
  zero-spend cache-economics candidate for the article.
