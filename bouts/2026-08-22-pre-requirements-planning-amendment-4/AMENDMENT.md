# Technical amendment 004: strict launch authorization and execution checkout

Status: preregistered before either remaining smoke call and before every
confirmatory call. The manifest timestamp frozen by this amendment is
`2026-08-23T23:40:00Z`.

## Scope and preserved decisions

This amendment changes only manifest-path handling, durable-attempt witness
validation, pre-launch authorization, execution-checkout safety, and proof of
the already specified confirmatory pause. It does not change the task, target
prompt, hypotheses, conditions, native/default effort settings, scoring
rubric, exclusions, confirmatory sample size, randomized schedule, analysis,
or approval gate.

The target prompt remains exactly 471 bytes with SHA-256
`5d8df8bce37fba5832273d20f99d4ef05abd87c3590be62ceed349e90f3da2b0`.
There is no target-facing compatibility amendment.

Technical amendment 003 was preregistered at commit `230637f` and superseded
before manifest publication and before any target call. Its `AMENDMENT.md` and
`RUNBOOK.md` remain byte-for-byte immutable with SHA-256 values
`55f5b16996172e1395ff9bb894578663426a2ae5c4a3fa6a3864219eb701e11c` and
`65e96fd842ffa99aa1269b01f8d3b14aa9387f58eef4088c96877eb49db4750c`.
No amendment-003 manifest exists and no call occurred under it.

The amendment-002 confirmatory and smoke freezes remain
`907f1280f3d9670899836fe476bbb5b17d7a70272a9b4f52c64d70d76a4c740c`
and `0b80e0f9b1fd4cfda26a78a3a134f3b97a9ab52861c17932d2053a91dde89a71`.
Neither was executed. The initial excluded-smoke freeze remains
`5b65987b40e70dcce883381baa40c93440510a82b95e048ea2caff4447d1762e`;
exactly its Codex slot is consumed. The remaining suffix is Kimi followed by
Claude, with a cumulative cap of three smoke calls and no retries. No
confirmatory call has occurred.

## Triggering pre-freeze evidence

Two independent offline engineering reviews of committed amendment-003
candidate `337b444` found that:

1. launch authorization trusted a ledger list read earlier in the invocation,
   so deletion of the on-disk ledger after claiming but before authorization
   did not stop the mocked `Popen`;
2. resolving the manifest output argument before publication let a canonical
   final-path symlink become its external referent and bypass the publisher's
   no-follow check;
3. generic JSONL parsing accepted a nonempty execution ledger without a final
   newline, so dry-run and status could treat a partial append as resolved;
   and
4. the immediate confirmatory-pause tests did not exercise a live mocked
   launch loop, so removal of the live pause could go undetected.

A separate offline permission review found that Git does not preserve the
owner/group write restrictions of tracked non-executable files. This host's
ordinary checkout materialized tracked files as `0664` and directories as
`0775`. Treating the owning group as private was rejected: NSS enumeration is
not complete on every configured provider, and a POSIX ACL can grant a named
writer independently of the apparent group membership.

These findings used synthetic state only. They did not call a target, access
credentials, inspect response semantics, or change the scientific design.

## Strict manifest and ledger handling

Manifest output paths remain lexical through canonical-path validation and
publication. Every path component and the final entry are inspected without
following symlinks. The atomic no-clobber and compare-and-swap draft rules from
amendment 003 otherwise remain unchanged.

One strict execution-ledger reader is used by continuation construction,
historical validation, dry-run, live execution, launch authorization, status,
blinding, aggregation, and artifact verification. It opens through validated
directory descriptors without following symlinks and requires a real
single-link regular file owned by the runner. Nonempty JSONL must be strict
UTF-8, end in a newline, contain no blank rows, and contain one JSON object per
row. A partial, malformed, missing, unsafe, or concurrently replaced ledger
fails closed wherever attempt state is consumed.

Immediately before every driver `Popen`, launch authorization rereads the
current claim journal, intent directory, and execution ledger from the
filesystem and validates their complete union, bindings, order, provenance,
and call budget. The only unresolved state permitted at that point is the
single current slot whose durable journal claim and immutable intent were just
created by the lock-holding invocation and whose ledger row cannot yet exist.
Deletion or disagreement of any prior witness blocks launch. Authorization is
never based on a cached ledger snapshot.

## Strict execution checkout

Every manifest build and live execution uses an isolated exact-commit checkout
created and kept under `umask 0077`. A mask that permits group or other writes
is rejected before publication or target preparation. The prescribed
environment is an independent local clone rooted beneath an owner-only
directory, so it does not inherit a linked worktree's separately writable Git
common directory.

Before publication and again before every target launch, the harness validates
the repository trust root and the active replacement ancestry, manifest,
claim journal, intent directory and records, and execution ledger without
following symlinks. Protected entries must have the expected real file or
directory type, be owned by the current user, have no group- or other-write
bit, and have no POSIX access ACL; protected directories must also have no
default ACL. Protected regular files must have exactly one hard link. Failure
or inability to inspect the metadata blocks publication or launch.

Live execution never changes permissions, removes ACLs, rewrites witnesses,
or otherwise repairs unsafe state. A checkout created under a permissive umask
is discarded. Offline metadata normalization is not part of this protocol.
Root and same-UID tampering remain outside the guarantee, consistent with the
amendment-003 threat boundary.

## Eligibility pause and regression evidence

After each confirmatory attempt, the runner durably appends and validates its
ledger row. A newly analysis-ineligible primary or reserve stops that
invocation before another target process can launch. Primary execution may
resume only after an explicit frozen-order reserve chain ends in an eligible
attempt. Smoke remains exempt because its outputs are intentionally excluded
from analysis.

Synthetic live-loop tests must prove that an ineligible primary permits
exactly one mocked `Popen`, an ineligible reserve leaves later primaries
blocked, an eligible reserve permits the next frozen primary, and an
analysis-ineligible smoke result does not itself stop the frozen Kimi-to-Claude
suffix. Separate tests cover permission, ACL, symlink, hard-link, partial-row,
manifest-path, current-ledger, witness-union, and call-budget failures.

## Freeze and review boundary

Pre-freeze engineering reviews may identify defects while source, tests,
documents, or manifests are still incomplete; their findings must be recorded
before publication. The formal amendment-004 smoke gate begins only after the
corrected source, tests, this amendment, its runbook, and both manifests are
committed and an exact candidate commit is declared for review. Two separate
fresh-context reviewers must approve that exact commit. Any blocker after that
declaration requires amendment 005 and new bout directories; amendment 004
must not then be rewritten.
