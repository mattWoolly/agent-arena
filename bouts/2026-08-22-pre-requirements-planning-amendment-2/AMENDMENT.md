# Technical amendment 002: crash-durable target-call accounting

Status: documented before either remaining smoke call and before every
confirmatory call.

## Scope and preserved decisions

This amendment changes only target-attempt accounting and resume safety. It
does not change the task, prompt, hypotheses, conditions, scoring rubric,
exclusions, confirmatory sample size, analysis, or approval gate. The target
prompt remains exactly 471 bytes with SHA-256
`5d8df8bce37fba5832273d20f99d4ef05abd87c3590be62ceed349e90f3da2b0`.
There is no target-facing compatibility amendment.

Technical amendment 001 and all artifacts produced before this amendment
remain immutable. Its superseded confirmatory freeze is
`f6a4914524616cc4f4fb32641778f6cfdc0b0ca65ecb1e486b9d8643df2e5a15`,
and its unexecuted smoke-continuation freeze is
`fbdbb1466efc22b71943c4d45419e24ecd98dd77fc0fb0bd5d064f3a7e490199`.
The initial excluded-smoke freeze and its one consumed Codex call remain
anchored exactly as described in amendment 001. No additional target call was
made under the amendment-001 continuation.

## Triggering review evidence

Independent security review of committed candidate `c58cb0f` found that the
runner did not durably record an attempt until after the target process had
returned, cleanup had completed, artifacts had been recovered and normalized,
and the execution ledger was appended. An uncatchable host or runner crash in
that interval could leave neither a ledger row nor a recovered run directory.
A later invocation would then select the same frozen slot and could exceed the
no-retry smoke-call cap.

This is a harness-safety defect, not target evidence. The finding used an
offline synthetic process and made no target, model, or API call.

## Frozen correction

Every production manifest now declares one exact attempt-intent contract. For
each invocation, the runner first holds a nonblocking exclusive advisory lock
on the bout directory for the complete state-check and execution transaction.
For each frozen slot, after all no-call preparation succeeds but before the
driver process is launched, the runner:

1. constructs a slot-bound record containing the manifest freeze, condition,
   preflight hash, harness commit, and staged command hash;
2. creates the record at `ATTEMPT_INTENTS/<slot_id>.json` with an exclusive
   no-follow regular-file operation; and
3. synchronizes both the file and its containing directory before `Popen`.

The intent is immutable and is not deleted. A completed execution-ledger row
must cite its exact repository-relative path and SHA-256. Ledger appends are
also file- and directory-synchronized. Before dry-run selection, live
execution, status reporting, or any resumed call, the runner validates the
entire intent directory and every ledger binding.

An intent without exactly one matching durable ledger row is unresolved. It
conservatively represents a possibly launched target, consumes the claimed
slot for call-budget purposes, and blocks all further execution. It may not be
deleted, rewritten, or retried. Recovery would require separately documented
evidence and a new amendment; this amendment provides no automatic recovery
or retry path.

The intent set must follow the frozen primary and reserve ordering. Unknown,
malformed, non-regular, symlinked, out-of-schedule, duplicate, hash-mismatched,
or tampered records fail closed. Concurrent runners contending for the same
pending slot cannot both acquire it because creation is exclusive.

## Validation amendment

Offline regression tests cover production-manifest contract integrity,
exclusive concurrent claims, intent-before-spawn ordering, unresolved intents
at each post-claim crash boundary, pre-claim failure, durable ledger binding,
resume advancement, call-cap accounting, tampering, symlinks, and historical
compatibility. The two remaining smoke calls require fresh independent
protocol and security approvals of the exact amended commit.
