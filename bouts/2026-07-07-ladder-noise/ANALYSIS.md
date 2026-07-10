# Bout analysis: ladder + noise floor — 2026-07-07

Design and hypotheses were pre-registered in [DESIGN.md](DESIGN.md), committed
at `73cd1a2` before the first run. 120 runs: 4 models × 6 tasks × 5 repeats,
serial, rotating model order, hermetic harness v2 (workspaces outside the
repo, `--effort xhigh` pinned, `--setting-sources project`, per-run
`run_env.json`). All numbers below computed from `results.json`; verification
steps are recorded in the last section.

## Headline results

| Model | Runs passed | Cost per pass-through | Wall per pass-through |
|---|---|---|---|
| claude-haiku-4-5 | 28/30 | $0.35 | 196s |
| claude-sonnet-5 | 30/30 | $1.30 measured / ≈$1.94 at list price | 328s |
| claude-opus-4-8 | 30/30 | $1.72 | 482s |
| claude-fable-5 | 30/30 | $3.13 | 430s |

Cost per pass-through = sum of per-task mean costs (repeats don't inflate it).
Sonnet 5 was billed at introductory pricing ($2/$10 per MTok through
2026-08-31); the list-normalized figure multiplies by exactly 1.5 (every token
class — input, output, cache read/write — scales uniformly with the $3/$15
list rate).

Three findings stand out:

1. **The 2026-07-06 speed claim did not replicate.** The published bout
   (N=1 per cell, pairwise-concurrent runs) found Opus 4.8 "faster on every
   single task." Under N=5 serialized runs: Opus faster on two tasks (01, 03,
   both by 19%), ties on two (04, 05), and Fable faster on two (02 by 26%,
   06 by 41%). Summed, Fable's pass-through is now *faster* than Opus's
   (430s vs 482s). The correct reading of both bouts together: per-task
   wall-clock differences between these two models are mostly within noise,
   and the original speed ordering was an artifact of single runs.
2. **The ladder folds at list price.** At intro pricing Sonnet 5 is cheaper
   than Opus 4.8 ($1.30 vs $1.72) with all 30 runs passing. At list price
   (≈$1.94) Sonnet would cost *more* than Opus on this workload — it consumes
   substantially more tokens per task (higher turn counts and roughly 1.5–2×
   the cache reads in most cells, consistent with its new tokenizer and more
   tool-eager style). "Mid-tier is cheaper" is a pricing-page intuition that
   the meter doesn't necessarily confirm.
3. **Haiku's failure mode is diligence, not capability.** Its only failures
   (06-instructions runs 1–2, score 4/6) produced *different wrong totals
   each time* — $6,618.09 and $5,288.55 against a truth of $7,154.44. The
   tool logs show why: the two failing runs used only Read+Write (arithmetic
   done "in its head"); the three passing runs used Bash to compute. Haiku
   can do the task — it doesn't reliably choose to.

## Hypothesis verdicts

- **H1 (noise) — partially wrong.** Wall-clock sd/mean per cell ranged
  5%–46% with a median of 13% — wider on both ends than the pre-registered
  10–30% band. Cost variance was mostly small as predicted, with exceptions
  (06/Opus: $0.29 ±0.10, 34%). Grades for Opus and Fable were stable at 30/30
  as predicted. Practical consequence: single-run latency comparisons under
  ~50% are not evidence; even five runs leave wide intervals on the noisiest
  cells (05/Opus: 97 ±44s).
- **H2 (Sonnet) — confirmed.** 30/30, every score at maximum.
- **H3 (Haiku) — confirmed in category, wrong on specifics.** It failed a
  task, but not the predicted ones (02's perf gate and 04's CRLF forensics
  both passed 5/5); the break was 06's exact-figures contract, and only when
  it skipped computation. It also failed *inconsistently* (2 of 5), which is
  worse for production use than a reliable break: a flaky rung can pass your
  eval and fail in the field.
- **H4 (cost tracks list price) — confirmed for Fable/Opus.** Measured ratio
  1.82× vs 2× list (within the pre-registered ±25%). The Sonnet result above
  is the interesting corollary: list-price ratios only predict cost ratios
  when token appetite is comparable, and Sonnet's isn't.
- **H5 (interpretation guardrail) — stands.** Three of four models were at
  ceiling on all six tasks. These tasks discriminate at the Haiku/Sonnet
  boundary and are blind above it. Harder v2 tasks remain necessary before
  any "Opus ≈ Fable" claim means more than "both clear a low bar."

## Deviations from the pre-registered design

1. **The Claude Code CLI auto-updated mid-bout** (2.1.202 → 2.1.203),
   affecting the last 17 of 120 runs — all within the 06-instructions group
   (the final task group executed). Within that group all four models ran
   mostly on 2.1.203, so within-task comparisons stay matched; Haiku's two
   failures span both versions (run-1 on .202, run-2 on .203), so the failure
   is not version-specific. Recorded per-run in `run_env.json`. Future bouts
   should pin the CLI version or disable auto-update for the duration.
2. None otherwise; the run command, repeats, and ordering matched DESIGN.md.

## Comparability caveat vs the 2026-07-06 bout

The published bout ran harness v1: workspaces inside the repo, no effort or
setting-source pinning (runs inherited this machine's user-level Claude
config), models run pairwise-concurrent. This bout is hermetic and serial.
Opus's wall-clock is notably higher here than in the v1 bout on three tasks
(02: 118s vs 67s; 05: 97s vs 38s; 06: 91s vs 44s) while Fable's total barely
moved (430s vs 434s). We cannot fully attribute that gap (config bleed,
API-side load, model-side drift, and N=1 luck are all candidates); it is
another reason the original speed ordering should not be cited without error
bars.

## Verification record

- Grader self-test before the run: `bin/check-graders.sh` 12/12.
- Both Haiku failures hand-verified: grader truth recomputed from the CSV;
  the submitted `summary.json` values quoted above are from the run
  workspaces; tool-call profiles read from `metrics.json` (failing runs:
  Read+Write only; passing runs: Bash present).
- Peek check: 120/120 runs `clean` (no transcript references the arena tree
  or grader assets).
- Aggregates in this file were computed by script from `results.json`
  (per-task means, sd/mean distribution, ratios) — not transcribed by hand.
- Analyst disclosure: this analysis was written by Claude (Fable 5), one of
  the models under test, from deterministic grader output and committed
  artifacts. Every raw artifact needed to check any claim is in this
  directory.
