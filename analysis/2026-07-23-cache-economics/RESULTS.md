# Results: 2026-07-23-cache-economics

224 graded Claude Code harness runs across 9 arms (4 bout/model pairs are
Claude models, plus Sol, Kimi K3, GLM-5.2). All dollars recomputed from
per-run usage records at list prices; full table in economics.json.

## Hypothesis verdicts (misses first)

- **H4 MISS.** The premise was backwards: Kimi K3 is not the chatty one.
  GPT-5.6 Sol emitted 2.5x Kimi's output tokens per run (7,786 vs 3,112)
  in the same harness on the same tasks. Kimi's output dollars are lower
  ($0.047 vs $0.234 per run), but for two compounding reasons (fewer
  tokens AND half the output price), not the price-beats-verbosity trade
  the hypothesis proposed.
- **H1 PASS.** Cache reads are 87.1-93.6% of processed tokens in every
  arm, but under 50% of the dollar bill in 7 of 9 arms (as low as 25.9%
  for the Opus anchor).
- **H2 PASS.** Output is 1.1-3.3% of tokens in every arm yet over 30% of
  dollars in 7 of 9 arms (Opus anchor 47.6%, Fable 3way 44.2%, Opus
  ladder 42.2%, Sol 41.9%).
- **H3 PASS.** The effective input-side rate is 15.8-23.8% of the sticker
  input price in every arm. Agents pay roughly a fifth of sticker for
  context; sticker-price comparisons overstate real gaps.
- **H5 PASS.** Across all 24 Sol runs, the Claude Code CLI's own cost
  figure overstated the sidecar-recomputed true cost by a mean 309%
  (reported ~4.1x actual), because the Anthropic-format translation drops
  OpenAI's cached-token field (LiteLLM upstream issues 27763, 9812).

## Deviations from DESIGN.md

1. All Anthropic-format arms use the CLI's reconciled per-run aggregate
   instead of per-request transcript records: transcripts under-report
   output tokens (usage logs at message start), and Kimi's endpoint lumps
   the whole prompt into input_tokens per request. The aggregate equals
   the main model's modelUsage entry exactly. Sol keeps per-request
   sidecar records (needed for the long-context surcharge; none of the
   576 Sol requests crossed the 272K threshold).
2. Sub-cent haiku helper-model usage inside runs is excluded; the
   decomposition covers each arm's main model.
3. Sol's cache-write premium is not separable from OpenAI usage records;
   written tokens are billed at the plain input rate, understating Sol's
   input-side dollars by at most 25% of the written span.

## Secondary observation

The CLI's costUSD for Sonnet 5 in the 2026-07-07 bout reproduces exactly
at list prices ($3/$15), not the intro pricing in effect at the time; CLI
cost figures for Sonnet 5 during the intro window overstate the actual
invoice by roughly 1.4x.
