# Reanalysis design: 2026-07-23-cache-economics (pre-registered)

Committed and pushed before any aggregate is computed. Hypotheses below are
fixed; deviations go in the ANALYSIS section of the output, not here.

## Question

Every vendor repriced the cache dimension this month: DeepSeek added 2x
peak-hour surge windows, OpenAI's GPT-5.6 line moved to 1.25x cache writes
with a 30-minute minimum cache life, and the Sonnet 5 tokenizer discourse
is at bottom an argument about effective (not sticker) pricing. Meanwhile
practitioner FinOps discourse prices agents off headline per-MTok rates.

From our public graded runs: what do agent bills actually consist of, per
vendor? Token composition vs dollar composition, the effective input rate
after cache discounts, whether chattiness (output volume) or cache
mechanics dominate the bill, and how big the LiteLLM cached-token
mistranslation was in our own records.

## Data (all committed in this repo; no new API calls)

Claude Code harness runs only, so the harness is held constant:

- `bouts/2026-07-07-ladder-noise`: claude-haiku-4-5, claude-sonnet-5,
  claude-opus-4-8, claude-fable-5; 30 runs each.
- `bouts/2026-07-17-fable-sol-kimi`: claude-fable-5, gpt-5.6-sol (LiteLLM
  proxy + usage sidecar), kimi-k3 (native Anthropic-compatible endpoint);
  Claude Code arms.
- `bouts/2026-07-20-glm52`: glm-5.2 and the claude-opus-4-8 anchor.

Sources per run: transcript.jsonl per-request usage records (Anthropic
accounting: input excludes cache reads and writes), committed proxy usage
records for the Sol arm, metrics.json, env/prices.json for non-Anthropic
list prices, and Anthropic list prices as published (Sonnet 5 intro $2/$10
noted separately where used).

Excluded: codex/kimi-code home-harness arms (different cache accounting
per harness would confound the vendor comparison) and the interrupted
2026-07-23-tokenizer-tax runs.

## Metrics

Per model arm: total tokens by class (uncached input, cache write, cache
read, output); dollars by class recomputed from per-request usage at list
prices; cache-read share of tokens and of dollars; effective input-side
rate = input-side dollars / input-side tokens, as a fraction of the
sticker input price; output tokens and output dollars per run.

Vendor accounting normalization (e.g. OpenAI reporting cached tokens as a
subset of prompt tokens vs Anthropic reporting them separately) is applied
explicitly in the analysis script and documented in its comments.

## Hypotheses (fixed before computing any aggregate)

- **H1:** Cache reads exceed 85% of total processed tokens in every arm,
  but are under 50% of the dollar bill in at least one arm.
- **H2:** Output tokens are under 5% of total tokens in every arm yet over
  30% of dollars in at least two arms.
- **H3:** The effective input-side rate is 12-25% of the sticker input
  price in every arm; sticker-price comparisons overstate the real gap
  between models.
- **H4:** Kimi K3 spends fewer output dollars per run than GPT-5.6 Sol in
  the same harness despite emitting more output tokens (the 2x output
  price gap outweighs the verbosity gap).
- **H5:** The Claude Code CLI's own cost figure for the proxied Sol arm
  (total_cost_usd_cli) overstates the recomputed true cost by more than
  25% on average across Sol runs, quantifying the LiteLLM cached-token
  translation bug (upstream issues 27763 and 9812) from our own records.

## Disclosures

- While checking field availability before writing this design, one run's
  metrics.json per arm was displayed (including its cost fields). No
  aggregate was computed before the hypotheses were fixed, but the single
  Sol run seen (01-bugfix run-1) showed a CLI/recomputed gap larger than
  H5's threshold; H5's 25% bar was kept as originally intended rather
  than tuned to that observation.
- Cache-share ballparks for GLM (93.4%), Kimi (~93%) and Sol (~95%) were
  already published in earlier notes; H1-H5 are chosen to go beyond those
  published figures, not to re-derive them.
- The analyst is Claude (Fable 5), one of the models being priced.
  Honest-reporting rules from the README apply; misses reported first.
- Zero new model spend: this is a pure reanalysis of committed artifacts.
