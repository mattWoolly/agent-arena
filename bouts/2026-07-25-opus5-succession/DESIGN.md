# Bout design: Claude Opus 5 succession audit (pre-registered)

Committed before any graded run. Founder-requested 2026-07-25. Blocked on
API credits at design time; whichever session first finds credits restored
executes this design unchanged. Anything the data does to the hypotheses is
reported, misses first.

## Question

Opus 4.8 anchored this arena all month: mid-priced, matched Fable's grades
at half the cost, and judged every rubric task we published. Its successor
launched 2026-07-24 at $5/$25 with a per-request effort toggle. Two
questions, one new axis: does the succession buy anything our instruments
can see, and what does the effort toggle actually price. The toggle is the
proprietary angle: a cost ladder inside one model, measured on a battery
with published baselines for five other configurations.

## Grid (est. $40-45 total; hard cap $50)

1. **Core:** `claude-opus-5` (exact ID verified at smoke; effort left at the
   CLI default, recorded) on all 8 tasks, r=3, serial. Claude Code native,
   same pinned conventions as every prior bout.
2. **Effort sweep:** low and high (`--effort` / whatever the CLI exposes for
   Opus 5, recorded verbatim) on a 3-task subset spanning the battery's
   range: 01-bugfix (short agentic), 04-terminal (heaviest agentic),
   06-instructions (judged prose). r=3 each: 18 runs.
3. **Same-window anchors:** Fable 5 and Opus 4.8, r=3, on the same 3-task
   subset (18 runs). Rationale is our own noise-floor finding: token-metered
   numbers are stable across windows, stopwatch numbers are not; published
   cost rows stand, wall-clock claims get fresh anchors.
4. **Judge pass:** Opus 4.8, blind, 3 samples, on the rubric tasks of the
   core grid plus the 06-instructions sweep cells. Disclosure: the judge is
   scoring its own successor; judge model recorded per run as always.
5. **Mechanism trace:** the established reanalysis class (re-read
   fingerprint, tool mix, first-move, delegation events) on the core
   transcripts, versus the published fingerprints for Fable/4.8/Kimi/Sol.

## Hypotheses

- **H1 (floor holds):** core grid 24/24 with full deterministic scores.
- **H2 (succession pricing):** default-effort cost per full pass within
  ±25% of Opus 4.8's published $2.27.
- **H3 (the toggle is monotone and safe):** wall clock and output tokens
  rise monotonically low → default → high on every sweep task, and grades
  hold at every effort. The interesting miss is a low-effort failure: that
  would be the first un-saturation of this battery since Haiku, and it
  would make effort, not model choice, the price of correctness.
- **H4 (depth):** judge total for Opus 5 lands in [66, 72], at or above
  4.8's 68. Below 66 is a regression finding and leads the article.
- **H5 (family resemblance):** Opus 5's working style sits closer to 4.8
  than to Fable: tool-mix proportions within 10 points of 4.8's published
  mix, wall CV nearer 4.8's than Kimi's 25%.
- **H6 (launch serving):** zero API retries across all new runs. Anthropic
  launch week versus Moonshot launch week is a published contrast worth a
  sentence either way.
- **H7 (transplant, fifth model):** on 05-review cells run during the core
  grid, the transplant variant lifts interaction_synthesis medians relative
  to baseline, as it has for four models across three vendors and three
  harnesses.

## Disclosures pinned in advance

Home field (Anthropic model in Anthropic tooling); judge is the
predecessor of the model under test; Fable co-authors harness and article;
effort-toggle semantics are vendor-defined and recorded, not assumed;
credits outage means run window is later than launch day and the article
says so plainly (day-two-or-later bout, not day-one).

## Analysis plan

summarize.py rows merged against published baselines; effort ladder table
(cost, wall, tokens, grades per effort); H-by-H verdicts, misses first;
judge medians vs the 4.8 and Fable columns; mechanism-trace fingerprint
paragraph; article follows the pipeline's standard panel + peer-review
path. Budget logged to pipeline state.json regardless of outcome.
