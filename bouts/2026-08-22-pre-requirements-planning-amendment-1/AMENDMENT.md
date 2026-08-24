# Technical amendment 001: Codex completed-item trace compatibility

Status: documented before either remaining smoke call and before every
confirmatory call.

## Scope and preserved decisions

This amendment changes only observable-trace classification and smoke
continuation mechanics. It does not change the task, prompt, hypotheses,
conditions, scoring rubric, exclusions, confirmatory sample size, analysis, or
approval gate. The target prompt remains exactly 471 bytes with SHA-256
`5d8df8bce37fba5832273d20f99d4ef05abd87c3590be62ceed349e90f3da2b0`.
There is no target-facing compatibility amendment.

The superseded confirmatory freeze is
`65d952383df9b167dae3104e9bc33c30b864bf28f2b258353bdc85c34c8ad32e`.
The initial excluded-smoke freeze is
`5b65987b40e70dcce883381baa40c93440510a82b95e048ea2caff4447d1762e`.
Both manifests and all artifacts already produced under them remain immutable.

## Triggering smoke evidence

After two independent offline approvals of committed candidate `c4c4c84`, the
initial randomized smoke command began. It made one target call, the first
Codex slot, and then halted at the integrity gate. The Codex CLI exited zero,
the target returned, no tool event or workspace change was observed, process
containment was cleaned, and the raw attempt was content-addressed and appended
to the excluded-smoke ledger. Normalization marked it `invalid_setup` solely
because two rollout envelopes used the previously unseen technical shape
`event_msg.item_completed`; their nested item types were `UserMessage` and
`AgentMessage`. This record states types and keys only and does not quote or
evaluate either message.

During initial technical triage, an overbroad projection of `metrics.json`
inadvertently displayed the first smoke response and instruction-policy value.
The response is not scored, is not used to tune the rubric or prompt, and
remains excluded. This observer-contamination limitation must appear in the
smoke evidence and final handoff.

## Frozen correction

The trace parser now recursively classifies `item_completed.item`:

- only the explicitly passive `UserMessage`, `AgentMessage`, `Plan`,
  `Reasoning`, and `ContextCompaction` variants pass without an action;
- action-bearing protocol variants are recorded as target activity; and
- malformed or unknown nested variants continue to fail closed.

This follows Codex's typed `TurnItem` lifecycle, where completed items can also
represent commands, file changes, tool calls, web searches, and collaboration
activity (see the official
[`TurnItem` schema](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/items.rs)).
Regression tests cover the observed passive wrappers, an active
command wrapper, a malformed wrapper, and an unknown future type.

## Smoke continuation and call accounting

The smoke budget remains exactly three target calls total, without retries.
For this budget, a call is one target CLI invocation after the executor's
preflight; any ledgered ambiguous or failed attempted slot consumes its place
and is never retried. Such a failure may leave fewer than three completed
responses, but it cannot cause more than three invocations.
One call is consumed by the immutable initial Codex attempt. A separately
frozen continuation manifest anchors the predecessor manifest, append-only
ledger, and attempt artifact manifest; contains only the two unattempted
conditions; and preserves their original frozen relative order. Codex is absent
from the continuation condition and schedule sets, so it cannot be retried by
that manifest. Both remaining outputs are excluded from confirmatory analysis
and must be inspected only through the redacted technical-status command.

The confirmatory matrix is refrozen in a separate amended bout directory. It
remains execution-locked until the user explicitly approves its new exact
freeze ID. No confirmatory invocation occurred before this amendment.
