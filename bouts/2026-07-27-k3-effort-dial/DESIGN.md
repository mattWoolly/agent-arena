# Bout design: Kimi K3 effort dial (pre-registered)

Committed and pushed before any graded run. Written 2026-07-27, K3
open-weights day. Whatever the data does to the hypotheses is reported,
misses first.

## Question

Three sources disagree about K3's reasoning-effort surface. Moonshot's
launch blog (2026-07-16) says "K3 currently accepts only maximum reasoning
effort." Kimi Code 0.29.0 (2026-07-22) shipped a selectable thinking-effort
picker. The CLI's own model catalog declares `support_efforts =
["low", "high", "max"]` for `kimi-k3`, and Moonshot's Anthropic-compatible
surface documents `output_config.effort`. Yesterday this series published
what Opus 5's effort dial does (moved the bill, not the grades). Today's
question: what does K3's dial do, and is it connected to anything?

Both resolutions are findings. A working dial gives the challenger's
effort curve next to Opus 5's published one. A decorative dial means the
ecosystem shipped effort UI the API ignores, measurable as unchanged
reasoning volume across requested efforts.

## Context constraint, disclosed up front

The queued cross-vendor serving bout (same weights, different servers) is
not runnable today: Moonshot is the only live K3 server (Together "coming
soon" per their own page, Fireworks catalog tops out at K2.7, Groq absent,
Baseten waitlisted; OpenRouter/Vercel resell Moonshot's endpoint), the
HF weights repo (`moonshotai/Kimi-K3-MXFP4`) is gated, and this pipeline
holds no third-party serving keys. Single-vendor bout; the cross-vendor
question stays open and is named in the article as future work.

## Instruments (validated before graded runs)

- Requested effort is PROVEN per request, not assumed: Kimi Code's session
  `wire.jsonl` records `thinkingEffort` on every `llm.request` event.
  Verified on 2026-07-18 homegame artifacts (all requests carry
  `"thinkingEffort": "max"`).
- Reasoning volume is measured, not inferred: `wire.jsonl`
  `context.append_loop_event` events carry `part.type == "think"` with the
  full thinking text; per-run thinking characters are extractable.
- Effort selection mechanism: per-alias `default_effort` in the isolated
  arena `config.toml` (aliases `arena/k3-low`, `arena/k3-high`,
  `arena/k3-max`, same provider, same model ID). CLI pinned at kimi-code
  0.27.0, the version of every prior Kimi bout; the 0.29.0 change is a
  UI-level picker for the same config surface, and comparability with the
  7/18 baseline outranks version freshness. Confirm at smoke that
  `default_effort` flows through to `llm.request.thinkingEffort`.
- Pre-grid API probes (ungraded, logged to `probes/`): send minimal
  requests to Moonshot's OpenAI-compatible and Anthropic-compatible
  surfaces requesting each effort value; record acceptance, rejection, or
  silent-clamp signals. These establish whether the API even admits the
  parameter before we measure whether it honors it.
- Harness extensions shipped as permanent tools with this bout:
  `run-task-kimi.sh` gains `ARENA_KIMI_LABEL` (cell label override,
  leakscan falls back to the base `kimi-k3-kimicode` scan file) and
  records the alias's requested effort in `run_env.json`;
  `metrics_kimi.py` gains an optional price-key argument plus two new
  metric keys: `thinking_chars` and `requested_efforts` (the set observed
  across the run's `llm.request` events). README coverage included.

## Grid (est. $9-12; target ≤$25, hard cap $50)

1. **Effort ladder:** kimi-k3 at low / high / max on the 6 base tasks
   (01-bugfix, 02-synthesis, 03-refactor, 04-terminal, 05-review,
   06-instructions), r=3, serial (`-s`; execution time is a claim), cells
   labeled `kimi-k3-<effort>-kimicode`. 54 graded runs. Order rotates
   effort arms per task so no arm systematically inherits a warm or cold
   serving window.
2. **Judge pass:** Opus 4.8, blind, 3 samples, on the rubric tasks
   (05-review, 06-instructions) across all three efforts (18 runs judged).
   Depth-versus-effort is where the Opus 5 article found its second story;
   same instrument, same disclosure (Anthropic model judging a rival's
   output; judge never sees model names or efforts).
3. **Smoke first:** one 01-bugfix cell at low effort before anything else.
   It validates the effort plumbing end-to-end AND is the first live cell
   of the merged Kimi HOME fix (arena PR 21) — watch `peek_check` and
   pytest behavior. A broken smoke stops the bout before money is spent.
4. **No new-model anchors.** Opus 5 effort-ladder rows and the 7/18
   homegame max-effort rows are the published comparators. Fresh anchors
   are not bought because cost rows are token-metered (stable across
   windows per the noise-floor finding) and no cross-model execution-time
   claim will be made from stale stopwatches.

Timing: runs start after 10:00 UTC (outside Moonshot's 12:00-18:00
Beijing peak window; it is ~20:00 Beijing at design time).

## Hypotheses

- **H1 (the dial is connected):** median per-run thinking characters at
  requested low are at most half the max-arm median on at least 4 of 6
  tasks. The miss — all arms statistically indistinguishable — is the
  "decorative dial" finding and would lead the article.
- **H2 (grades hold at every effort):** 54/54 deterministic passes. The
  interesting miss is any low-effort failure: the first time this battery
  un-saturates for a non-Claude model, making effort the price of
  correctness.
- **H3 (the bill moves monotonically):** per-pass cost and output tokens
  order low < high < max on at least 5 of 6 tasks. (If H1 misses, H3 is
  expected to miss with it; that co-miss is the story's spine.)
- **H4 (the verbosity claim, contextualized):** Artificial Analysis
  measured K3 burning roughly twice the output tokens of same-tier models
  across their suite. Prediction: at max effort K3's per-pass output
  tokens are at least 1.5x Opus 5's published default-effort figure on
  this battery; at low effort the gap halves. Either way the series gets
  its own number for the discourse claim.
- **H5 (HOME fix holds under fire):** zero peek-check flags and zero
  unplanted pytest faults across all 54 runs; 04-terminal mean execution
  time re-baselines below the contaminated 7/18 figure (386s ±111, which
  included fifth-fault recovery time in 9/24 runs).
- **H6 (weights-day serving):** per-run error/retry incidence recorded;
  contrast with the 7/16 API-launch-day 429 log already on record. A
  quiet weights day versus a noisy API-launch day is a sentence worth
  having either way.
- **H7 (depth is effort-insensitive):** judge medians on 05-review and
  06-instructions at low within 1 point of max. The miss — low effort
  buys shallower judged work even while grades hold — mirrors the Opus 5
  second-story structure and would co-lead the article.

## Disclosures pinned in advance

Home field reversed: K3 runs in its own vendor's CLI (Kimi Code), the
harness-pairing effect has a sign and it favors the home team here. Judge
is Opus 4.8, an Anthropic model, scoring a rival vendor's output (blind).
Fable co-authors the harness and the article. Sampling is fixed by the
vendor (temperature 1.0, top_p 1.0) so arms differ only in requested
effort. Effort semantics are vendor-defined and recorded verbatim, never
assumed. The 7/18 homegame 04-terminal rows are known-contaminated by the
harness's own fifth fault (disclosed and quantified in the published
walkthrough note); this bout re-baselines that cell post-fix. Single
vendor serving; nothing here measures the open weights themselves.

## Analysis plan

summarize.py rows merged across the three arms plus published Opus 5 and
homegame baselines; effort table (thinking chars, output tokens, cost,
execution time, grades per effort per task); H-by-H verdicts, misses
first; judge medians table for the rubric tasks; step-3.5 claims mapping
(launch blog "only max," CLI picker, AA verbosity number) with any
second-order arms run as amendments to this design, in the open. Spend
logged to pipeline state.json regardless of outcome.
