# Verification prompt versus inference effort

Pre-registered before any new model run. The exact prompts, confirmatory task,
grader, run order, model, effort settings, repetitions, and analysis code are
committed and pushed before the first development smoke.

## Question

For one fixed coding agent, does a short, generic verification instruction at
`low` effort produce more source-audit utility per dollar than the base prompt
at `xhigh` effort?

This is the 2 by 2 control proposed in the prompt-engineering research design:
base versus verification prompt, crossed with low versus high inference effort.
The operational high setting is `xhigh`, the arena's established default.

## Development evidence and intervention

The 2026-08-17 arithmetic bout is development evidence only. On `15-rollup`,
Claude Sonnet 5 flagged a planted EUR 300 source inconsistency in 0/3
incidental runs at `xhigh`, and 2/6 across both task framings. Those outputs
motivated the generic verification preamble below. No task-16 output exists at
the time of this freeze.

The intervention, byte-identical in `15-rollup-verify` and
`16-source-audit-verify`, is:

> Before finalizing, independently verify the deliverable against the supplied
> source evidence. Recompute or cross-check material claims where the evidence
> permits. If the supplied evidence is internally inconsistent, report the
> conflict and state which interpretation you used.

It does not name a domain, field, value, or expected inconsistency. Everything
after the preamble is byte-identical to the corresponding base prompt.

## Development smoke

Four new `15-rollup` runs exercise every cell once and are excluded from all
confirmatory estimates:

1. base-low
2. verify-xhigh
3. base-xhigh
4. verify-low

The confirmatory grid may begin only if each smoke has the requested effort in
`run_env.json`, served model `claude-sonnet-5`, a clean `peek_check`, complete
metrics, and a parseable discrepancy FLAG. Any instrument change after a smoke
requires a numbered amendment committed and pushed before confirmation.

## Confirmatory task

`16-source-audit` is a new private task with four source packets and a required
leadership brief. Three packets contain different inconsistency mechanisms:

- finance: a stated spend total conflicts with its category line items;
- support: a stated close rate conflicts with its numerator and denominator;
- delivery: a stated launch date conflicts with a business-day phase plan.

The fourth, security, is a clean control whose stated resolution rate exactly
matches its counts. This measures verification-induced false alarms without
doubling the model calls.

The grader recomputes truth from its pristine fixture. It accepts either
defensible source basis for downstream key figures, separately reports six
key-figure verdicts, emits three non-gating `FLAG <source> yes|no` lines, and
emits `FALSE_FLAG security yes|no`. Document structure is the task-level gate.
The agent never sees the grader, reference solution, or repository tree.

## Fixed and varied factors

| Factor | Frozen value |
|---|---|
| Model | `claude-sonnet-5` |
| Driver | Claude Code 2.1.239, native Anthropic route, subscription OAuth |
| Prompt | base or generic verification preamble |
| Effort | `low` or `xhigh` |
| Repetitions | 10 per prompt-effort cell |
| Total confirmation | 40 serial runs |
| Task | `16-source-audit` plus its prompt-only variant |
| Max turns / timeout | 60 / 1,500 seconds |
| Settings sources | `project` |

The model is fixed because the causal question is prompt versus inference
effort, not a model leaderboard. Sonnet was chosen from development evidence:
it had headroom on the source-audit behavior, runs natively, and avoids both a
translation-layer confound and the Opus ceiling observed on `15-rollup`.

The 40-cell execution order is frozen in `ORDER.tsv`, shuffled with seed
20260821. Runs are serial. `low` and `xhigh` are requested vendor settings, not
assumed-equivalent quantities of hidden reasoning. Realized tokens and cost are
reported.

## Outcomes and analysis

The primary per-run outcome is **audit utility success**:

- task-level grade passes;
- all six key figures are correct under an accepted source interpretation;
- all three planted inconsistencies are explicitly identified; and
- the clean security packet is not falsely flagged.

The confirmatory contrast is verification-low minus base-xhigh. Exact counts
and Wilson 95% intervals are reported. Verification-low is the economic winner
only if its success rate is at least base-xhigh's and its mean realized cost is
no higher. Otherwise both points remain on the prompt-engineering frontier or
the result is inconclusive.

Secondary outcomes:

- base-low versus verification-low: prompt effect at low effort;
- base-low versus base-xhigh: effort effect under the base prompt;
- prompt-by-effort difference in differences;
- per-source detection rate and clean-source false-alarm rate;
- key-figure accuracy, task pass rate, tokens, turns, cost, and execution time.

No LLM judge and no null-hypothesis significance test are used. Ten runs per
cell can identify a large behavioral movement, not a subtle one. Repeats
measure sampling variance on this task, not transfer to every source-audit
setting.

## Hypotheses

- **H1 (primary):** verification-low has at least the audit-success rate of
  base-xhigh at no higher mean realized cost.
- **H2 (prompt effect):** verification-low improves audit success over
  base-low by at least 40 percentage points.
- **H3 (relative intervention):** the low-effort prompt gain is larger than
  the base-prompt gain from low to xhigh.
- **H4 (false alarms):** neither verification arm falsely flags the clean
  security packet in more than 1/10 runs.
- **H5 (integrity):** all 44 new runs, including four excluded smokes, match
  the declared served model and requested effort, with zero peek or secret
  leak flags.

Misses are reported before hits.

## Budget and stop rules

Local evidence prices Sonnet's prior `15-rollup` xhigh runs at about $0.17
notional list cost each. Forty confirmation runs plus four smokes are expected
to remain below $10 notional, with zero incremental API charge under the
existing subscription. The hard stop is $25 notional or any evidence that the
subscription route was shadowed by a pay-as-you-go key.

Stop before confirmation if a smoke has the wrong served model or effort,
missing telemetry, a grader failure, a peek or secret warning, or an
unparseable FLAG. Stop the grid if cumulative notional cost exceeds $20, leaving
room for retries under the $25 hard stop. Do not replace failed outputs or tune
the prompt after seeing confirmation results.

## Validity boundaries

1. The verification preamble explicitly requests source checking. This tests
   whether that instruction is a better resource purchase than higher effort,
   not whether verification emerges unprompted.
2. All three planted conflicts appear in one task. Run repetitions are
   independent samples, but the source stimuli are fixed; generalization to
   other domains requires another frozen task.
3. A clean control is present, but one packet is a thin estimate of false
   alarms.
4. Sonnet under Claude Code is one model-scaffold pairing. Cross-model transfer
   is a separate experiment.
5. Subscription runs still report notional list-price cost from usage. That is
   comparable resource accounting, not incremental cash spend.
