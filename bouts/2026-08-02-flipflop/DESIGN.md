# Bout design: does Opus 5 flip-flop in agentic loops more than 4.8 (pre-registered)

Committed before the graded grid. Founder-directed 2026-08-02: two weeks of
community complaints single out one behavior, "each round was just
flip-flopping the same logic back and forth" over ~13 iterations, "never saw
anything remotely this bad on Opus 4.8" (Hacker News 49079191, and related
reports). This bout tries to reproduce or refute that, and tests whether the
effort dial is the lever.

## Instrument

New task tasks/09-converge: a money-formatter with genuine multi-constraint
tension. The sign must be decided from the ROUNDED value; a value that rounds
to zero is not negative. A naive "sign from the raw input" fix passes most
tests and fails exactly the rounds-to-zero case (proven in check-grader), so a
careless fix to one constraint can re-break another. The full test suite ships
in the fixture, so the agent iterates against pytest naturally; the flip-flop,
if it happens, is whack-a-mole across the interacting tests inside one run.
Proven solvable (reference passes 2/2) so non-convergence is a model property.

Measurement (bin/loopmetrics.py, from transcripts):
- regressions: successive pytest runs where the failing count INCREASED
  (broke something that was passing) -- the whack-a-mole signature; monotone
  convergence has zero.
- reverts: an edit re-introducing a code region a prior edit removed.
- test_runs, edits, converged, and output tokens (verbosity cross-check).

## Field and protocol

- claude-opus-5 at effort=low AND effort=xhigh (the dial is a hypothesis),
  claude-opus-4-8 at xhigh, claude-fable-5 at xhigh. r=6, serial, same window,
  CLI recorded. Deterministic grader; no judge.

## Hypotheses

- **H1 (the complaint):** Opus 5 at xhigh shows more regressions per run than
  Opus 4.8 at xhigh. If false (equal or fewer), the complaint does not
  reproduce on this task and we report that as the lead.
- **H2 (effort is the lever):** Opus 5 at low shows fewer regressions and
  fewer edits than Opus 5 at xhigh. A large gap would mean the flip-flop, if
  real, is an effort-setting artifact with a one-line fix.
- **H3 (convergence):** all configurations converge (grade pass) in the
  60-turn budget; the story is HOW they converge (churn, regressions), not
  whether. A genuine non-convergence (DNF) by any config is the lead finding.
- **H4 (verbosity co-travels):** Opus 5 xhigh emits more output tokens and
  more edits than 4.8, consistent with the "burns tokens / Claude Slop"
  complaints, and low effort reduces both.

## Analysis + disclosures

loopmetrics per corpus; per-run fail trajectories published. Disclosures: one
task family and one tension shape, so a null result refutes the complaint ON
THIS TASK, not universally; single-run internal loop, not the multi-agent
outer review loop some reports describe (a follow-up if the signal needs it);
home-field and Fable-co-authorship as always; complaints are anecdotal and
we are testing them, not endorsing them.
