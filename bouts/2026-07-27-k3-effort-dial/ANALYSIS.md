# Analysis: 2026-07-27 K3 effort-dial bout

Grid ran 2026-07-27 (12:14-13:52 UTC, serial, kimi-code 0.27.0, Moonshot
platform API). 54 graded runs: 3 efforts x 6 base tasks x r3. $5.34 metered.
Judge pass (Opus 4.8, blind, 3 samples, rubric tasks) ran 2026-07-28.
Full rows in results.md; per-run artifacts under each task directory.

## Correction to the pre-registration, on the record

DESIGN.md quotes Moonshot's launch blog as saying K3 "currently accepts
only maximum reasoning effort." That is a misquote, found during claims
review (step 3.5) against the Wayback Machine launch-day snapshot
(web/20260716190336/https://www.kimi.com/blog/kimi-k3). The blog has said
since day one: "At launch, Kimi K3 will use max thinking effort by default,
with low- and high-effort modes to be introduced in subsequent updates."
Never "only"; never edited. The low/high tiers went live around 7/18
(platform docs now document `reasoning_effort: low|high|max`, default max).
The bout's question ("is the dial connected, and what does it price") and
all seven hypotheses are unaffected; the "vendor denies the dial" framing
available from the misquote is dead and is not used. Precedent for carrying
a correction openly: the 7/25 amendment-provenance disclosure.

## Hypothesis verdicts (misses first)

- **H3 MISS (bill monotonicity): cost ordered low < high < max on only 4/6
  tasks** (fails 01-bugfix: max median $0.062 vs low $0.075; 02-synthesis:
  high $0.161 vs max $0.124). Output tokens ordered 6/6. The pre-registered
  bar was 5/6 on both. Mechanism, from the cost anatomy: per-run input
  traffic (100k-300k tokens, dominated by cache reads) dwarfs output
  (1-5k), so the bill tracks turn count, not requested effort; the
  off-order cells are exactly the ones where a higher-effort arm took
  fewer turns. On agentic work the dial does not govern the thing that
  costs money.
- **H4 MISS, inverted (the verbosity claim):** prediction was K3-max
  >= 1.5x Opus 5's published default-effort output tokens; measured is
  ~0.37x (7.3k vs 19.7k on the three ladder-comparable tasks, per-task
  medians vs the published Opus 5 ladder row). K3 at max effort is the
  TERSER model on this battery. Artificial Analysis's suite-level ~2x
  token-burn figure does not transfer to agentic coding work, where
  completion tokens are a small fraction of traffic. K3 is heavy in
  thinking (see H1) and light in completion.
- **H1 HIT (the dial is connected), 6/6 tasks** (bar was 4/6): median
  per-run thinking chars, low vs max: 01-bugfix 110→470, 02-synthesis
  467→5732, 03-refactor 15→550, 04-terminal 283→2280, 05-review
  983→12367, 06-instructions 142→5628. Pooled per full pass: 6.6k → 20.8k
  → 80.0k chars (12.1x low→max). Every one of the 54 runs' wire logs
  carries the requested effort on every llm.request event
  (requested_efforts == [arm effort], 54/54; instruments shipped in
  e86f51a).
- **H2 HIT: 54/54 passes, full deterministic scores at every effort.**
  The battery stays saturated for K3 at low; effort is not the price of
  correctness here (same shape as the published Opus 5 result).
- **H5 HIT (HOME fix holds): peek_check clean 54/54, zero unplanted pytest
  faults.** 04-terminal re-baselines at 87 ±8s (low), 87 ±10s (high),
  123 ±42s (max) vs the contaminated 7/18 figure of 386 ±111s that
  included fifth-fault recovery in 9/24 runs. The 7/18 04-terminal rows
  are retired as a baseline.
- **H6 (weights-day serving): zero 429s, retries, or error events across
  54 runs and ~104 minutes of serial traffic** (grep of all stderr.log and
  wire.jsonl). Contrast on record: the 7/16 API-launch-day bout logged
  429 pressure. A quiet weights day; also note the serving field opened
  within 24h (AA tracked 8 live providers by 7/28).
- **H7 (depth vs effort): see judge table below.**

## The smoke run that justified the instrument

The first smoke cell (bouts/2026-07-27-k3-effort-dial-smoke, 01-bugfix,
labeled low) passed its grade — and its wire log shows
`requested_efforts: ["max"]`. The per-alias `default_effort` had not
flowed through to the request on the first wiring attempt. The graded
result alone was indistinguishable from a working dial; only the
wire-level proof caught it. After the config fix, smoke run-2 recorded
`["low"]` and the grid proceeded. This is why every one of the 54 grid
runs carries per-request effort proof rather than assuming the config
worked: the silent failure mode is real and we hit it on the first try.

## The effort table (per 6-task pass, sums of per-task medians)

| Arm | Thinking chars | Output tokens | Tool calls | Cost | Execution time |
| --- | --- | --- | --- | --- | --- |
| low | 6.6k | 6.1k | 40 | $0.50 | 358s |
| high | 20.8k | 10.2k | 53 | $0.59 | 512s |
| max | 80.0k | 16.9k | 56 | $0.69 | 688s |

Lever hierarchy low→max: thinking 12.1x, output tokens 2.8x, execution
time 1.9x, tool calls 1.4x, cost 1.4x, grades 1.0x. The published Opus 5
dial on the same battery: cost 2.2x (full battery $1.48→$3.33), execution
time 3.1x, grades 1.0x. Two dials, same grades, opposite economics: the
Opus 5 dial moved the bill; the K3 dial moves reasoning volume while cheap
cache reads and context-dominated traffic hold the bill nearly flat.

## Behavioral note (02-synthesis, low arm)

Low effort did not just think less; it worked less: 3.7 turns median vs
8-9 at high/max, one Read + one Bash in run-2 (22 chars of thinking) for
a 6/6 pass. The task's information need was satisfiable in one pass;
higher effort re-read and re-verified. Same pattern in miniature as the
Opus 5 low arm (52 vs 99 tool calls).

## H7 judge table (Opus 4.8, blind, 3 samples per run, median of samples)

**H7 HIT (depth is effort-insensitive).** Pre-registered bar: low within
1 point of max on per-task medians. Measured: 05-review low 4 vs max 5;
06-instructions low 5 vs max 5. Arm totals (of 36): low 27, high 24,
max 30 — non-monotone, with the high arm below low, which is the shape
of judge noise, not of a depth dividend. Per-run medians:

| Task | Arm | Run totals (of 6) | Dimension detail |
| --- | --- | --- | --- |
| 05-review | low | 4, 4, 5 | interaction_synthesis 0,0,1; other dims all 2 |
| 05-review | high | 4, 4, 4 | interaction_synthesis 0,0,0; other dims all 2 |
| 05-review | max | 6, 4, 5 | interaction_synthesis 2,0,1; other dims all 2 |
| 06-instructions | low | 3, 6, 5 | insight 1,2,2; quant 1,2,1; specificity 1,2,2 |
| 06-instructions | high | 3, 4, 5 | insight 1,1,2; quant 1,1,1; specificity 1,2,2 |
| 06-instructions | max | 4, 6, 5 | insight 1,2,2; quant 1,2,1; specificity 2,2,2 |

The only dimension with any effort signal, interaction_synthesis on
05-review (0/0/0-1 at low/high vs 2/0/1 at max), is the same dimension
the transplant experiment showed responds to four lines of prompt, and
it moves within-arm as much as between arms. 80k characters of max-arm
thinking bought nothing this judge could price.

Judge-pass provenance: 17/18 runs judged in one pass 2026-07-28
(~12:0x-12:25 UTC); one judge invocation (05-review/high/run-3) died
without writing judge.json and was rerun ~13:0x UTC same day; one sample
within another run was unparseable and retried by the harness. Final
data: n_samples=3 for all 18 runs.

## Claims map (step 3.5)

- Moonshot launch blog "max default, low/high in subsequent updates":
  CONFIRMED delivered; tested here end-to-end through Kimi Code 0.27.0
  per-alias config. (Misquote in our own DESIGN corrected above.)
- Platform docs `reasoning_effort` low/high/max, default max: consistent
  with probes (all three accepted on the OpenAI-compatible surface;
  reasoning volume scales in the factorial probe 70→260 reasoning tokens).
- AA ~2x verbosity: INVERTED on agentic work (H4). Suite construction,
  not model character, appears to carry that number.
- vLLM day-0 "K3 thinks a lot before it answers": true in thinking volume
  (80k chars/pass at max), NOT in completion tokens or bill on this
  battery; and the dial is the mitigation the discourse mostly ignores.
- Cross-vendor serving variance (same weights, 8 providers by 7/28):
  out of reach without third-party keys; named future work.
