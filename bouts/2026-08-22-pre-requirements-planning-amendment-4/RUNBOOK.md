# Amended frozen experiment runbook (technical amendment 004)

Read the base design and technical amendments 001 through 004 together.
Every earlier manifest, amendment, ledger, intent, and run artifact is
immutable. Amendment 003 has no manifest and made no target call.

## Secure exact-commit checkout

Manifest creation, no-API preflight, live execution, and technical status
inspection use a fresh independent local clone beneath an owner-only temporary
directory. Do not use a checkout materialized under the ordinary `0002` umask,
do not normalize an existing bout in place, and do not use a linked worktree
whose Git common directory is outside the protected root.

```bash
umask 077
arena_a4_root="$(mktemp -d /tmp/agent-arena-plan-a4.XXXXXX)"
chmod 700 "$arena_a4_root"
git clone --no-local <SOURCE_REPOSITORY_PATH> "$arena_a4_root/repository"
cd "$arena_a4_root/repository"
git switch --detach <EXACT_COMMITTED_CANDIDATE>
test "$(umask)" = "0077"
git status --porcelain=v1
```

Require empty status output. Keep `umask 0077` for every command below. The
harness performs its own no-follow ownership, mode, ACL, and witness checks;
it never repairs an unsafe checkout. Remove the isolated clone only after its
needed commits and artifacts have been preserved.

## Reproduce the amendment-004 freezes

Run these commands only after the corrected source, tests, amendment, and
runbook are committed, from an exact checkout where both destinations are
absent:

```bash
python3 bin/plan_experiment.py manifest --phase confirmatory --output bouts/2026-08-22-pre-requirements-planning-amendment-4/MANIFEST.json --bout-dir bouts/2026-08-22-pre-requirements-planning-amendment-4 --design bouts/2026-08-22-pre-requirements-planning/DESIGN.md --analysis-script analysis/2026-08-22-pre-requirements-planning/analyze.py --report-template analysis/2026-08-22-pre-requirements-planning/REPORT_TEMPLATE.md --runs 20 --reserves 5 --seed 2808222026 --frozen-at 2026-08-23T23:40:00Z
python3 bin/plan_experiment.py manifest --phase smoke --output bouts/2026-08-22-pre-requirements-planning-smoke-amendment-4/MANIFEST.json --bout-dir bouts/2026-08-22-pre-requirements-planning-smoke-amendment-4 --smoke-continuation-from bouts/2026-08-22-pre-requirements-planning-smoke/MANIFEST.json --design bouts/2026-08-22-pre-requirements-planning/DESIGN.md --analysis-script analysis/2026-08-22-pre-requirements-planning/analyze.py --report-template analysis/2026-08-22-pre-requirements-planning/REPORT_TEMPLATE.md --runs 1 --reserves 0 --seed 2808222027 --frozen-at 2026-08-23T23:40:00Z
```

Publication is atomic and no-clobber. Reproduce each file from the exact
pre-manifest commit in another secure clone, then compare its complete bytes
with the committed manifest.

## Offline validation

```bash
python3 bin/plan_experiment.py validate bouts/2026-08-22-pre-requirements-planning-amendment-4/MANIFEST.json
python3 bin/plan_experiment.py validate bouts/2026-08-22-pre-requirements-planning-smoke-amendment-4/MANIFEST.json
ARENA_SYNTHETIC_ONLY=1 python3 bin/test_plan_experiment.py
ARENA_SYNTHETIC_ONLY=1 python3 bin/test_served_model.py
python3 bin/test_summarize_integrity.py
bin/check-graders.sh
ruff check bin/plan_experiment.py bin/credential_guard.py bin/test_plan_experiment.py bin/test_served_model.py bin/metrics.py bin/metrics_codex.py bin/metrics_kimi.py analysis/2026-08-22-pre-requirements-planning/analyze.py
bash -n bin/run-task.sh bin/run-task-codex.sh bin/run-task-kimi.sh
git diff --check
git fsck --no-reflogs
```

The synthetic suite must prove strict umask and ACL rejection; lexical
manifest publication; strict no-follow ledger reads in every consumer;
fresh-filesystem launch authorization; three-witness durability and union
accounting; the inherited three-call smoke cap; and the live primary, reserve,
and smoke flow cases specified by the amendment.

Run aggregate credential scans for all three exact external source homes
against the whole repository and require zero leaks, unsafe entries, and
symlinks. Then configure those source-home variables exactly as in the base
runbook and run both no-API gates from the exact clean committed tree:

```bash
python3 bin/plan_experiment.py preflight bouts/2026-08-22-pre-requirements-planning-amendment-4/MANIFEST.json
python3 bin/plan_experiment.py preflight bouts/2026-08-22-pre-requirements-planning-smoke-amendment-4/MANIFEST.json
```

## Formal independent review gate

After both manifests are committed, declare one exact amendment-004 candidate
commit. Two separate fresh-context reviewers must approve it: one for protocol
and reproducibility and one for security and adversarial safety. Reviews are
offline and may not call targets, inspect response semantics, or access
credentials. A blocker after declaration requires amendment 005 and new bout
directories; do not rewrite amendment 004.

## The two remaining excluded smoke calls

Only after both approvals, run the frozen Kimi-then-Claude suffix once:

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning-smoke-amendment-4/MANIFEST.json
```

The cumulative maximum remains three calls: the immutable initial Codex call
plus at most these two calls. Never retry a failed, uncertain, claimed, or
unresolved slot. Preserve the claim journal, intent files, ledger, and raw
artifacts. Do not open response text, broad metrics, or configuration objects.
Use only these response-free technical views:

```bash
python3 bin/plan_experiment.py smoke-status bouts/2026-08-22-pre-requirements-planning-smoke/MANIFEST.json --historical
python3 bin/plan_experiment.py smoke-status bouts/2026-08-22-pre-requirements-planning-smoke-amendment-4/MANIFEST.json
```

The excluded-smoke evidence and handoff must disclose the initial accidental
display of the Codex response and instruction-policy value.

## Confirmatory dry run and approval lock

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning-amendment-4/MANIFEST.json --dry-run
jq -r .freeze_id bouts/2026-08-22-pre-requirements-planning-amendment-4/MANIFEST.json
```

Confirmatory execution remains forbidden until the user explicitly approves
that exact committed amendment-004 freeze ID. Only after approval may it be
passed through `--approval`.

If a primary is newly ineligible, the command stops after preserving its
ledger row. Run only the next frozen reserve explicitly:

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning-amendment-4/MANIFEST.json \
  --approval <APPROVED_AMENDMENT_004_FREEZE_ID> \
  --reserve <NEXT_FROZEN_RESERVE_SLOT_ID> \
  --replacement-for <INELIGIBLE_PRIMARY_OR_RESERVE_SLOT_ID> \
  --exclusion-reason <SUPPORTED_PREREGISTERED_REASON>
```

An ineligible reserve pauses again. Resume primary execution only after its
effective replacement chain ends in an eligible attempt. Any unresolved
claim, intent, or ledger state blocks execution and requires a separately
frozen amendment; it is never repaired or retried.

Do not merge, deploy, or run the paid confirmatory matrix as part of this work.
