# Frozen experiment runbook

All commands run from the Agent Arena repository root. The confirmatory command
is intentionally blocked until explicit user approval of the exact manifest
freeze ID. Do not edit the prompt, rubric, design, manifest, or analyzer between
approval and execution.

## Reproduce the manifests before any run

These commands deterministically reconstruct the current draft manifests from
the frozen sources. `--replace-draft` is explicit and is rejected once any
execution ledger or run artifact exists.

```bash
python3 bin/plan_experiment.py manifest --phase confirmatory --output bouts/2026-08-22-pre-requirements-planning/MANIFEST.json --design bouts/2026-08-22-pre-requirements-planning/DESIGN.md --analysis-script analysis/2026-08-22-pre-requirements-planning/analyze.py --report-template analysis/2026-08-22-pre-requirements-planning/REPORT_TEMPLATE.md --runs 20 --reserves 5 --seed 2808222026 --frozen-at 2026-08-22T18:00:00Z --replace-draft
python3 bin/plan_experiment.py manifest --phase smoke --output bouts/2026-08-22-pre-requirements-planning-smoke/MANIFEST.json --design bouts/2026-08-22-pre-requirements-planning/DESIGN.md --analysis-script analysis/2026-08-22-pre-requirements-planning/analyze.py --report-template analysis/2026-08-22-pre-requirements-planning/REPORT_TEMPLATE.md --runs 1 --reserves 0 --seed 2808222027 --frozen-at 2026-08-22T18:00:00Z --replace-draft
```

## Validate the frozen package

```bash
python3 bin/plan_experiment.py validate bouts/2026-08-22-pre-requirements-planning/MANIFEST.json
python3 bin/plan_experiment.py validate bouts/2026-08-22-pre-requirements-planning-smoke/MANIFEST.json
ARENA_SYNTHETIC_ONLY=1 python3 bin/test_plan_experiment.py
ARENA_SYNTHETIC_ONLY=1 python3 bin/test_served_model.py
python3 bin/test_summarize_integrity.py
bin/check-graders.sh
ruff check bin/plan_experiment.py bin/credential_guard.py bin/test_plan_experiment.py bin/test_served_model.py bin/metrics.py bin/metrics_codex.py bin/metrics_kimi.py analysis/2026-08-22-pre-requirements-planning/analyze.py
bash -n bin/run-task.sh bin/run-task-codex.sh bin/run-task-kimi.sh
git diff --check
```

The three authentication/config source homes must be outside the published
worktree. Export their paths only in the operator shell. Secret contents and
paths are never recorded; their schemas, recognized-field counts, and redacted
structural inventories are frozen in `CONFIGURATION.json`.

```bash
export ARENA_CLAUDE_HOME=/absolute/path/outside/repository/to/auth-only-claude-home
export ARENA_CODEX_HOME=/absolute/path/outside/repository/to/auth-only-codex-home
export ARENA_KIMI_HOME=/absolute/path/outside/repository/to/config-only-kimi-home
```

The Claude source contains exactly `.credentials.json`; the Codex source
exactly `auth.json`; and the Kimi source exactly `.kimi-code/config.toml` plus
that parent directory. No source may contain a symlink or extra entry. Each
slot copies its allowlisted file into a new `0700` runtime home. Run the explicit
no-API gate after committing the frozen package:

```bash
python3 bin/plan_experiment.py preflight bouts/2026-08-22-pre-requirements-planning/MANIFEST.json
python3 bin/plan_experiment.py preflight bouts/2026-08-22-pre-requirements-planning-smoke/MANIFEST.json
```

The executor repeats the same preflight before every slot and refuses tracked
worktree/index changes. Preflight also requires the recorded delegated
cgroup-v2 parent, `cgroup.kill`, and Linux child-subreaper support; no target
starts if either containment layer is unavailable.

## Excluded smoke only

Do not enter this gate until two fresh independent reviewers approve the exact
clean committed candidate. The command below then makes exactly three target
calls—one frozen smoke slot per condition—and no retries. Preserve outputs and
technical traces, but do not read or semantically score the smoke response text.

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning-smoke/MANIFEST.json
```

Inspect only transport/integrity fields in each `run_record.json`, then verify
every smoke directory with:

```bash
python3 bin/plan_experiment.py verify-run bouts/2026-08-22-pre-requirements-planning-smoke/16-pre-requirements-plan/claude-opus-5/run-1
python3 bin/plan_experiment.py verify-run bouts/2026-08-22-pre-requirements-planning-smoke/16-pre-requirements-plan/gpt-5.6-sol-codex/run-1
python3 bin/plan_experiment.py verify-run bouts/2026-08-22-pre-requirements-planning-smoke/16-pre-requirements-plan/kimi-k3-kimicode/run-1
```

## Confirmatory dry run (no API calls)

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning/MANIFEST.json --dry-run
```

## Confirmatory execution (forbidden before approval)

After the user explicitly approves the frozen design, substitute the exact
committed `freeze_id` below. The runner rejects a missing or different value.

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning/MANIFEST.json --approval 65d952383df9b167dae3104e9bc33c30b864bf28f2b258353bdc85c34c8ad32e
```

After an operator interruption, rerun the same command: the ledger must be a
prefix of the frozen order and the runner resumes at the next primary. It will
refuse to continue past an objectively ineligible attempt until its linked
reserve chain ends in an eligible attempt. It also refuses all later calls when
process-scope cleanup is unproven or an external staging path remains retained;
recover the external state manually, then document and freeze an amendment
rather than editing the append-only ledger.

Do not run reserves with the primary schedule. Record an objective invalidation
and explicit reserve linkage first; the requested reason must appear in that
attempt's `eligible_exclusion_reasons`. If a reserve is also ineligible, link the
next reserve to that failed reserve. If all five reserves for a condition are
exhausted, stop and amend.

One reserve is run explicitly and only for an ineligible primary of the same
condition. Use identifiers and one exact reason from `replace_only` in the
manifest:

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning/MANIFEST.json \
  --approval 65d952383df9b167dae3104e9bc33c30b864bf28f2b258353bdc85c34c8ad32e \
  --reserve [frozen-reserve-slot-id] \
  --replacement-for [ineligible-primary-or-reserve-attempt-id] \
  --exclusion-reason [preregistered-reason]
```

## Blind and analyze after the complete matrix

Set a fresh secret blinding key. Preserve the generated mapping for audit but
withhold it from both semantic reviewers until their independent reviews are
locked.

```bash
export ARENA_BLIND_KEY=[fresh-random-value-of-at-least-32-bytes]
python3 bin/plan_experiment.py blind bouts/2026-08-22-pre-requirements-planning/MANIFEST.json --output-dir analysis/2026-08-22-pre-requirements-planning/blinded
```

Give semantic reviewers only `blinded/reviewer/review-packets.json` and the
hidden rubric; keep the `0600` `blinded/custodian/blind-map.json`, manifest
schedule, and repository access with the mapping custodian. Copy the
reviewer/adjudication templates to append-only working files, obtain reciprocal
independence declarations, and code instruction exposure before revealing the
mapping. Then generate the no-clobber output bundle together:

```bash
python3 analysis/2026-08-22-pre-requirements-planning/analyze.py \
  --manifest bouts/2026-08-22-pre-requirements-planning/MANIFEST.json \
  --packets analysis/2026-08-22-pre-requirements-planning/blinded/reviewer/review-packets.json \
  --blind-map analysis/2026-08-22-pre-requirements-planning/blinded/custodian/blind-map.json \
  --reviewer-a analysis/2026-08-22-pre-requirements-planning/reviewer-a.json \
  --reviewer-b analysis/2026-08-22-pre-requirements-planning/reviewer-b.json \
  --adjudications analysis/2026-08-22-pre-requirements-planning/adjudications.json \
  --instruction-exposure analysis/2026-08-22-pre-requirements-planning/instruction-exposure.json \
  --output-json analysis/2026-08-22-pre-requirements-planning/analysis.json \
  --output-report analysis/2026-08-22-pre-requirements-planning/REPORT.md \
  --output-manifest analysis/2026-08-22-pre-requirements-planning/ANALYSIS_MANIFEST.json
```
