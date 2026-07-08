# Bout design: 2026-07-07-transplant (pre-registered)

Committed **before** any transplant run executes. Runs launch only after the
2026-07-07-ladder-noise bout completes, so serialized wall-clock measurements
there are never contaminated by concurrent API calls from this experiment.

## Question

The 2026-07-06 bout found Opus 4.8 and Fable 5 tied on correctness, with
Fable's only visible edge being *depth of write-up*: it connected findings
into compound failure modes, cited file:line unprompted, and quantified
comparisons. Can a ~10-line prompt preamble transplant those behaviors onto
Opus 4.8 — the expensive model's habits at the cheap model's price?

## Arms (three, two tasks each: 05-review and 06-instructions)

1. **Opus vanilla** — `claude-opus-4-8` on the unmodified tasks. Reused from
   the 2026-07-07-ladder-noise bout (N=5 per task, identical harness config);
   no new runs.
2. **Opus transplant** — `claude-opus-4-8` on `05-review-transplant` /
   `06-instructions-transplant`: identical fixture and grader (symlink +
   wrapper), PROMPT.md prefixed with a four-rule depth preamble (precise
   locations; interaction synthesis; quantified comparisons; named edge
   cases). N=5 per task, serial.
3. **Fable vanilla** — `claude-fable-5` on the unmodified tasks, the target
   bar. Also reused from the ladder bout (N=5 per task).

## Measurement

- **Correctness** stays with the deterministic graders (transplant must not
  regress pass rate — a preamble that breaks 06's 250-word cap is a result,
  not a nuisance).
- **Depth** scored by `bin/judge-run.sh` against the committed rubrics
  (`tasks/05-review/rubric.md`, `tasks/06-instructions/rubric.md`): three
  dimensions each, 0–2, judge = `claude-opus-4-8`, 3 samples per run, median
  reported. The judge is blind to arm and model. Judging runs after all
  arms complete, in one batch.
- **Cost/latency** from run envelopes as usual: what does the preamble add?

## Disclosures

- The judge model (Opus 4.8) is from the same family as all arms, and is
  itself one of the models under test in the vanilla arm. Scores are
  therefore comparative, not absolute; the blind protocol and fixed rubric
  are the mitigations available within a single-vendor family.
- The rubric dimensions intentionally mirror the transplant preamble — the
  experiment asks whether *prompting for* the behaviors produces them at
  Fable-vanilla levels, as judged blind.
- The preamble was written from Fable's observed behaviors in the 2026-07-06
  bout artifacts, before any transplant run.

## Pre-registered hypotheses

- **T1:** Opus-transplant scores ≥ Opus-vanilla on every rubric dimension's
  median, on both tasks.
- **T2:** Opus-transplant reaches Fable-vanilla's median on at least half the
  dimensions (3 of 6 across both tasks).
- **T3:** Transplant does not regress correctness: pass rate stays 5/5 on
  both tasks.
- **T4:** Transplant cost stays within 15% of Opus-vanilla (the preamble is
  ~90 input tokens; any larger delta is behavior change, not token count).
- **T5 (the money question):** if T1–T3 hold, prompt engineering buys most of
  the observable depth gap at ~half the price; if transplant plateaus below
  Fable on interaction_synthesis specifically, that dimension is evidence of
  capability rather than prompting.
