# Technical amendment 005: Kimi wire-identity compatibility replacement

Status: draft, to be frozen and independently reviewed before any replacement
call. No target call has occurred under this amendment.

## Scope

Amendment 004 remains immutable. This amendment authorizes one excluded-smoke
replacement attempt for the Kimi K3 condition after the Amendment-004 Kimi
attempt was halted by the run-integrity gate. The historical Codex attempt and
the Amendment-004 Kimi evidence remain preserved and excluded.

The target-facing prompt, task, domain neutrality, hypotheses, native/default
effort, scoring rubric, semantic analysis, and confirmatory sample size do not
change. The exact prompt remains 471 bytes with SHA-256
`5d8df8bce37fba5832273d20f99d4ef05abd87c3590be62ceed349e90f3da2b0`.

## Trigger and observed compatibility issue

The response-free Amendment-004 status recorded the Kimi process exit as zero,
but marked the attempt `invalid_setup`. Its observable wire identity contained
model `kimi-k3`, alias `arena/k3`, and provider label `kimi`; the Amendment-004
condition expected provider label `moonshot-platform`. The same status reported
unknown trace shapes and a failed trace-integrity gate. Raw responses, wire
payloads, policy values, metrics, and other semantic content were not inspected.

The replacement changes only the expected Kimi wire-provider label from
`moonshot-platform` to `kimi`. It does not change the Kimi CLI, model argument,
platform base URL, credential source, effort setting, instruction stack, tool
configuration, or target prompt. Any new trace-integrity failure remains an
invalid setup and halts the amendment without another retry.

## Replacement accounting

- Predecessor: immutable Amendment-004 smoke manifest and its one Kimi row.
- Replacement: exactly one new Kimi primary slot in a new bout directory.
- Previously consumed calls: two (historical Codex plus Amendment-004 Kimi).
- Amendment-005 call cap: three cumulative calls, leaving one available call.
- Retries: forbidden. A claimed, uncertain, invalid, or integrity-failed
  replacement consumes the Amendment-005 opportunity and cannot be rerun.
- Claude is not included in this replacement and will not be called by it.
- All replacement output is excluded from semantic analysis.

## Integrity and approval gate

The replacement manifest binds the exact Amendment-004 manifest bytes, freeze ID,
failed Kimi slot, and recorded exclusion reason. It uses a new bout directory and
does not rewrite any prior manifest, ledger, claim, intent, or raw artifact.

Before the call, the amendment, runbook, harness, tests, and replacement
manifest must be committed at one exact candidate commit. Two fresh-context
offline reviewers must approve that candidate. The replacement call remains
forbidden until the user explicitly approves the frozen Amendment-005 design.

No confirmatory call is authorized by this amendment.
