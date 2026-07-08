# Bout analysis: transplant — 2026-07-07

Design pre-registered in [DESIGN.md](DESIGN.md) (committed `b8a3375`, before
any transplant run). Arms: Opus 4.8 vanilla and Fable 5 vanilla reused from
the 2026-07-07-ladder-noise bout (N=5 per task, identical harness config);
Opus 4.8 transplant ran the `-transplant` prompt variants, N=5 per task,
serial, after the ladder bout completed (no concurrent API traffic).
Judging: `bin/judge-run.sh`, judge `claude-opus-4-8`, blind to arm, 3 samples
per run, median reported. 29 of 30 runs judged on the first pass; one
(fable/05/run-4) failed JSON parsing twice and was re-judged successfully.

## Judge scores (median of run-medians; brackets = the 5 per-run medians)

| Task | Dimension | Opus vanilla | Opus transplant | Fable vanilla |
|---|---|---|---|---|
| 05 | location_precision | 2.0 [2,2,2,2,2] | 2.0 [2,2,2,2,2] | 2.0 [2,2,2,2,2] |
| 05 | interaction_synthesis | **1.0 [0,0,1,2,2]** | **2.0 [0,2,2,2,2]** | **2.0 [0,2,2,2,2]** |
| 05 | causal_clarity | 2.0 [2,2,2,2,2] | 2.0 [2,2,2,2,2] | 2.0 [2,2,2,2,2] |
| 06 | quantification | 2.0 [1,2,2,2,2] | 2.0 [2,2,2,2,2] | 2.0 [2,2,2,2,2] |
| 06 | specificity | 2.0 [2,2,2,2,2] | 2.0 [2,2,2,2,2] | 2.0 [2,2,2,2,2] |
| 06 | insight_density | 2.0 [2,2,2,2,2] | 2.0 [2,2,2,2,2] | 2.0 [2,2,2,2,2] |

## Cost and correctness

| Arm (tasks 05+06 only) | Pass | Cost | Output tokens (05 / 06) |
|---|---|---|---|
| Opus vanilla | 10/10 | $0.58 | 5670 / 5120 |
| Opus transplant | 10/10 | $0.74 | 8010 / 7755 |
| Fable vanilla | 10/10 | $0.99 | 5804 / 2842 |

## Hypothesis verdicts

- **T1 (transplant ≥ vanilla everywhere) — confirmed.** Strictly better on
  interaction_synthesis (median 2.0 vs 1.0) and 06/quantification's single
  sub-ceiling run; ties at ceiling elsewhere.
- **T2 (reaches Fable on ≥3/6 dimensions) — confirmed, and then some.** The
  transplant matches Fable's median on all six dimensions — on the one
  discriminating dimension its per-run distribution is *identical* to
  Fable's ([0,2,2,2,2]).
- **T3 (no correctness regression) — confirmed.** 10/10, all graders at max.
- **T4 (cost within 15% of vanilla) — refuted.** Transplant cost +28%
  ($0.74 vs $0.58); output tokens rose 41–51%. The preamble is ~90 input
  tokens, so the delta is behavior, not prompt length: asked to defend edges
  and quantify comparisons, Opus writes substantially more. The depth
  behaviors cost tokens *whoever exhibits them* — which also reframes part
  of Fable's price premium on these tasks as the cost of habits, not just
  the price sheet.
- **T5 (the money question) — prompting wins on these tasks, with caveats.**
  T1–T3 held: a four-rule preamble bought Fable-level judged depth at 75% of
  Fable's cost (transplant $0.74 vs Fable $0.99 on the same tasks). The
  pre-registered escape clause — "if transplant plateaus below Fable on
  interaction_synthesis, that's evidence of capability" — did not trigger.

## Honest limitations

- **Ceiling everywhere but one dimension.** Five of six rubric dimensions
  scored 2.0 for every arm, so this experiment discriminates on exactly one
  behavior (interaction synthesis in code review). The rubric inherited the
  tasks' low ceiling; harder v2 tasks need harder rubrics.
- **Small N on a coarse scale.** Five runs per cell, 0–2 medians. The
  vanilla distribution [0,0,1,2,2] vs transplant [0,2,2,2,2] is a visible
  shift, not a significance test. Note both Fable and transplant each
  produced one 0-scoring run — none of these behaviors is deterministic.
- **Same-family, self-adjacent judge.** The judge (Opus 4.8) is the vanilla
  arm's own model, blind to arm but not to style. Rubric + blind protocol
  are the available mitigations; an out-of-family judge would strengthen
  this.
- **Judge API cost was not metered** — judge-run.sh discards the CLI cost
  envelope (90+ short calls, single-turn; harness improvement noted).
- Vanilla-arm runs were executed hours earlier (within the ladder bout) than
  transplant runs; same pinned config, but time-of-day API conditions were
  not identical.

## Verification record

- All 30 `judge.json` files present; every file records judge model, all 3
  raw samples, and the median (re-run of fable/05/run-4 included).
- Transplant grader parity spot-checked: variant `grade.sh` execs the parent
  grader; both variants' graders produced max scores on all 10 runs.
- Peek checks: 10/10 transplant runs `clean`.
- Analyst disclosure: written by Claude (Fable 5) — the model whose behaviors
  were being transplanted — from committed artifacts and blind judge output.
