# Technical amendment 003: atomic freezes, journal-first claims, and eligibility pauses

Status: documented before either remaining smoke call and before every
confirmatory call.

## Scope and preserved decisions

This amendment changes only manifest-publication safety, target-attempt
accounting, and confirmatory pause behavior. It does not change the task,
target prompt, hypotheses, conditions, scoring rubric, exclusions, sample
size, randomization, analysis, or approval gate.

The target prompt remains exactly 471 bytes with SHA-256
`5d8df8bce37fba5832273d20f99d4ef05abd87c3590be62ceed349e90f3da2b0`.
There is no target-facing compatibility amendment.

The base package and technical amendments 001 and 002 remain immutable. The
superseded amendment-001 confirmatory and smoke-continuation freezes are
`f6a4914524616cc4f4fb32641778f6cfdc0b0ca65ecb1e486b9d8643df2e5a15`
and `fbdbb1466efc22b71943c4d45419e24ecd98dd77fc0fb0bd5d064f3a7e490199`.
The superseded amendment-002 freezes are
`907f1280f3d9670899836fe476bbb5b17d7a70272a9b4f52c64d70d76a4c740c`
and `0b80e0f9b1fd4cfda26a78a3a134f3b97a9ab52861c17932d2053a91dde89a71`.
No target call was made under either superseded continuation.

The initial excluded-smoke freeze remains
`5b65987b40e70dcce883381baa40c93440510a82b95e048ea2caff4447d1762e`.
Exactly its one Codex call is consumed. The remaining suffix is still Kimi
followed by Claude, for a cumulative maximum of three smoke calls and no
retries. No confirmatory call has occurred.

## Triggering review evidence

Two fresh reviews of committed candidate `c29bed5` identified three harness
protocol gaps:

1. manifest creation checked for an existing output and then wrote the final
   path in place, allowing concurrent creators to report different freezes
   while one silently replaced the other's bytes;
2. an intent was the only pre-launch witness until the execution ledger was
   written, so deleting one unresolved intent restored apparently unattempted
   state; and
3. one multi-slot confirmatory invocation could continue after a newly
   recorded `analysis_eligible: false` outcome because only selected failure
   states forced an immediate pause.

These are offline harness findings. No target, model, or API call and no smoke
response semantics were involved.

## Atomic no-clobber manifest publication

A manifest is constructed completely before publication. The publisher opens
and validates its output parent without following symlinks, creates an
owner-only randomized temporary regular file there with exclusive no-follow
creation, writes and synchronizes the exact bytes, verifies the completed
file, and publishes it with a same-directory no-replace operation. It then
synchronizes the parent directory before reporting success.

An existing destination, unsafe path, unsupported no-replace primitive, or
publication race fails closed without changing the destination. A failing
invocation may remove only the temporary file that it created. Explicit draft
replacement remains restricted to a safe same-experiment draft with no run
artifacts; it verifies that the original inode and bytes did not change before
one atomic replacement. Confirmatory reproduction uses an absent destination
in a disposable clean checkout and compares the complete bytes with the
committed manifest.

## Journal-first durable target-call accounting

Every current manifest freezes an `ATTEMPT_CLAIMS.jsonl` contract in addition
to immutable `ATTEMPT_INTENTS/<slot_id>.json` records and `EXECUTION.jsonl`.
While holding the bout-wide nonblocking exclusive lock, the runner validates
the complete claim, intent, and ledger union before selecting a slot.

After all no-call preparation succeeds, the runner constructs the exact intent
bytes and their SHA-256. Before any driver `Popen`, it:

1. appends one canonical slot-bound row to `ATTEMPT_CLAIMS.jsonl`;
2. synchronizes that journal and its parent directory;
3. exclusively creates the exact prehashed intent and synchronizes both the
   file and intent directory; and
4. rereads and validates the claim-to-intent binding, order, and call budget.

The journal row binds the manifest freeze, phase, frozen slot and condition,
primary or reserve kind, run directory, replacement metadata, timestamp,
preflight hash, harness commit, staged-command hash, intent path, and intent
hash. A completed execution-ledger row must bind the exact claim-journal path,
sequence, and row hash as well as the exact intent path and hash.

A slot represented by any of the journal, intent set, or ledger consumes its
call budget. Exactly one matching claim, intent, and ledger row is resolved.
Journal-only, intent-only, claim-plus-intent without a ledger, ledger-only,
duplicate, partial, malformed, unsafe, out-of-order, or field- or hash-mismatched
state is unresolved and blocks every later dry or live execution without retry
or automatic repair. The initial Codex smoke record is the sole frozen legacy
exception without current claim and intent witnesses. Current smoke accounting
is the inherited Codex count plus the union of current witnesses.

This rule is conservative: a durable journal claim consumes its slot even if a
crash occurred before process launch. Recovery requires separately documented
evidence and a new amendment; deleting or rewriting a witness is not recovery.

## Threat boundary

The journal is an independently synchronized witness and makes partial loss or
disagreement detectable. It cannot prove tampering by an actor able to delete
every related witness and repository state from the same owner-writable local
filesystem. The protocol covers cooperative operation, concurrent runners,
partial evidence loss, and expected runner or host crashes, not malicious
same-owner destruction of all local evidence.

## Immediate confirmatory eligibility pause

After each confirmatory attempt, the runner first durably appends and validates
its ledger row. If the new primary or reserve has `analysis_eligible: false`,
the invocation then stops before another target process can launch, regardless
of wrapper exit status or validity-state label.

A ledgered ineligible attempt may be replaced only by a later explicit command
using the next frozen reserve for that condition, the exact replaced attempt,
and a preregistered exclusion reason supported by its recorded evidence. An
ineligible reserve causes the same pause. Primary execution may resume only
after the effective replacement chain ends in an eligible attempt. Reserves
are never launched automatically.

Smoke is exempt from this confirmatory gate because all smoke outputs are
intentionally analysis-ineligible. Its exact suffix, cumulative call cap,
integrity gates, and no-retry rule remain binding.

## Validation amendment

Offline regressions cover no-clobber publication and concurrent publishers;
journal durability and append integrity; every journal, intent, launch, and
ledger crash boundary; three-witness binding; partial deletion, mismatches,
and call-budget union accounting; the historical exception; and immediate
confirmatory pauses for primaries and reserves.

The remaining smoke calls require fresh independent protocol and security
approvals of the exact amendment-003 commit.
