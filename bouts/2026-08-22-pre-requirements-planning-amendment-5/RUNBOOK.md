# Amendment-005 Kimi replacement runbook

This runbook supplements the base design and Amendments 001 through 005.
Every earlier manifest and runtime artifact is immutable. Do not inspect target
response semantics or retry the Amendment-004 Kimi attempt.

## Freeze and validation

Use a fresh independent local clone beneath an owner-only temporary directory,
with `umask 0077`, no linked worktree, and no hard-linked Git objects. Build the
replacement manifest only after the Amendment-005 source and documents are
committed:

```bash
umask 077
python3 bin/plan_experiment.py manifest \
  --phase smoke \
  --output bouts/2026-08-22-pre-requirements-planning-smoke-amendment-5/MANIFEST.json \
  --bout-dir bouts/2026-08-22-pre-requirements-planning-smoke-amendment-5 \
  --smoke-replacement-from bouts/2026-08-22-pre-requirements-planning-smoke-amendment-4/MANIFEST.json \
  --design bouts/2026-08-22-pre-requirements-planning/DESIGN.md \
  --analysis-script analysis/2026-08-22-pre-requirements-planning/analyze.py \
  --report-template analysis/2026-08-22-pre-requirements-planning/REPORT_TEMPLATE.md \
  --runs 1 --reserves 0 --seed 2808242028 \
  --frozen-at 2026-08-24T02:05:49Z
python3 bin/plan_experiment.py validate bouts/2026-08-22-pre-requirements-planning-smoke-amendment-5/MANIFEST.json
```

Reproduce the manifest independently in a second secure clone and compare
complete bytes. Run the synthetic harness, served-model checks, summary checks,
graders, lint, shell syntax, compilation, Git integrity, and all three
aggregate credential scans. Do not run a target during validation.

## Independent review gate

Two fresh-context reviewers must approve the exact committed candidate. Reviews
must be offline and must not access credentials, targets, APIs, network, raw
responses, wire payloads, policy values, or semantic output. Any blocker requires
another amendment; Amendment 005 must not be rewritten after declaration.

## One authorized replacement call

After both approvals and explicit user approval, run exactly once:

```bash
umask 077
export ARENA_CLAUDE_HOME=/absolute/path/outside/repository/claude-home
export ARENA_CODEX_HOME=/absolute/path/outside/repository/codex-home
export ARENA_KIMI_HOME=/absolute/path/outside/repository/kimi-home
export PYTHONDONTWRITEBYTECODE=1
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning-smoke-amendment-5/MANIFEST.json \
  --approval 3834461fcbf1760ffe138aff14d5fd99324085346e65e028ed136918acff0da4
```

Never retry, resume, or manually invoke Claude. Preserve all raw artifacts,
claims, intents, and the execution ledger. Inspect only the response-free
`smoke-status` view and deterministic `verify-run`/manifest validation. The
replacement remains excluded from semantic analysis regardless of outcome.

The paid confirmatory matrix remains forbidden until separately approved.
