#!/usr/bin/env python3
"""Frozen-manifest runner and observable-evidence tooling for task 16.

The experiment measures final-answer and trace behavior. It never reads or
scores hidden reasoning. Raw driver artifacts remain untouched; normalized
artifacts are content-addressed derivatives.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import hmac
import itertools
import json
import os
import random
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import credential_guard


ROOT = Path(__file__).resolve().parent.parent
SAFE_TEMP_ROOT = Path("/tmp")
STAGED_DRIVER_FILES = {
    "claude": (
        "bin/run-task.sh",
        "bin/credential_guard.py",
        "bin/metrics.py",
        "bin/served_model.py",
        "env/prices.json",
    ),
    "codex": (
        "bin/run-task-codex.sh",
        "bin/credential_guard.py",
        "bin/metrics_codex.py",
        "env/prices.json",
    ),
    "kimi": (
        "bin/run-task-kimi.sh",
        "bin/credential_guard.py",
        "bin/metrics_kimi.py",
        "env/prices.json",
    ),
}
TASK_REL = "tasks/16-pre-requirements-plan"
PROMPT_REL = f"{TASK_REL}/PROMPT.md"
FROZEN_PROMPT_SHA256 = "5d8df8bce37fba5832273d20f99d4ef05abd87c3590be62ceed349e90f3da2b0"
EXPERIMENT_ID = "2026-08-22-pre-requirements-planning"
CONFIG_LOCK_REL = f"bouts/{EXPERIMENT_ID}/CONFIGURATION.json"
FROZEN_CORE_RELATIVE = [
    PROMPT_REL,
    f"{TASK_REL}/SCORING.md",
    f"{TASK_REL}/review.schema.json",
    f"{TASK_REL}/adjudication.schema.json",
    f"bouts/{EXPERIMENT_ID}/DESIGN.md",
    CONFIG_LOCK_REL,
    f"analysis/{EXPERIMENT_ID}/analyze.py",
    f"analysis/{EXPERIMENT_ID}/REPORT_TEMPLATE.md",
    f"analysis/{EXPERIMENT_ID}/adjudications.template.json",
    f"analysis/{EXPERIMENT_ID}/instruction-exposure.template.json",
    f"analysis/{EXPERIMENT_ID}/reviewer-a.template.json",
    f"analysis/{EXPERIMENT_ID}/reviewer-b.template.json",
    "bin/plan_experiment.py",
    "bin/credential_guard.py",
    "bin/run-task.sh",
    "bin/run-task-codex.sh",
    "bin/run-task-kimi.sh",
    "bin/metrics.py",
    "bin/metrics_codex.py",
    "bin/metrics_kimi.py",
    "bin/served_model.py",
    "env/prices.json",
]
RAW_ARTIFACTS = {
    "claude": ["transcript.jsonl", "result.json"],
    "codex": ["transcript.jsonl", "last_message.txt", "session.jsonl"],
    "kimi": ["transcript.jsonl", "wire.jsonl"],
}
COMMON_ARTIFACTS = [
    "agent_exit",
    "credential_scan.raw.json",
    "credential_scan.runtime.json",
    "metrics.json",
    "peek_check",
    "prompt.txt",
    "run_env.json",
    "stderr.log",
    "target_returned",
    "target_started",
    "wall_seconds",
    "workspace.diff",
    "workspace.diffstat",
]
DERIVED_ARTIFACTS = [
    "credential_scan.json",
    "final_output.txt",
    "embargo.json",
    "instruction_context.json",
    "run_record.json",
]
OBSERVER_ARTIFACTS = ["final_output.txt", "embargo.json", "instruction_context.json", "run_record.json"]
CLAUDE_TOP_LEVEL_EVENTS = {"assistant", "result", "system", "user"}
CLAUDE_SYSTEM_SUBTYPES = {"init"}
CLAUDE_PASSIVE_BLOCKS = {"redacted_thinking", "text", "thinking"}
CLAUDE_ACTION_BLOCKS = {"mcp_tool_use", "server_tool_use", "tool_use"}
CODEX_TOP_LEVEL_EVENTS = {
    "error",
    "item.completed",
    "item.started",
    "item.updated",
    "thread.started",
    "turn.completed",
    "turn.failed",
    "turn.started",
}
PASSIVE_CODEX_ITEMS = {"agent_message", "error", "plan", "reasoning"}
ACTIVE_CODEX_ITEMS = {
    "collab_agent_tool_call",
    "command_execution",
    "computer_call",
    "file_change",
    "image_generation",
    "mcp_tool_call",
    "todo_list",
    "web_search",
}
CALL_SESSION_TYPES = {
    "computer_call",
    "custom_tool_call",
    "function_call",
    "local_shell_call",
    "mcp_tool_call",
    "web_search_call",
}
PASSIVE_SESSION_RESPONSE_TYPES = {
    "message",
    "reasoning",
}
CODEX_SESSION_RESULT_TYPES = {
    "computer_call_output",
    "custom_tool_call_output",
    "function_call_output",
    "local_shell_call_output",
    "mcp_tool_call_output",
    "web_search_call_output",
}
CODEX_SESSION_TOP_LEVEL_EVENTS = {
    "event_msg",
    "response_item",
    "session_meta",
    "turn_context",
    "world_state",
}
PASSIVE_CODEX_EVENT_MESSAGES = {
    "agent_message",
    "agent_reasoning",
    "context_compacted",
    "stream_error",
    "task_complete",
    "task_started",
    "token_count",
    "turn_aborted",
    "user_message",
    "warning",
}
ACTIVE_CODEX_EVENT_MESSAGES = {
    "collab_agent_spawn_begin",
    "collab_agent_spawn_end",
    "exec_command_begin",
    "mcp_tool_call_begin",
    "web_search_begin",
}
KIMI_TRANSCRIPT_TYPES = {"error", "result", "session.resume_hint"}
KIMI_TRANSCRIPT_ROLES = {"assistant", "system", "tool", "user"}
KIMI_WIRE_PASSIVE_TYPES = {
    "config.update",
    "context.append_message",
    "llm.request",
    "llm.response",
    "llm.tools_snapshot",
    "session.create",
    "session.update",
    "tools.set_active_tools",
    "usage.record",
}
KIMI_WIRE_LOOP_PASSIVE_TYPES = {
    "assistant.message",
    "assistant.reasoning",
    "step.begin",
    "step.end",
    "user.message",
}
CREDENTIAL_RECEIPT_FIELDS = {
    "schema_version",
    "driver",
    "source_schema",
    "source_redacted_structural_inventory_sha256",
    "credential_pattern_count",
    "scanned_entry_count",
    "scanned_path_bytes",
    "scanned_regular_and_symlink_bytes",
    "leak_match_count",
    "unsafe_special_entry_count",
    "escaping_symlink_count",
    "pass",
}


class SecretLeakError(RuntimeError):
    """Raised before normalization when a driver marks publishable evidence unsafe."""


class OperatorTermination(KeyboardInterrupt):
    """Raised when an external signal interrupts an active driver attempt."""

    def __init__(self, signum: int):
        self.signum = signum
        super().__init__(f"operator termination signal {signum}")


def process_dumpable(value: int | None = None) -> int:
    """Get or set Linux dumpability so a target cannot read the runner's cwd, fds, or environment."""
    libc = ctypes.CDLL(None, use_errno=True)
    operation = 3 if value is None else 4  # PR_GET_DUMPABLE / PR_SET_DUMPABLE
    result = libc.prctl(operation, 0 if value is None else value, 0, 0, 0)
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return result


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def file_record(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": relative(path), "sha256": sha256_bytes(data), "bytes": len(data)}


def default_conditions() -> list[dict[str, Any]]:
    """The convenience sample frozen for this experiment."""
    return [
        {
            "condition_id": "claude-code--claude-opus-5",
            "driver": "claude",
            "requested_model": "claude-opus-5",
            "model_argument": "claude-opus-5",
            "output_label": "claude-opus-5",
            "expected_model_identities": ["claude-opus-5"],
            "expected_cli_version": "2.1.241 (Claude Code)",
            "expected_base_url": "https://api.anthropic.com",
            "model_env_expected": "absent",
            "effort": {"mode": "native_default", "cli_argument": None, "observed_value": "not_exposed"},
            "expected_effort_record": "native-default (flag omitted)",
            "expected_setting_sources": "project (fresh auth-only per-run home)",
            "instruction_configuration": "fresh auth-only per-run home; project setting source in a neutral scratch repository",
            "instruction_text_observability": "partial",
            "tool_configuration": "native default tools enabled",
        },
        {
            "condition_id": "codex--gpt-5.6-sol",
            "driver": "codex",
            "requested_model": "gpt-5.6-sol",
            "model_argument": "gpt-5.6-sol",
            "output_label": "gpt-5.6-sol-codex",
            "expected_model_identities": ["gpt-5.6-sol"],
            "expected_cli_version": "codex-cli 0.149.0",
            "expected_base_url": "https://api.openai.com (native)",
            "effort": {"mode": "native_default", "cli_argument": None, "observed_value": "not_exposed"},
            "expected_effort_record": "codex-default",
            "expected_setting_sources": "none (--ignore-user-config, --ignore-rules, fresh auth-only HOME/CODEX_HOME)",
            "instruction_configuration": "fresh auth-only per-run HOME/CODEX_HOME with user config and rules disabled",
            "instruction_text_observability": "partial",
            "tool_configuration": "native default tools enabled; schemas opaque unless present in session rollout",
        },
        {
            "condition_id": "kimi-code--kimi-k3",
            "driver": "kimi",
            "requested_model": "kimi-k3",
            "model_argument": "arena/k3",
            "output_label": "kimi-k3-kimicode",
            "expected_model_identities": ["kimi-k3"],
            "expected_cli_version": "kimi-code 0.27.0",
            "expected_base_url": "https://api.moonshot.ai/v1 (platform, metered)",
            "effort": {"mode": "native_default", "cli_argument": None, "observed_value": "max"},
            "expected_effort_record": "native-default (observed in wire journal)",
            "expected_setting_sources": "arena config.toml plus explicit empty skills directory",
            "instruction_configuration": "fresh per-run HOME copied from an exact config-only source; skills discovery overridden empty",
            "instruction_text_observability": "complete",
            "tool_configuration": "native default tools enabled",
        },
    ]


def _balanced_orders(condition_ids: list[str], repeats: int, seed: int) -> list[tuple[str, ...]]:
    """Return randomized complete-block orders with near-perfect position balance."""
    if repeats < 1:
        raise ValueError("repeats must be positive")
    permutations = list(itertools.permutations(condition_ids))
    quotient, remainder = divmod(repeats, len(permutations))
    orders = permutations * quotient
    if remainder:
        base = len(permutations) // len(condition_ids)
        best: list[tuple[tuple[str, ...], ...]] = []
        best_spread: int | None = None
        for candidate in itertools.combinations(permutations, remainder):
            counts = {cid: [base * quotient] * len(condition_ids) for cid in condition_ids}
            for order in candidate:
                for position, cid in enumerate(order):
                    counts[cid][position] += 1
            spread = max(max(v) - min(v) for v in counts.values())
            if best_spread is None or spread < best_spread:
                best_spread, best = spread, [candidate]
            elif spread == best_spread:
                best.append(candidate)
        chooser = random.Random(seed ^ 0xA53C91)
        orders.extend(chooser.choice(best))
    random.Random(seed).shuffle(orders)
    return orders


def build_manifest(
    *,
    phase: str,
    output: Path,
    design: Path,
    analysis_script: Path,
    report_template: Path,
    repeats: int,
    seed: int,
    frozen_at: str,
    reserve_per_condition: int = 5,
    replace_draft: bool = False,
) -> dict[str, Any]:
    if phase not in {"smoke", "confirmatory"}:
        raise ValueError("phase must be smoke or confirmatory")
    if phase == "confirmatory" and repeats < 10:
        raise ValueError("confirmatory manifests require at least 10 runs per condition")
    prompt = ROOT / PROMPT_REL
    if sha256_path(prompt) != FROZEN_PROMPT_SHA256:
        raise ValueError("target prompt differs from the frozen exact prompt")
    conditions = default_conditions()
    condition_ids = [c["condition_id"] for c in conditions]
    orders = _balanced_orders(condition_ids, repeats, seed)
    schedule: list[dict[str, Any]] = []
    sequence = 0
    for block, order in enumerate(orders, start=1):
        for position, condition_id in enumerate(order, start=1):
            sequence += 1
            schedule.append(
                {
                    "slot_id": f"primary-{block:02d}--{condition_id}",
                    "kind": "primary",
                    "block": block,
                    "position": position,
                    "sequence": sequence,
                    "replicate": block,
                    "condition_id": condition_id,
                }
            )
    reserves: list[dict[str, Any]] = []
    if phase == "confirmatory":
        for condition_id in condition_ids:
            for index in range(1, reserve_per_condition + 1):
                reserves.append(
                    {
                        "slot_id": f"reserve-{index:02d}--{condition_id}",
                        "kind": "reserve",
                        "reserve_index": index,
                        "replicate": repeats + index,
                        "condition_id": condition_id,
                        "replacement_for": None,
                    }
                )
    fixture_dir = ROOT / TASK_REL / "fixture"
    fixture_files = sorted(path for path in fixture_dir.rglob("*") if path.is_file())
    expected_fixture_path = (fixture_dir / ".gitkeep").resolve()
    if [path.resolve() for path in fixture_files] != [expected_fixture_path]:
        raise ValueError("neutral fixture must contain exactly its .gitkeep marker")
    supplied_core = {design.resolve(), analysis_script.resolve(), report_template.resolve()}
    expected_supplied = {
        (ROOT / f"bouts/{EXPERIMENT_ID}/DESIGN.md").resolve(),
        (ROOT / f"analysis/{EXPERIMENT_ID}/analyze.py").resolve(),
        (ROOT / f"analysis/{EXPERIMENT_ID}/REPORT_TEMPLATE.md").resolve(),
    }
    if supplied_core != expected_supplied:
        raise ValueError("manifest inputs must use the experiment's canonical design/analyzer/report paths")
    frozen_files = [*(ROOT / path for path in FROZEN_CORE_RELATIVE), *fixture_files]
    missing = [str(path) for path in frozen_files if not path.is_file()]
    if missing:
        raise ValueError(f"missing frozen input files: {missing}")
    bout_dir = f"bouts/{EXPERIMENT_ID}{'-smoke' if phase == 'smoke' else ''}"
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "phase": phase,
        "status": "excluded-smoke" if phase == "smoke" else "frozen-awaiting-explicit-user-approval",
        "frozen_at": frozen_at,
        "amendments": [],
        "bout_dir": bout_dir,
        "task": {
            "path": TASK_REL,
            "target_prompt": prompt.read_text(),
            "prompt_sha256": sha256_path(prompt),
            "prompt_bytes": prompt.stat().st_size,
            "compatibility_amendments": [],
            "fixture_inventory": [file_record(path) for path in fixture_files],
            "setup_script": None,
        },
        "conditions": conditions,
        "sampling": {
            "valid_runs_per_condition": repeats,
            "fresh_process_and_session_per_slot": True,
            "serial_execution": True,
            "smoke_excluded_from_confirmatory": True,
            "reserve_slots_per_condition": reserve_per_condition if phase == "confirmatory" else 0,
            "adaptive_stopping": False,
        },
        "randomization": {
            "algorithm": "Python random.Random MT19937; complete blocks; position-balanced permutation selection",
            "seed": seed,
            "unit": "within-replicate condition order",
        },
        "schedule": schedule,
        "reserve_slots": reserves,
        "exclusions": {
            "replace_only": [
                "transport_or_service_failure_before_request_acceptance",
                "harness_crash_before_target_execution",
                "prompt_hash_mismatch",
                "wrong_model_or_frozen_configuration",
                "corrupted_or_missing_raw_artifact_due_to_harness",
                "external_termination_before_attributable_target_completion",
                "security_quarantine_after_secret_scan",
            ],
            "never_exclude": [
                "tool_or_subagent_call",
                "refusal_or_empty_target_output",
                "question_or_non_outline_prose",
                "invented_requirement_or_implementation_content",
                "normal_truncation",
                "target_driven_tool_loop_or_timeout",
            ],
        },
        "analysis": {
            "semantic_reviewers": 2,
            "third_adjudicator_for_every_disagreement": True,
            "primary_endpoints": [
                "A_ge_2",
                "B_ge_2",
                "C_eq_3",
                "D_ge_2",
                "full_gate_chain",
                "restraint_pass",
                "embargo_pass",
                "format_pass",
                "full_compliance",
            ],
            "interval": "two-sided 95% Wilson score interval",
            "embargo_clean_semantic_sensitivity": True,
            "no_omnibus_score_or_confirmatory_pairwise_ranking": True,
            "hidden_reasoning_scored": False,
        },
        "artifact_contract": {
            "raw_outputs_immutable": True,
            "required_common": COMMON_ARTIFACTS,
            "required_by_driver": RAW_ARTIFACTS,
            "derived": [*DERIVED_ARTIFACTS, "artifact_manifest.json"],
        },
        "frozen_inputs": [file_record(path) for path in frozen_files],
    }
    manifest["freeze_id"] = sha256_bytes(canonical_json(manifest))
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or output.is_symlink():
        if not replace_draft:
            raise FileExistsError(f"refusing to overwrite frozen manifest: {output}")
        if output.is_symlink() or not output.is_file():
            raise ValueError(f"draft manifest replacement target is unsafe: {output}")
        try:
            prior = load_json(output)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"draft manifest replacement target is unreadable: {type(exc).__name__}") from exc
        if prior.get("experiment_id") != EXPERIMENT_ID or prior.get("phase") != phase:
            raise ValueError("draft manifest replacement target belongs to a different experiment or phase")
        prior_bout = ROOT / str(prior.get("bout_dir", ""))
        runtime_paths = (
            prior_bout / "EXECUTION.jsonl",
            prior_bout / "ATTEMPT_FAILURES",
            prior_bout / "QUARANTINE",
            prior_bout / Path(TASK_REL).name,
        )
        if any(path.exists() or path.is_symlink() for path in runtime_paths):
            raise ValueError("refusing to replace a manifest after any run artifact or ledger exists")
    output.write_bytes(json.dumps(manifest, indent=2, ensure_ascii=False).encode() + b"\n")
    return manifest


def condition_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {condition["condition_id"]: condition for condition in manifest["conditions"]}


def compute_freeze_id(manifest: dict[str, Any]) -> str:
    clone = dict(manifest)
    clone.pop("freeze_id", None)
    return sha256_bytes(canonical_json(clone))


def validate_manifest(manifest: dict[str, Any], *, check_files: bool = True) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1:
        errors.append("unsupported manifest schema")
    phase = manifest.get("phase")
    if phase not in {"smoke", "confirmatory"}:
        errors.append("invalid phase")
    if manifest.get("freeze_id") != compute_freeze_id(manifest):
        errors.append("freeze_id does not match manifest content")
    task = manifest.get("task") or {}
    prompt_path = ROOT / str(task.get("path", "")) / "PROMPT.md"
    if task.get("prompt_sha256") != FROZEN_PROMPT_SHA256:
        errors.append("manifest prompt hash is not the frozen target hash")
    if task.get("compatibility_amendments") != []:
        errors.append("target-prompt amendment present; freeze a new design version before running")
    if task.get("setup_script") is not None:
        errors.append("neutral response-only task must not have a setup script")
    if check_files:
        if not prompt_path.is_file():
            errors.append("target prompt file missing")
        else:
            data = prompt_path.read_bytes()
            if sha256_bytes(data) != task.get("prompt_sha256"):
                errors.append("target prompt file hash mismatch")
            if data.decode() != task.get("target_prompt"):
                errors.append("manifest target prompt text mismatch")
        frozen_records = manifest.get("frozen_inputs") or []
        frozen_paths = [rec.get("path") for rec in frozen_records if isinstance(rec, dict)]
        expected_frozen_paths = set(FROZEN_CORE_RELATIVE) | {
            item.get("path") for item in task.get("fixture_inventory") or [] if isinstance(item, dict)
        }
        if len(frozen_paths) != len(set(frozen_paths)) or set(frozen_paths) != expected_frozen_paths:
            errors.append("frozen input inventory differs from the required treatment surface")
        for rec in frozen_records:
            if not isinstance(rec, dict):
                errors.append("malformed frozen input record")
                continue
            path = ROOT / rec.get("path", "")
            if not path.is_file():
                errors.append(f"frozen input missing: {rec.get('path')}")
            elif sha256_path(path) != rec.get("sha256") or path.stat().st_size != rec.get("bytes"):
                errors.append(f"frozen input drift: {rec.get('path')}")
        fixture_dir = ROOT / str(task.get("path", "")) / "fixture"
        actual_fixture = {
            relative(path): (sha256_path(path), path.stat().st_size)
            for path in fixture_dir.rglob("*")
            if path.is_file()
        } if fixture_dir.is_dir() else {}
        frozen_fixture = {
            item.get("path"): (item.get("sha256"), item.get("bytes"))
            for item in task.get("fixture_inventory") or []
            if isinstance(item, dict)
        }
        if actual_fixture != frozen_fixture:
            errors.append("neutral fixture inventory or content drift")
        if set(actual_fixture) != {f"{TASK_REL}/fixture/.gitkeep"}:
            errors.append("neutral fixture must contain exactly .gitkeep and no instruction or product files")
        setup_path = ROOT / str(task.get("path", "")) / "setup.sh"
        if task.get("setup_script") is None and setup_path.exists():
            errors.append("unexpected task setup.sh would change the frozen target workspace")
    conditions = condition_map(manifest) if manifest.get("conditions") else {}
    if len(conditions) != len(manifest.get("conditions") or []):
        errors.append("duplicate condition_id")
    for condition_id, condition in conditions.items():
        if condition.get("instruction_text_observability") not in {"complete", "partial"}:
            errors.append(f"condition {condition_id} has invalid instruction-text observability")
    if check_files:
        try:
            configuration_lock = load_json(ROOT / CONFIG_LOCK_REL)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"configuration lock unreadable: {exc}")
        else:
            if configuration_lock.get("schema_version") != 1 or set(configuration_lock.get("conditions") or {}) != set(conditions):
                errors.append("configuration lock does not cover frozen conditions")
    repeats = (manifest.get("sampling") or {}).get("valid_runs_per_condition")
    if not isinstance(repeats, int) or repeats < 1:
        errors.append("invalid valid_runs_per_condition")
    elif phase == "confirmatory" and repeats < 10:
        errors.append("confirmatory runs per condition below 10")
    slots = manifest.get("schedule") or []
    slot_ids = [slot.get("slot_id") for slot in slots]
    if len(slot_ids) != len(set(slot_ids)):
        errors.append("duplicate primary slot_id")
    if conditions and isinstance(repeats, int):
        seed = (manifest.get("randomization") or {}).get("seed")
        if isinstance(seed, int):
            expected_slots: list[dict[str, Any]] = []
            sequence = 0
            for block, order in enumerate(_balanced_orders(list(conditions), repeats, seed), start=1):
                for position, condition_id in enumerate(order, start=1):
                    sequence += 1
                    expected_slots.append(
                        {
                            "slot_id": f"primary-{block:02d}--{condition_id}",
                            "kind": "primary",
                            "block": block,
                            "position": position,
                            "sequence": sequence,
                            "replicate": block,
                            "condition_id": condition_id,
                        }
                    )
            if slots != expected_slots:
                errors.append("primary schedule differs from the deterministic frozen randomization")
        else:
            errors.append("randomization seed must be an integer")
        by_condition = Counter(slot.get("condition_id") for slot in slots)
        for cid in conditions:
            if by_condition[cid] != repeats:
                errors.append(f"condition {cid} has {by_condition[cid]} primary slots, expected {repeats}")
        by_block: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for slot in slots:
            by_block[slot.get("block")].append(slot)
        for block, block_slots in by_block.items():
            if {slot.get("condition_id") for slot in block_slots} != set(conditions):
                errors.append(f"block {block} is not a complete condition block")
            positions = sorted(slot.get("position") for slot in block_slots)
            if positions != list(range(1, len(conditions) + 1)):
                errors.append(f"block {block} positions are invalid")
        if phase == "confirmatory":
            position_counts: dict[str, Counter[int]] = defaultdict(Counter)
            for slot in slots:
                position_counts[slot["condition_id"]][slot["position"]] += 1
            for cid, counts in position_counts.items():
                values = [counts[p] for p in range(1, len(conditions) + 1)]
                if max(values) - min(values) > 1:
                    errors.append(f"condition {cid} order positions are not balanced: {values}")
    reserve_ids = [slot.get("slot_id") for slot in manifest.get("reserve_slots") or []]
    if len(reserve_ids) != len(set(reserve_ids)) or set(reserve_ids) & set(slot_ids):
        errors.append("duplicate or overlapping reserve slot_id")
    if phase == "smoke" and (manifest.get("reserve_slots") or []):
        errors.append("smoke manifest must not contain replacement slots")
    if phase == "confirmatory" and isinstance(repeats, int):
        reserve_count = (manifest.get("sampling") or {}).get("reserve_slots_per_condition")
        expected_reserves = [
            {
                "slot_id": f"reserve-{index:02d}--{condition_id}",
                "kind": "reserve",
                "reserve_index": index,
                "replicate": repeats + index,
                "condition_id": condition_id,
                "replacement_for": None,
            }
            for condition_id in conditions
            for index in range(1, int(reserve_count or 0) + 1)
        ]
        if (manifest.get("reserve_slots") or []) != expected_reserves:
            errors.append("reserve schedule differs from the deterministic frozen construction")
    return errors


def iter_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[int]]:
    events: list[dict[str, Any]] = []
    malformed: list[int] = []
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return events, [0]
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            malformed.append(number)
            continue
        if isinstance(event, dict):
            event["_line"] = number
            events.append(event)
        else:
            malformed.append(number)
    return events, malformed


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        for key in ("text", "output_text", "input_text"):
            if isinstance(block.get(key), str):
                parts.append(block[key])
                break
    return "".join(parts)


def extract_final_output(driver: str, run_dir: Path, events: list[dict[str, Any]]) -> tuple[str, str]:
    if driver == "claude":
        result_events: list[dict[str, Any]] = []
        result_path = run_dir / "result.json"
        if result_path.is_file() and result_path.read_text().strip():
            try:
                parsed = json.loads(result_path.read_text())
                if isinstance(parsed, dict):
                    result_events.append(parsed)
            except json.JSONDecodeError:
                pass
        result_events.extend(event for event in events if event.get("type") == "result")
        for event in reversed(result_events):
            if isinstance(event.get("result"), str):
                return event["result"], "result_event.result"
        return "", "missing_result_event"
    if driver == "codex":
        path = run_dir / "last_message.txt"
        return (path.read_text(errors="replace"), "last_message.txt") if path.is_file() else ("", "missing_last_message")
    if driver == "kimi":
        for event in reversed(events):
            if event.get("role") == "assistant" and not (event.get("tool_calls") or []):
                text = _content_text(event.get("content"))
                if text:
                    return text, f"transcript.jsonl:{event['_line']}"
        return "", "missing_terminal_assistant_content"
    raise ValueError(f"unknown driver: {driver}")


def _event_name_from_input(item: dict[str, Any]) -> str:
    for key in ("name", "tool_name", "command"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value if key != "command" else "command_execution"
        if isinstance(value, list) and value:
            return "command_execution"
    return str(item.get("type") or item.get("item_type") or "unknown_tool")


def _call_arguments(value: Any) -> Any:
    """Keep observable call arguments for deterministic subtype coding."""
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)


def detect_tool_events(driver: str, events: list[dict[str, Any]], run_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    calls: dict[str, dict[str, Any]] = {}
    unknown: list[str] = []
    if driver == "claude":
        for event in events:
            event_type = event.get("type")
            if event_type not in CLAUDE_TOP_LEVEL_EVENTS:
                unknown.append(f"transcript.jsonl:{event['_line']}:unknown top-level event {event_type!r}")
                continue
            if event_type == "system":
                if event.get("subtype") not in CLAUDE_SYSTEM_SUBTYPES:
                    unknown.append(
                        f"transcript.jsonl:{event['_line']}:unknown system subtype {event.get('subtype')!r}"
                    )
                continue
            if event_type not in {"assistant", "user"}:
                continue
            message = event.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), list):
                unknown.append(f"transcript.jsonl:{event['_line']}:malformed {event_type} message envelope")
                continue
            for index, block in enumerate(message["content"]):
                if not isinstance(block, dict):
                    unknown.append(f"transcript.jsonl:{event['_line']}:malformed {event_type} content block")
                    continue
                block_type = block.get("type")
                if block_type in CLAUDE_ACTION_BLOCKS:
                    event_id = str(block.get("id") or f"line-{event['_line']}-block-{index}")
                    calls[event_id] = {
                        "event_id": event_id,
                        "source": "transcript.jsonl",
                        "line": event["_line"],
                        "name": str(block.get("name") or block_type),
                        "event_type": block_type,
                        "arguments": _call_arguments(block.get("input")),
                    }
                elif block_type == "tool_result":
                    event_id = str(block.get("tool_use_id") or f"line-{event['_line']}-block-{index}")
                    if event_id not in calls:
                        calls[event_id] = {
                            "event_id": event_id,
                            "source": "transcript.jsonl",
                            "line": event["_line"],
                            "name": "observed_tool_result_without_call",
                            "event_type": "tool_result",
                            "arguments": None,
                        }
                elif block_type not in CLAUDE_PASSIVE_BLOCKS:
                    unknown.append(
                        f"transcript.jsonl:{event['_line']}:unknown {event_type} content type {block_type!r}"
                    )
            parent = event.get("parent_tool_use_id") if event_type == "assistant" else None
            if parent and str(parent) not in calls:
                calls[str(parent)] = {
                    "event_id": str(parent),
                    "source": "transcript.jsonl",
                    "line": event["_line"],
                    "name": "nested_agent_activity",
                    "event_type": "parent_tool_use_id",
                    "arguments": None,
                }
    elif driver == "codex":
        for event in events:
            envelope_type = event.get("type")
            if envelope_type not in CODEX_TOP_LEVEL_EVENTS:
                unknown.append(f"transcript.jsonl:{event['_line']}:unknown top-level event {envelope_type!r}")
                continue
            if envelope_type not in {"item.started", "item.updated", "item.completed"}:
                continue
            item = event.get("item")
            if not isinstance(item, dict):
                unknown.append(f"transcript.jsonl:{event['_line']}:malformed item envelope")
                continue
            item_type = item.get("type") or item.get("item_type")
            if item_type in PASSIVE_CODEX_ITEMS:
                continue
            if not item_type:
                unknown.append(f"transcript.jsonl:{event['_line']}:missing item type")
                continue
            if item_type not in ACTIVE_CODEX_ITEMS:
                unknown.append(f"transcript.jsonl:{event['_line']}:unknown item type {item_type!r}")
            event_id = str(item.get("id") or f"line-{event['_line']}")
            calls[event_id] = {
                "event_id": event_id,
                "source": "transcript.jsonl",
                "line": event["_line"],
                "name": _event_name_from_input(item),
                "event_type": str(item_type),
                "arguments": _call_arguments(
                    item.get("arguments")
                    if item.get("arguments") is not None
                    else item.get("command")
                    if item.get("command") is not None
                    else item.get("changes")
                ),
            }
        session_path = run_dir / "session.jsonl"
        session_events, session_bad = iter_jsonl(session_path) if session_path.is_file() else ([], [])
        unknown.extend(f"session.jsonl:{line}:malformed" for line in session_bad)
        for event in session_events:
            envelope_type = event.get("type")
            if envelope_type not in CODEX_SESSION_TOP_LEVEL_EVENTS:
                unknown.append(f"session.jsonl:{event['_line']}:unknown top-level event {envelope_type!r}")
                continue
            if envelope_type not in {"response_item", "event_msg"}:
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                unknown.append(f"session.jsonl:{event['_line']}:malformed {envelope_type} payload")
                continue
            payload_type = payload.get("type")
            if envelope_type == "event_msg":
                if payload_type in PASSIVE_CODEX_EVENT_MESSAGES:
                    continue
                if payload_type not in ACTIVE_CODEX_EVENT_MESSAGES:
                    unknown.append(
                        f"session.jsonl:{event['_line']}:unknown event message type {payload_type!r}"
                    )
                    continue
            elif payload_type in CODEX_SESSION_RESULT_TYPES:
                event_id = str(
                    payload.get("call_id") or payload.get("id") or f"session-line-{event['_line']}"
                )
                if event_id not in calls:
                    calls[event_id] = {
                        "event_id": event_id,
                        "source": "session.jsonl",
                        "line": event["_line"],
                        "name": "observed_tool_result_without_call",
                        "event_type": str(payload_type),
                        "arguments": None,
                    }
                continue
            elif payload_type in PASSIVE_SESSION_RESPONSE_TYPES:
                continue
            elif payload_type not in CALL_SESSION_TYPES:
                unknown.append(
                    f"session.jsonl:{event['_line']}:unknown response item type {payload_type!r}"
                )
                continue
            event_id = str(payload.get("call_id") or payload.get("id") or f"session-line-{event['_line']}")
            if event_id not in calls:
                calls[event_id] = {
                    "event_id": event_id,
                    "source": "session.jsonl",
                    "line": event["_line"],
                    "name": str(payload.get("name") or payload_type),
                    "event_type": str(payload_type),
                    "arguments": _call_arguments(
                        payload.get("arguments")
                        if payload.get("arguments") is not None
                        else payload.get("input")
                    ),
                }
    elif driver == "kimi":
        for event in events:
            role = event.get("role")
            event_type = event.get("type")
            if role is None:
                if event_type not in KIMI_TRANSCRIPT_TYPES:
                    unknown.append(f"transcript.jsonl:{event['_line']}:unknown top-level event {event_type!r}")
                continue
            if role not in KIMI_TRANSCRIPT_ROLES:
                unknown.append(f"transcript.jsonl:{event['_line']}:unknown message role {role!r}")
                continue
            if role == "tool":
                event_id = str(
                    event.get("tool_call_id") or event.get("id") or f"line-{event['_line']}-tool-result"
                )
                if event_id not in calls:
                    calls[event_id] = {
                        "event_id": event_id,
                        "source": "transcript.jsonl",
                        "line": event["_line"],
                        "name": "observed_tool_result_without_call",
                        "event_type": "tool_result",
                        "arguments": None,
                    }
                continue
            if role != "assistant":
                continue
            tool_calls = event.get("tool_calls") or []
            if not isinstance(tool_calls, list):
                unknown.append(f"transcript.jsonl:{event['_line']}:malformed tool_calls collection")
                continue
            for index, call in enumerate(tool_calls):
                if not isinstance(call, dict):
                    unknown.append(f"transcript.jsonl:{event['_line']}:malformed tool call")
                    continue
                function = call.get("function")
                if not isinstance(function, dict):
                    unknown.append(f"transcript.jsonl:{event['_line']}:malformed tool function")
                    continue
                event_id = str(call.get("id") or f"line-{event['_line']}-call-{index}")
                calls[event_id] = {
                    "event_id": event_id,
                    "source": "transcript.jsonl",
                    "line": event["_line"],
                    "name": str(function.get("name") or call.get("type") or "unknown_tool"),
                    "event_type": str(call.get("type") or "tool_call"),
                    "arguments": _call_arguments(function.get("arguments")),
                }
        wire_path = run_dir / "wire.jsonl"
        wire_events, wire_bad = iter_jsonl(wire_path) if wire_path.is_file() else ([], [])
        unknown.extend(f"wire.jsonl:{line}:malformed" for line in wire_bad)
        for event in wire_events:
            envelope_type = event.get("type")
            if envelope_type in KIMI_WIRE_PASSIVE_TYPES:
                continue
            if envelope_type != "context.append_loop_event":
                unknown.append(f"wire.jsonl:{event['_line']}:unknown top-level event {envelope_type!r}")
                continue
            loop_event = event.get("event")
            if not isinstance(loop_event, dict):
                unknown.append(f"wire.jsonl:{event['_line']}:malformed loop event")
                continue
            loop_type = loop_event.get("type")
            if loop_type == "content.part":
                part = loop_event.get("part")
                if not isinstance(part, dict) or part.get("type") not in {"text", "think"}:
                    unknown.append(
                        f"wire.jsonl:{event['_line']}:unknown or malformed content part {part.get('type') if isinstance(part, dict) else None!r}"
                    )
                continue
            if loop_type == "tool.result":
                event_id = str(
                    loop_event.get("toolCallId")
                    or loop_event.get("uuid")
                    or f"wire-line-{event['_line']}-tool-result"
                )
                if event_id not in calls:
                    calls[event_id] = {
                        "event_id": event_id,
                        "source": "wire.jsonl",
                        "line": event["_line"],
                        "name": "observed_tool_result_without_call",
                        "event_type": "tool.result",
                        "arguments": None,
                    }
                continue
            if loop_type in KIMI_WIRE_LOOP_PASSIVE_TYPES:
                continue
            if loop_type not in {"tool.call", "tool.call.delta", "tool.call.started"}:
                unknown.append(f"wire.jsonl:{event['_line']}:unknown loop event type {loop_type!r}")
                continue
            event_id = str(loop_event.get("toolCallId") or loop_event.get("uuid") or f"wire-line-{event['_line']}")
            if event_id not in calls:
                calls[event_id] = {
                    "event_id": event_id,
                    "source": "wire.jsonl",
                    "line": event["_line"],
                    "name": str(loop_event.get("name") or "tool.call"),
                    "event_type": str(loop_type),
                    "arguments": _call_arguments(
                        loop_event.get("arguments")
                        if loop_event.get("arguments") is not None
                        else loop_event.get("input")
                    ),
                }
    else:
        raise ValueError(f"unknown driver: {driver}")
    return sorted(calls.values(), key=lambda item: (item["source"], item["line"], item["event_id"])), unknown


def classify_calls(calls: list[dict[str, Any]], workspace_changed: bool) -> dict[str, bool]:
    names = [call["name"].lower() for call in calls]
    types = [call["event_type"].lower() for call in calls]
    arguments = [
        json.dumps(call.get("arguments"), sort_keys=True, ensure_ascii=False).lower()
        if not isinstance(call.get("arguments"), str)
        else call["arguments"].lower()
        for call in calls
    ]
    surfaces = [" ".join(parts) for parts in zip(names, types, arguments)]
    spawned = any(
        name in {"task", "agent", "agentswarm", "spawn_agent", "collaboration.spawn_agent"}
        or "spawn_agent" in name
        or "agent_swarm" in name
        or event_type in {"collab_agent_tool_call"}
        or "spawn_agent" in surface
        or "collaboration.spawn_agent" in surface
        for name, event_type, surface in zip(names, types, surfaces)
    )
    inspected = any(
        name in {"read", "grep", "glob", "view_image", "read_file", "search_files"}
        or any(token in surface for token in (
            "tools.view_image", "tools.read", "tools.exec_command", " read ", " cat ", " sed -n", " head ",
            " tail ", " grep ", " rg ", " find ", " ls ", " pwd", "git status", "git diff",
            "open(", ".read_text(", ".read_bytes(", "os.listdir(", "os.scandir(", "glob.glob(",
            "/proc/",
        ))
        for name, surface in zip(names, surfaces)
    )
    researched = any(
        any(token in surface for token in (
            "websearch", "web_search", "webfetch", "web__run", "web.run", "fetchurl", "fetch_url",
            "research", "curl ", "wget ", "http://", "https://", "socket.", "requests.",
            "urllib.", "http.client", "httpx.", "aiohttp", "dns.resolver",
        ))
        for surface in surfaces
    )
    mutated = workspace_changed or any(
        name in {"write", "edit", "apply_patch", "file_change", "write_file", "create_file", "delete_file"}
        or event_type == "file_change"
        or any(token in surface for token in (
            "apply_patch", "tools.apply_patch", " sed -i", " tee ", "touch ", "mkdir ", "rm ", "mv ",
            "cp ", "git commit", "npm install", "pip install", " > ", ">>", ".write_text(",
            ".write_bytes(", "os.remove(", "os.unlink(", "os.rename(", "os.replace(", "shutil.move(",
        ))
        or bool(re.search(r"open\s*\([^)]*,\s*\\?[\"'][wax+]", surface))
        for name, event_type, surface in zip(names, types, surfaces)
    )
    unclassified = bool(calls) and not any((spawned, inspected, researched, mutated))
    return {
        "target_originated_tool_or_function_call": bool(calls),
        "spawned_agent": spawned,
        "repository_or_file_inspection": inspected,
        "research_or_network_action": researched,
        "implementation_or_mutation_attempt": mutated,
        "unclassified_tool_action": unclassified,
    }


def instruction_context(driver: str, events: list[dict[str, Any]], run_dir: Path) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    if driver == "claude":
        init = next((event for event in events if event.get("type") == "system" and event.get("subtype") == "init"), None)
        if init is None:
            issues.append("missing Claude init event")
            return {"driver": driver, "native_system_text": "not exposed by stream-json", "init_event": None}, issues
        clean = {key: value for key, value in init.items() if key != "_line"}
        return {
            "driver": driver,
            "native_system_text": "not exposed by stream-json",
            "init_event": clean,
            "limitations": ["Claude Code does not expose the full native system/developer prompt in this artifact format."],
        }, issues
    if driver == "codex":
        session_path = run_dir / "session.jsonl"
        session, malformed = iter_jsonl(session_path)
        if malformed:
            issues.append(f"malformed Codex session lines: {malformed}")
        if not session:
            issues.append("missing Codex session rollout")
        base = None
        messages: list[dict[str, Any]] = []
        turn_contexts: list[dict[str, Any]] = []
        world_states: list[dict[str, Any]] = []
        for event in session:
            payload = event.get("payload") or {}
            if event.get("type") == "session_meta":
                base = payload.get("base_instructions")
            elif event.get("type") == "response_item" and payload.get("type") == "message" and payload.get("role") in {"system", "developer", "user"}:
                messages.append({key: value for key, value in payload.items()})
            elif event.get("type") == "turn_context":
                turn_contexts.append(payload)
            elif event.get("type") == "world_state":
                world_states.append(payload)
        if base is None:
            issues.append("Codex base instructions missing from session rollout")
        return {
            "driver": driver,
            "base_instructions": base,
            "pre_response_messages": messages,
            "turn_contexts": turn_contexts,
            "world_states": world_states,
            "limitations": ["API-served model identity and the complete native tool schema are not independently exposed."],
        }, issues
    if driver == "kimi":
        wire_path = run_dir / "wire.jsonl"
        wire, malformed = iter_jsonl(wire_path)
        if malformed:
            issues.append(f"malformed Kimi wire lines: {malformed}")
        if not wire:
            issues.append("missing Kimi wire journal")
        config = []
        active_tools = []
        tool_snapshots = []
        requests = []
        for event in wire:
            clean = {key: value for key, value in event.items() if key != "_line"}
            if event.get("type") == "config.update":
                config.append(clean)
            elif event.get("type") == "tools.set_active_tools":
                active_tools.append(clean)
            elif event.get("type") == "llm.tools_snapshot":
                tool_snapshots.append(clean)
            elif event.get("type") == "llm.request":
                requests.append(
                    {
                        key: clean.get(key)
                        for key in (
                            "type",
                            "time",
                            "maxTokens",
                            "model",
                            "modelAlias",
                            "provider",
                            "systemPromptHash",
                            "thinkingEffort",
                            "thinkingKeep",
                            "toolSelect",
                            "toolsHash",
                        )
                        if key in clean
                    }
                )
        if not any("systemPrompt" in event for event in config):
            issues.append("Kimi system prompt missing from wire journal")
        return {
            "driver": driver,
            "config_updates": config,
            "active_tools": active_tools,
            "tool_snapshots": tool_snapshots,
            "requests": requests,
        }, issues
    raise ValueError(f"unknown driver: {driver}")


def observed_model_and_effort(driver: str, events: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
    models: list[str] = []
    evidence: list[dict[str, str]] = []
    effort: Any = None
    identity_kind = "served"
    if driver == "claude":
        init_model = (context.get("init_event") or {}).get("model")
        if isinstance(init_model, str) and init_model:
            models.append(init_model)
            evidence.append({"kind": "requested_init_tag", "value": init_model})
        for event in events:
            model = (event.get("message") or {}).get("model") if event.get("type") == "assistant" else None
            if isinstance(model, str) and model not in models:
                models.append(model)
                evidence.append({"kind": "served_response_tag", "value": model})
        identity_kind = "requested_init_and_served_response_tags"
    elif driver == "codex":
        for turn in context.get("turn_contexts") or []:
            model = turn.get("model")
            if isinstance(model, str) and model not in models:
                models.append(model)
                evidence.append({"kind": "requested_turn_context", "value": model})
            settings = ((turn.get("collaboration_mode") or {}).get("settings") or {})
            if settings.get("reasoning_effort") is not None:
                effort = settings["reasoning_effort"]
        identity_kind = "requested_turn_context_only"
    elif driver == "kimi":
        for request in context.get("requests") or []:
            model = request.get("model")
            if isinstance(model, str) and model not in models:
                models.append(model)
                evidence.append({"kind": "request_wire_record", "value": model})
            if request.get("thinkingEffort") is not None:
                effort = request["thinkingEffort"]
        identity_kind = "request_wire_record"
    return {"models": models, "model_evidence": evidence, "identity_kind": identity_kind, "observed_effort": effort}


def credential_receipt_issues(path: Path, driver: str) -> list[str]:
    """Validate only aggregate scanner evidence; never load or expect secret values."""
    if path.is_symlink() or not path.is_file():
        return [f"missing regular credential scan receipt: {path.name}"]
    try:
        receipt = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"malformed credential scan receipt {path.name}: {type(exc).__name__}"]
    if not isinstance(receipt, dict):
        return [f"credential scan receipt is not an object: {path.name}"]
    errors = []
    if set(receipt) != CREDENTIAL_RECEIPT_FIELDS:
        errors.append(f"credential scan receipt fields differ from frozen schema: {path.name}")
    if receipt.get("schema_version") != 1 or receipt.get("driver") != driver:
        errors.append(f"credential scan receipt identity mismatch: {path.name}")
    positive_counts = ("credential_pattern_count", "scanned_entry_count", "scanned_path_bytes")
    zero_counts = ("leak_match_count", "unsafe_special_entry_count", "escaping_symlink_count")
    if any(
        not isinstance(receipt.get(key), int)
        or isinstance(receipt.get(key), bool)
        or receipt[key] <= 0
        for key in positive_counts
    ):
        errors.append(f"credential scan receipt has invalid coverage: {path.name}")
    byte_count = receipt.get("scanned_regular_and_symlink_bytes")
    if not isinstance(byte_count, int) or isinstance(byte_count, bool) or byte_count < 0:
        errors.append(f"credential scan receipt has invalid byte count: {path.name}")
    if any(
        not isinstance(receipt.get(key), int)
        or isinstance(receipt.get(key), bool)
        or receipt[key] != 0
        for key in zero_counts
    ):
        errors.append(f"credential scan receipt reports unsafe content: {path.name}")
    if receipt.get("pass") is not True:
        errors.append(f"credential scan receipt did not pass: {path.name}")
    return errors


def _normalize_dynamic_policy_value(value: Any) -> Any:
    """Remove per-run scratch paths without weakening policy-content comparison."""
    if isinstance(value, dict):
        return {key: _normalize_dynamic_policy_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_dynamic_policy_value(item) for item in value]
    if isinstance(value, str):
        stage_prefix = r"(?:arena-plan-attempt\.[A-Za-z0-9_]+/runtime/)?"
        value = re.sub(rf"/tmp/{stage_prefix}arena-ws\.[A-Za-z0-9]+", "[workspace]", value)
        return re.sub(
            rf"/tmp/{stage_prefix}arena-(?:claude|codex|kimi)-home\.[A-Za-z0-9]+",
            "[auth-home]",
            value,
        )
    return value


def instruction_policy_signature(driver: str, context: dict[str, Any]) -> dict[str, Any]:
    if driver == "claude":
        init = context.get("init_event") or {}
        keys = (
            "agents",
            "capabilities",
            "claude_code_version",
            "mcp_servers",
            "model",
            "output_style",
            "permissionMode",
            "plugins",
            "skills",
            "tools",
        )
        value = {key: init.get(key) for key in keys}
    elif driver == "codex":
        contexts = context.get("turn_contexts") or []
        value = _normalize_dynamic_policy_value({
            "base_instructions": context.get("base_instructions"),
            "system_and_developer_messages": [
                message
                for message in context.get("pre_response_messages") or []
                if message.get("role") in {"system", "developer"}
            ],
            "turn_policy": {
                key: contexts[0].get(key)
                for key in (
                    "approval_policy",
                    "collaboration_mode",
                    "model",
                    "multi_agent_mode",
                    "permission_profile",
                    "personality",
                    "sandbox_policy",
                )
            }
            if contexts
            else None,
        })
    elif driver == "kimi":
        normalized_updates = []
        for item in context.get("config_updates") or []:
            normalized = {key: item.get(key) for key in item if key != "time"}
            if isinstance(normalized.get("systemPrompt"), str):
                text = normalized["systemPrompt"]
                text = re.sub(
                    r"The current date and time in ISO format is `[^`]*`",
                    "The current date and time in ISO format is `[dynamic]`",
                    text,
                )
                text = re.sub(
                    r"The current working directory is `[^`]*`",
                    "The current working directory is `[dynamic]`",
                    text,
                )
                normalized["systemPrompt"] = text
            normalized_updates.append(normalized)
        value = {
            "config_updates": normalized_updates,
            "active_tools": (context.get("active_tools") or [{}])[0].get("names"),
            "tool_snapshot": {
                key: (context.get("tool_snapshots") or [{}])[0].get(key) for key in ("hash", "tools")
            },
            "request": {
                key: (context.get("requests") or [{}])[0].get(key)
                for key in (
                    "maxTokens",
                    "model",
                    "modelAlias",
                    "provider",
                    "systemPromptHash",
                    "thinkingEffort",
                    "thinkingKeep",
                    "toolSelect",
                    "toolsHash",
                )
            },
        }
    else:
        raise ValueError(f"unknown driver: {driver}")
    return {"sha256": sha256_bytes(canonical_json(value)), "value": value}


def run_identifiers(driver: str, events: list[dict[str, Any]]) -> dict[str, list[str]]:
    identifiers: dict[str, list[str]] = defaultdict(list)
    if driver == "claude":
        for event in events:
            for key in ("session_id", "request_id"):
                value = event.get(key)
                if isinstance(value, str) and value not in identifiers[key]:
                    identifiers[key].append(value)
    elif driver == "codex":
        for event in events:
            if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str):
                identifiers["thread_id"].append(event["thread_id"])
    elif driver == "kimi":
        for event in events:
            if event.get("type") == "session.resume_hint" and isinstance(event.get("session_id"), str):
                identifiers["session_id"].append(event["session_id"])
    return dict(identifiers)


def artifact_records(run_dir: Path) -> list[dict[str, Any]]:
    excluded = {"artifact_manifest.json"}
    records = []
    for path in sorted(run_dir.rglob("*")):
        if path.parent == run_dir and path.name in excluded:
            continue
        metadata = path.lstat()
        base = {"path": str(path.relative_to(run_dir))}
        if stat.S_ISREG(metadata.st_mode):
            data = path.read_bytes()
            records.append({**base, "type": "regular_file", "sha256": sha256_bytes(data), "bytes": len(data)})
        elif stat.S_ISDIR(metadata.st_mode):
            records.append({**base, "type": "directory"})
        elif stat.S_ISLNK(metadata.st_mode):
            target = os.readlink(path).encode(errors="surrogateescape")
            records.append(
                {**base, "type": "symlink", "target_sha256": sha256_bytes(target), "target_bytes": len(target)}
            )
        else:
            raise ValueError(f"unsafe special filesystem entry in run artifacts: {base['path']}")
    return records


def completion_observation(
    driver: str, events: list[dict[str, Any]], metrics: dict[str, Any], output: str
) -> dict[str, Any]:
    """Normalize only structured completion facts exposed by the drivers."""
    exit_code = metrics.get("agent_exit")
    statuses: list[str] = []
    if driver == "claude":
        for event in events:
            if event.get("type") == "result":
                for key in ("subtype", "stop_reason"):
                    value = event.get(key)
                    if isinstance(value, str) and value not in statuses:
                        statuses.append(value)
    elif driver == "codex":
        statuses.extend(
            str(event.get("type"))
            for event in events
            if event.get("type") in {"turn.completed", "turn.failed", "error"}
        )
    elif driver == "kimi":
        statuses.extend(
            str(event.get("type"))
            for event in events
            if isinstance(event.get("type"), str) and event.get("type") in {"error", "result"}
        )
    status_text = " ".join(statuses).lower()
    return {
        "agent_exit": exit_code,
        "timeout_exit": exit_code == 124,
        "output_present": bool(output),
        "structured_statuses": statuses,
        "truncation_observed": exit_code == 124
        or any(token in status_text for token in ("max_turn", "max_token", "length", "truncat")),
        "refusal_observed": None,
        "refusal_observability": "no cross-driver structured refusal field; semantic nonanswers remain in the output",
    }


def observe_run(
    manifest: dict[str, Any],
    slot: dict[str, Any],
    run_dir: Path,
    *,
    expected_policy_signature: str | None = None,
    finalize_artifact_manifest: bool = True,
) -> dict[str, Any]:
    condition = condition_map(manifest)[slot["condition_id"]]
    driver = condition["driver"]
    for name in OBSERVER_ARTIFACTS:
        path = run_dir / name
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"refusing target-created or preexisting derived artifact: {name}")
    peek = (run_dir / "peek_check").read_text(errors="replace") if (run_dir / "peek_check").is_file() else ""
    if "SECRET LEAK" in peek:
        raise SecretLeakError("driver secret scan marked this attempt for quarantine")
    events, malformed = iter_jsonl(run_dir / "transcript.jsonl")
    output, output_source = extract_final_output(driver, run_dir, events)
    (run_dir / "final_output.txt").write_text(output)
    calls, trace_unknown = detect_tool_events(driver, events, run_dir)
    workspace_changed = bool((run_dir / "workspace.diff").is_file() and (run_dir / "workspace.diff").stat().st_size)
    classifications = classify_calls(calls, workspace_changed)
    embargo = {
        "schema_version": 1,
        "slot_id": slot["slot_id"],
        "pass": not classifications["target_originated_tool_or_function_call"]
        and not workspace_changed
        and not trace_unknown,
        "trace_integrity_pass": not trace_unknown,
        "trace_integrity_failure": bool(trace_unknown),
        "workspace_changed": workspace_changed,
        "tool_call_count": len(calls),
        "tool_calls": calls,
        "trace_unknowns": trace_unknown,
        **classifications,
    }
    write_json(run_dir / "embargo.json", embargo)
    context, context_issues = instruction_context(driver, events, run_dir)
    write_json(run_dir / "instruction_context.json", context)
    observed = observed_model_and_effort(driver, events, context)
    identifiers = run_identifiers(driver, events)
    policy_signature = instruction_policy_signature(driver, context)
    metrics: dict[str, Any] = {}
    run_env: dict[str, Any] = {}
    for path, destination in ((run_dir / "metrics.json", metrics), (run_dir / "run_env.json", run_env)):
        if not path.is_file():
            continue
        try:
            parsed = load_json(path)
            if isinstance(parsed, dict):
                destination.update(parsed)
            else:
                context_issues.append(f"{path.name} is not a JSON object")
        except (OSError, json.JSONDecodeError) as exc:
            context_issues.append(f"malformed {path.name}: {exc}")
    required = COMMON_ARTIFACTS + RAW_ARTIFACTS[driver]
    missing = [
        name
        for name in required
        if (run_dir / name).is_symlink() or not (run_dir / name).is_file()
    ]
    technical_issues = [f"missing required artifact: {name}" for name in missing]
    for name in ("credential_scan.raw.json", "credential_scan.runtime.json"):
        technical_issues.extend(credential_receipt_issues(run_dir / name, driver))
    technical_issues.extend(f"malformed transcript line: {line}" for line in malformed)
    technical_issues.extend(f"unknown trace shape: {value}" for value in trace_unknown)
    technical_issues.extend(context_issues)
    identifier_key = {"claude": "session_id", "codex": "thread_id", "kimi": "session_id"}[driver]
    if len(identifiers.get(identifier_key) or []) != 1:
        technical_issues.append(f"expected exactly one emitted {identifier_key} for run association")
    for metric_name in ("input_tokens", "output_tokens", "total_cost_usd", "wall_seconds"):
        value = metrics.get(metric_name)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            technical_issues.append(f"missing or invalid required descriptive metric: {metric_name}")
    if expected_policy_signature is not None and policy_signature["sha256"] != expected_policy_signature:
        technical_issues.append(
            f"instruction/tool policy drift: expected {expected_policy_signature}, got {policy_signature['sha256']}"
        )
    prompt_path = run_dir / "prompt.txt"
    prompt_sha = sha256_path(prompt_path) if prompt_path.is_file() else None
    if prompt_sha != manifest["task"]["prompt_sha256"]:
        technical_issues.append("delivered prompt hash mismatch")
    if run_env.get("prompt_sha256") != manifest["task"]["prompt_sha256"]:
        technical_issues.append("run environment prompt hash mismatch")
    frozen_prices = next(
        (item.get("sha256") for item in manifest.get("frozen_inputs") or [] if item.get("path") == "env/prices.json"),
        None,
    )
    if run_env.get("price_sheet_sha256") != frozen_prices:
        technical_issues.append("run environment price-sheet hash mismatch")
    if run_env.get("harness_tracked_dirty") is not False:
        technical_issues.append("harness had tracked changes at launch")
    cli_version = run_env.get("cli_version")
    if cli_version != condition.get("expected_cli_version"):
        technical_issues.append(f"CLI version drift: expected {condition.get('expected_cli_version')!r}, got {cli_version!r}")
    for field, expected_key in (
        ("base_url", "expected_base_url"),
        ("effort", "expected_effort_record"),
        ("setting_sources", "expected_setting_sources"),
    ):
        if run_env.get(field) != condition.get(expected_key):
            technical_issues.append(
                f"run environment {field} drift: expected {condition.get(expected_key)!r}, got {run_env.get(field)!r}"
            )
    if driver == "claude" and condition.get("model_env_expected") == "absent" and run_env.get("model_env") != "none":
        technical_issues.append("unexpected Claude model environment changed the frozen endpoint configuration")
    expected_models = set(condition.get("expected_model_identities") or [])
    if observed["models"] and any(model not in expected_models for model in observed["models"]):
        technical_issues.append(
            f"model mismatch: every observable identity must equal one of {sorted(expected_models)!r}, "
            f"observed {observed['models']!r}"
        )
    if not observed["models"]:
        technical_issues.append("observable model identity missing")
    if driver == "kimi" and observed.get("observed_effort") != condition["effort"].get("observed_value"):
        technical_issues.append(
            f"effort drift: expected {condition['effort'].get('observed_value')!r}, got {observed.get('observed_effort')!r}"
        )
    output_bytes = output.encode()
    completion = completion_observation(driver, events, metrics, output)
    completion_notes = []
    agent_exit = metrics.get("agent_exit")
    if agent_exit not in {0, None}:
        completion_notes.append(f"agent process exit {agent_exit}; retain unless adjudicated exogenous")
    if not output:
        completion_notes.append("empty target output; retain as behavioral outcome unless caused by an exogenous pre-execution failure")
    state = "invalid_setup" if technical_issues else ("review_required" if completion_notes else "valid")
    record = {
        "schema_version": 1,
        "experiment_id": manifest["experiment_id"],
        "manifest_freeze_id": manifest["freeze_id"],
        "phase": manifest["phase"],
        "slot": slot,
        "condition": condition,
        "run_dir": relative(run_dir),
        "output": {
            "path": "final_output.txt",
            "source": output_source,
            "present": bool(output),
            "bytes": len(output_bytes),
            "sha256": sha256_bytes(output_bytes),
        },
        "configuration": {
            "run_env": run_env,
            "observed_identity": observed,
            "run_identifiers": identifiers,
            "instruction_policy_signature": policy_signature,
            "workspace_instruction_files": [
                relative(path)
                for name in ("AGENTS.md", "CLAUDE.md")
                for path in (ROOT / manifest["task"]["path"] / "fixture").rglob(name)
            ],
        },
        "metrics": metrics,
        "completion": completion,
        "embargo": embargo,
        "validity": {
            "state": state,
            "technical_issues": technical_issues,
            "completion_notes": completion_notes,
            "confirmatory_analysis_eligible": manifest["phase"] == "confirmatory" and not technical_issues,
            "smoke_excluded": manifest["phase"] == "smoke",
        },
        "observed_at": utc_now(),
    }
    exogenous_reasons = set(eligible_exclusion_reasons(record)) & {
        "external_termination_before_attributable_target_completion",
        "transport_or_service_failure_before_request_acceptance",
    }
    if exogenous_reasons:
        record["validity"]["state"] = "invalid_exogenous_pre_attribution"
        record["validity"]["confirmatory_analysis_eligible"] = False
        record["validity"]["exogenous_exclusion_evidence"] = sorted(exogenous_reasons)
    write_json(run_dir / "run_record.json", record)
    if finalize_artifact_manifest:
        write_artifact_manifest(manifest, slot, run_dir)
    return record


def write_artifact_manifest(manifest: dict[str, Any], slot: dict[str, Any], run_dir: Path) -> None:
    path = run_dir / "artifact_manifest.json"
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite artifact manifest {path}")
    write_json(
        path,
        {
            "schema_version": 1,
            "slot_id": slot["slot_id"],
            "manifest_freeze_id": manifest["freeze_id"],
            "artifacts": artifact_records(run_dir),
        },
    )


def verify_artifacts(run_dir: Path) -> list[str]:
    """Verify exact run-file coverage and the run-record identity anchor."""
    path = run_dir / "artifact_manifest.json"
    if not path.is_file():
        return ["artifact_manifest.json missing"]
    try:
        manifest = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"artifact manifest unreadable: {exc}"]
    errors: list[str] = []
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        errors.append("artifact manifest has unsupported schema")
    records = manifest.get("artifacts") if isinstance(manifest, dict) else None
    if not isinstance(records, list) or not records:
        return errors + ["artifact manifest must contain a nonempty artifact inventory"]
    indexed: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"artifact record {index} is not an object")
            continue
        name = record.get("path")
        relative_path = Path(name) if isinstance(name, str) else Path()
        if (
            not isinstance(name, str)
            or not name
            or relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            errors.append(f"artifact record {index} has an unsafe path")
            continue
        if name in indexed:
            errors.append(f"duplicate artifact record: {name}")
            continue
        indexed[name] = record
    actual: dict[str, str] = {}
    for item in run_dir.rglob("*"):
        if item.parent == run_dir and item.name == "artifact_manifest.json":
            continue
        mode = item.lstat().st_mode
        kind = (
            "regular_file"
            if stat.S_ISREG(mode)
            else "directory"
            if stat.S_ISDIR(mode)
            else "symlink"
            if stat.S_ISLNK(mode)
            else "special"
        )
        actual[str(item.relative_to(run_dir))] = kind
    if set(indexed) != set(actual):
        errors.append(
            f"artifact inventory differs from run directory: missing={sorted(set(actual) - set(indexed))}, "
            f"unlisted={sorted(set(indexed) - set(actual))}"
        )
    for name, record in indexed.items():
        artifact = run_dir / name
        if name not in actual:
            errors.append(f"artifact missing: {name}")
            continue
        if record.get("type") != actual[name]:
            errors.append(f"artifact type changed: {name}")
        elif actual[name] == "regular_file":
            if sha256_path(artifact) != record.get("sha256") or artifact.lstat().st_size != record.get("bytes"):
                errors.append(f"artifact changed: {name}")
        elif actual[name] == "symlink":
            target = os.readlink(artifact).encode(errors="surrogateescape")
            if sha256_bytes(target) != record.get("target_sha256") or len(target) != record.get("target_bytes"):
                errors.append(f"artifact symlink changed: {name}")
        elif actual[name] == "special":
            errors.append(f"unsafe special artifact entry: {name}")
    run_record_path = run_dir / "run_record.json"
    if not run_record_path.is_file():
        return errors + ["run_record.json missing from artifact inventory"]
    try:
        run_record = load_json(run_record_path)
    except (OSError, json.JSONDecodeError) as exc:
        return errors + [f"run record unreadable: {exc}"]
    driver = ((run_record.get("condition") or {}).get("driver")) if isinstance(run_record, dict) else None
    if driver not in RAW_ARTIFACTS:
        errors.append("run record has unknown driver")
    else:
        required = set(COMMON_ARTIFACTS + RAW_ARTIFACTS[driver] + DERIVED_ARTIFACTS)
        missing_required = required - set(actual)
        if missing_required:
            errors.append(f"required artifacts absent: {sorted(missing_required)}")
        wrong_types = sorted(name for name in required & set(actual) if actual[name] != "regular_file")
        if wrong_types:
            errors.append(f"required artifacts are not regular files: {wrong_types}")
        for name in (
            "credential_scan.raw.json",
            "credential_scan.runtime.json",
            "credential_scan.json",
        ):
            errors.extend(credential_receipt_issues(run_dir / name, driver))
    slot_id = ((run_record.get("slot") or {}).get("slot_id")) if isinstance(run_record, dict) else None
    if manifest.get("slot_id") != slot_id:
        errors.append("artifact manifest slot_id does not match run record")
    if manifest.get("manifest_freeze_id") != run_record.get("manifest_freeze_id"):
        errors.append("artifact manifest freeze ID does not match run record")
    return errors


def eligible_exclusion_reasons(record: dict[str, Any]) -> list[str]:
    issues = [str(value).lower() for value in (record.get("validity") or {}).get("technical_issues") or []]
    reasons: set[str] = set()
    if any("prompt" in issue and "mismatch" in issue for issue in issues):
        reasons.add("prompt_hash_mismatch")
    if any(token in issue for issue in issues for token in (
        "cli version drift", "model mismatch", "effort drift", "run environment", "harness had tracked changes",
        "price-sheet hash mismatch", "frozen configuration", "instruction/tool policy drift",
    )):
        reasons.add("wrong_model_or_frozen_configuration")
    if any(token in issue for issue in issues for token in (
        "missing required artifact",
        "malformed",
        "base instructions missing",
        "init event",
        "session rollout",
        "system prompt missing",
        "observable model identity missing",
    )):
        reasons.add("corrupted_or_missing_raw_artifact_due_to_harness")
    completion = record.get("completion") or {}
    embargo = record.get("embargo") or {}
    exit_code = completion.get("agent_exit")
    no_attributable_target_activity = (
        not (record.get("output") or {}).get("present")
        and not embargo.get("target_originated_tool_or_function_call")
    )
    if no_attributable_target_activity and exit_code not in {0, None, 124, 130, 137, 143}:
        reasons.add("transport_or_service_failure_before_request_acceptance")
    if no_attributable_target_activity and exit_code in {130, 137, 143}:
        reasons.add("external_termination_before_attributable_target_completion")
    return sorted(reasons)


def validate_execution_ledger(manifest: dict[str, Any], ledger: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    all_slots = {
        slot["slot_id"]: slot for slot in [*(manifest.get("schedule") or []), *(manifest.get("reserve_slots") or [])]
    }
    seen: dict[str, dict[str, Any]] = {}
    child_by_parent: dict[str, str] = {}
    allowed_reasons = set((manifest.get("exclusions") or {}).get("replace_only") or [])
    for index, row in enumerate(ledger):
        location = f"execution ledger row {index + 1}"
        if not isinstance(row, dict):
            errors.append(f"{location} is not an object")
            continue
        slot_id = row.get("slot_id")
        if slot_id in seen:
            errors.append(f"{location} duplicates slot_id {slot_id}")
            continue
        slot = all_slots.get(slot_id)
        if slot is None:
            errors.append(f"{location} references non-frozen slot {slot_id}")
            continue
        seen[str(slot_id)] = row
        if row.get("phase") != manifest.get("phase"):
            errors.append(f"{location} phase does not match manifest")
        if row.get("condition_id") != slot.get("condition_id"):
            errors.append(f"{location} condition does not match frozen slot")
        if row.get("kind") != slot.get("kind", "primary"):
            errors.append(f"{location} kind does not match frozen slot")
        try:
            expected_dir = relative(output_dir_for(manifest, slot))
        except (KeyError, ValueError):
            expected_dir = None
        if row.get("run_dir") != expected_dir:
            errors.append(f"{location} run directory does not match frozen slot")
        if not isinstance(row.get("analysis_eligible"), bool):
            errors.append(f"{location} analysis_eligible must be boolean")
        if row.get("analysis_eligible") is True and not re.fullmatch(
            r"[0-9a-f]{64}", str(row.get("artifact_manifest_sha256") or "")
        ):
            errors.append(f"{location} eligible attempt lacks an artifact-manifest hash anchor")
        if row.get("analysis_eligible") is True and not re.fullmatch(
            r"[0-9a-f]{64}", str(row.get("instruction_policy_signature_sha256") or "")
        ):
            errors.append(f"{location} eligible attempt lacks an instruction/tool policy signature")
        for path_key, hash_key in (
            ("failure_receipt", "failure_receipt_sha256"),
            ("quarantine_receipt", "quarantine_receipt_sha256"),
        ):
            if row.get(path_key) is not None and not re.fullmatch(
                r"[0-9a-f]{64}", str(row.get(hash_key) or "")
            ):
                errors.append(f"{location} {path_key} lacks a content hash anchor")
        preflight = row.get("preflight")
        if not isinstance(preflight, dict):
            errors.append(f"{location} lacks a treatment preflight record")
        elif preflight.get("sha256") != sha256_bytes(
            canonical_json({key: value for key, value in preflight.items() if key != "sha256"})
        ):
            errors.append(f"{location} treatment-preflight hash is invalid")
        elif preflight.get("condition_id") != row.get("condition_id"):
            errors.append(f"{location} treatment preflight belongs to a different condition")
        expected_smoke = manifest.get("phase") == "smoke"
        if row.get("smoke_excluded") is not expected_smoke:
            errors.append(f"{location} smoke exclusion flag is inconsistent")
        replacement_for = row.get("replacement_for")
        if slot.get("kind") == "primary":
            if replacement_for is not None:
                errors.append(f"{location} primary slot cannot replace another attempt")
        else:
            parent = seen.get(str(replacement_for))
            if parent is None:
                errors.append(f"{location} reserve must link to an earlier attempted slot")
            else:
                if parent.get("condition_id") != row.get("condition_id"):
                    errors.append(f"{location} reserve and replaced attempt have different conditions")
                if parent.get("analysis_eligible") is not False:
                    errors.append(f"{location} may replace only an objectively ineligible attempt")
                reason = row.get("exclusion_reason")
                if reason not in allowed_reasons:
                    errors.append(f"{location} uses a non-preregistered exclusion reason")
                if reason not in set(parent.get("eligible_exclusion_reasons") or []):
                    errors.append(f"{location} exclusion reason is unsupported by the replaced attempt evidence")
            if replacement_for in child_by_parent:
                errors.append(f"{location} creates a second replacement for {replacement_for}")
            elif isinstance(replacement_for, str):
                child_by_parent[replacement_for] = str(slot_id)
    primary_order = [
        row.get("slot_id")
        for row in ledger
        if isinstance(row, dict) and row.get("kind") == "primary"
    ]
    expected_primary_order = [slot["slot_id"] for slot in manifest.get("schedule") or []]
    if primary_order != expected_primary_order[: len(primary_order)]:
        errors.append("execution ledger primary attempts are not a prefix of frozen sequence order")
    for condition_id in condition_map(manifest):
        attempted_reserves = [
            row.get("slot_id")
            for row in ledger
            if isinstance(row, dict)
            and row.get("kind") == "reserve"
            and row.get("condition_id") == condition_id
        ]
        expected_reserves = [
            slot["slot_id"]
            for slot in manifest.get("reserve_slots") or []
            if slot.get("condition_id") == condition_id
        ]
        if attempted_reserves != expected_reserves[: len(attempted_reserves)]:
            errors.append(f"reserve attempts for {condition_id} are not in frozen reserve-index order")
    return errors


def select_effective_attempts(
    manifest: dict[str, Any], ledger: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors = validate_execution_ledger(manifest, ledger)
    by_slot = {row.get("slot_id"): row for row in ledger if isinstance(row, dict)}
    by_parent = {
        row.get("replacement_for"): row
        for row in ledger
        if isinstance(row, dict) and row.get("replacement_for") is not None
    }
    effective: dict[str, dict[str, Any]] = {}
    for primary in manifest.get("schedule") or []:
        row = by_slot.get(primary["slot_id"])
        visited: set[str] = set()
        while row is not None and row.get("analysis_eligible") is False:
            slot_id = str(row.get("slot_id"))
            if slot_id in visited:
                errors.append(f"replacement cycle for {primary['slot_id']}")
                row = None
                break
            visited.add(slot_id)
            row = by_parent.get(slot_id)
        if row is None:
            errors.append(f"no eligible attempt for primary slot {primary['slot_id']}")
        elif row.get("analysis_eligible") is not True:
            errors.append(f"effective attempt eligibility is invalid for {primary['slot_id']}")
        else:
            effective[primary["slot_id"]] = row
    return effective, errors


def validate_run_provenance(
    manifest: dict[str, Any], slot: dict[str, Any], ledger_row: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    expected_dir = output_dir_for(manifest, slot)
    try:
        supplied_dir = (ROOT / str(ledger_row.get("run_dir", ""))).resolve()
        supplied_dir.relative_to(ROOT.resolve())
    except (OSError, ValueError):
        return None, [f"unsafe run directory for {slot['slot_id']}"]
    if supplied_dir != expected_dir.resolve():
        errors.append(f"run directory does not match frozen slot {slot['slot_id']}")
    errors.extend(f"{slot['slot_id']}: {error}" for error in verify_artifacts(supplied_dir))
    record_path = supplied_dir / "run_record.json"
    if not record_path.is_file():
        return None, errors + [f"run record missing for {slot['slot_id']}"]
    try:
        record = load_json(record_path)
    except (OSError, json.JSONDecodeError) as exc:
        return None, errors + [f"run record unreadable for {slot['slot_id']}: {exc}"]
    condition = condition_map(manifest).get(slot["condition_id"])
    checks = (
        (record.get("experiment_id") == manifest.get("experiment_id"), "experiment ID"),
        (record.get("manifest_freeze_id") == manifest.get("freeze_id"), "freeze ID"),
        (record.get("phase") == manifest.get("phase"), "phase"),
        ((record.get("slot") or {}).get("slot_id") == slot.get("slot_id"), "slot ID"),
        ((record.get("slot") or {}).get("condition_id") == slot.get("condition_id"), "slot condition"),
        (record.get("condition") == condition, "condition record"),
        (record.get("run_dir") == ledger_row.get("run_dir"), "run directory record"),
        ((record.get("validity") or {}).get("confirmatory_analysis_eligible") == ledger_row.get("analysis_eligible"), "eligibility"),
        ((record.get("validity") or {}).get("smoke_excluded") == ledger_row.get("smoke_excluded"), "smoke exclusion"),
        ((record.get("embargo") or {}).get("slot_id") == slot.get("slot_id"), "embargo slot"),
        (
            (record.get("configuration") or {}).get("run_env", {}).get("harness_commit")
            == (ledger_row.get("preflight") or {}).get("harness_commit"),
            "preflight harness commit",
        ),
        (
            (record.get("configuration") or {}).get("run_env", {}).get("cli_version")
            == (ledger_row.get("preflight") or {}).get("cli_version"),
            "preflight CLI version",
        ),
        (
            (record.get("configuration") or {}).get("instruction_policy_signature", {}).get("sha256")
            == ledger_row.get("instruction_policy_signature_sha256"),
            "instruction/tool policy signature",
        ),
    )
    for good, label in checks:
        if not good:
            errors.append(f"{slot['slot_id']}: run-record {label} mismatch")
    artifact_manifest_path = supplied_dir / "artifact_manifest.json"
    if artifact_manifest_path.is_file() and ledger_row.get("artifact_manifest_sha256") != sha256_path(artifact_manifest_path):
        errors.append(f"{slot['slot_id']}: artifact manifest does not match execution-ledger anchor")
    output_path = supplied_dir / "final_output.txt"
    if output_path.is_file():
        data = output_path.read_bytes()
        output = record.get("output") or {}
        if output.get("sha256") != sha256_bytes(data) or output.get("bytes") != len(data):
            errors.append(f"{slot['slot_id']}: final output does not match run record")
    return record, errors


def output_dir_for(manifest: dict[str, Any], slot: dict[str, Any]) -> Path:
    condition = condition_map(manifest)[slot["condition_id"]]
    return ROOT / manifest["bout_dir"] / Path(manifest["task"]["path"]).name / condition["output_label"] / f"run-{slot['replicate']}"


def driver_environment(driver: str, source: dict[str, str]) -> dict[str, str]:
    """Construct the exact minimal environment inherited by a driver process."""
    operational = {
        "HOME",
        "LANG",
        "LOGNAME",
        "PATH",
        "SHELL",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "TERM",
        "TZ",
        "USER",
        "XDG_RUNTIME_DIR",
    }
    env = {
        key: value
        for key, value in source.items()
        if key in operational or key.startswith("LC_")
    }
    try:
        temp_metadata = SAFE_TEMP_ROOT.lstat()
        temp_root = SAFE_TEMP_ROOT.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"safe temp root is unavailable: {type(exc).__name__}") from exc
    if SAFE_TEMP_ROOT.is_symlink() or not stat.S_ISDIR(temp_metadata.st_mode):
        raise ValueError("safe temp root must be a real directory, not a symlink")
    if temp_root == ROOT or ROOT in temp_root.parents:
        raise ValueError("safe temp root must be outside the Agent Arena repository")
    if temp_root.stat().st_dev != ROOT.stat().st_dev:
        raise ValueError("safe temp root must share a filesystem with the repository for atomic transfer")
    env["TMPDIR"] = str(temp_root)
    source_name = {
        "claude": "ARENA_CLAUDE_HOME",
        "codex": "ARENA_CODEX_HOME",
        "kimi": "ARENA_KIMI_HOME",
    }[driver]
    if source.get(source_name):
        env[source_name] = source[source_name]
    env["ARENA_TIMEOUT_S"] = "600"
    env["ARENA_PLAN_PROBE"] = "1"
    if driver == "claude":
        for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
            if source.get(name):
                env[name] = source[name]
        env["ARENA_EFFORT"] = "native-default"
        env["ARENA_SETTING_SOURCES"] = "project"
        env["ARENA_SETTING_SOURCES_RECORD"] = "project (fresh auth-only per-run home)"
    elif driver == "kimi":
        env["ARENA_KIMI_EFFORT"] = "native-default (observed in wire journal)"
    return env


def driver_command(manifest: dict[str, Any], slot: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    condition = condition_map(manifest)[slot["condition_id"]]
    driver = condition["driver"]
    script = {
        "claude": ROOT / "bin/run-task.sh",
        "codex": ROOT / "bin/run-task-codex.sh",
        "kimi": ROOT / "bin/run-task-kimi.sh",
    }[driver]
    command = [
        str(script),
        str(ROOT / manifest["task"]["path"]),
        condition["model_argument"],
        str(ROOT / manifest["bout_dir"]),
        str(slot["replicate"]),
    ]
    env = driver_environment(driver, dict(os.environ))
    if driver == "kimi":
        env["ARENA_KIMI_LABEL"] = condition["output_label"]
    return command, env


def prepare_staged_driver(
    manifest: dict[str, Any], slot: dict[str, Any], env: dict[str, str]
) -> tuple[Path, Path, list[str], dict[str, str]]:
    """Build a rubric-free live harness tree and external output path for one attempt."""
    condition = condition_map(manifest)[slot["condition_id"]]
    driver = condition["driver"]
    temp_base = Path(env["TMPDIR"]).resolve(strict=True)
    attempt_root = Path(tempfile.mkdtemp(prefix="arena-plan-attempt.", dir=temp_base))
    attempt_root.chmod(0o700)
    harness_root = attempt_root / "harness"
    runtime_root = attempt_root / "runtime"
    staged_bout = attempt_root / "bout"
    harness_root.mkdir(mode=0o700)
    runtime_root.mkdir(mode=0o700)
    staged_bout.mkdir(mode=0o700)
    try:
        for relative_path in STAGED_DRIVER_FILES[driver]:
            source = ROOT / relative_path
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"staged driver input is not a regular file: {relative_path}")
            destination = harness_root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if sha256_path(source) != sha256_path(destination):
                raise ValueError(f"staged driver input hash mismatch: {relative_path}")
        source_task = ROOT / manifest["task"]["path"]
        staged_task = harness_root / manifest["task"]["path"]
        staged_task.mkdir(parents=True)
        shutil.copy2(source_task / "PROMPT.md", staged_task / "PROMPT.md")
        shutil.copytree(source_task / "fixture", staged_task / "fixture")
        staged_script = {
            "claude": harness_root / "bin/run-task.sh",
            "codex": harness_root / "bin/run-task-codex.sh",
            "kimi": harness_root / "bin/run-task-kimi.sh",
        }[driver]
        command = [
            str(staged_script),
            str(staged_task),
            condition["model_argument"],
            str(staged_bout),
            str(slot["replicate"]),
        ]
        staged_run_dir = (
            staged_bout
            / Path(manifest["task"]["path"]).name
            / condition["output_label"]
            / f"run-{slot['replicate']}"
        )
        staged_env = dict(env)
        staged_env["TMPDIR"] = str(runtime_root)
        staged_env["ARENA_PLAN_TMPDIR"] = str(runtime_root)
        return attempt_root, staged_run_dir, command, staged_env
    except BaseException:
        shutil.rmtree(attempt_root)
        raise


def recover_and_remove_staged_driver(attempt_root: Path, staged_run_dir: Path, run_dir: Path) -> None:
    """Atomically transfer a completed/partial run, then erase the exact external stage."""
    safe_base = SAFE_TEMP_ROOT.resolve(strict=True)
    resolved_attempt = attempt_root.resolve(strict=True)
    if resolved_attempt.parent != safe_base or not resolved_attempt.name.startswith("arena-plan-attempt."):
        raise ValueError("refusing unsafe staged-driver cleanup target")
    if staged_run_dir.exists() or staged_run_dir.is_symlink():
        if staged_run_dir.is_symlink() or not staged_run_dir.is_dir():
            raise ValueError("staged run output is not a real directory")
        if run_dir.exists() or run_dir.is_symlink():
            raise FileExistsError(f"refusing to overwrite recovered run directory {run_dir}")
        run_dir.parent.mkdir(parents=True, exist_ok=True)
        staged_run_dir.rename(run_dir)
    shutil.rmtree(resolved_attempt)


def _external_home(raw: str | None, label: str) -> tuple[Path | None, list[str]]:
    if not raw:
        return None, [f"{label} is not set"]
    unresolved = Path(raw).expanduser()
    path = unresolved.resolve()
    errors = []
    if unresolved.is_symlink():
        errors.append(f"{label} itself must not be a symlink")
    if not path.is_dir():
        errors.append(f"{label} is not an accessible directory")
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        errors.append(f"{label} must be outside the Agent Arena repository")
    return path, errors


def preflight_condition(condition: dict[str, Any], env: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    """Check treatment-defining local state without invoking a target model."""
    driver = condition["driver"]
    errors: list[str] = []
    if driver == "claude":
        version_command = ["claude", "--version"]
    elif driver == "codex":
        version_command = ["codex", "--version"]
    else:
        version_command = [str(Path(env.get("HOME", str(Path.home()))) / ".kimi-code/bin/kimi"), "-V"]
    try:
        completed = subprocess.run(version_command, text=True, capture_output=True, check=False, timeout=30)
        raw_version = (completed.stdout or completed.stderr).splitlines()[0].strip() if (completed.stdout or completed.stderr) else ""
    except (OSError, subprocess.SubprocessError) as exc:
        raw_version = ""
        errors.append(f"could not query {driver} CLI version: {type(exc).__name__}")
    version = f"kimi-code {raw_version}" if driver == "kimi" and raw_version and not raw_version.startswith("kimi-code ") else raw_version
    if version != condition["expected_cli_version"]:
        errors.append(f"CLI version drift for {condition['condition_id']}: expected {condition['expected_cli_version']!r}, got {version!r}")

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False
    ).stdout.strip()
    snapshot: dict[str, Any] = {
        "condition_id": condition["condition_id"],
        "driver": driver,
        "cli_version": version,
        "harness_commit": commit or "unknown",
        "environment_policy": "minimal-allowlist-v3",
        "execution_isolation_policy": "rubric-free staged driver; nondumpable parent; atomic output transfer",
        "temp_root": env.get("TMPDIR"),
    }
    if driver == "claude":
        snapshot["credential_environment_fields_present"] = sorted(
            name for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN") if env.get(name)
        )
        home, home_errors = _external_home(env.get("ARENA_CLAUDE_HOME"), "ARENA_CLAUDE_HOME")
        errors.extend(home_errors)
        if home is not None:
            try:
                inventory, _ = credential_guard.inspect_source(driver, home)
                snapshot.update(
                    {
                        "credential_source_schema": inventory["source_schema"],
                        "credential_secret_field_count": inventory["secret_field_count"],
                        "redacted_home_inventory_sha256": inventory[
                            "redacted_structural_inventory_sha256"
                        ],
                    }
                )
            except credential_guard.CredentialGuardError as exc:
                errors.append(f"Claude credential source invalid: {exc}")
        model_env = ROOT / "env" / f"{condition['model_argument']}.env"
        if condition.get("model_env_expected") == "absent" and model_env.exists():
            errors.append(f"unexpected Claude model environment exists: {relative(model_env)}")
        effective_base = env.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        if effective_base != condition["expected_base_url"]:
            errors.append(f"Claude base URL drift: expected {condition['expected_base_url']!r}, got {effective_base!r}")
        snapshot.update({"base_url": effective_base, "model_env_present": model_env.exists()})
    elif driver == "codex":
        snapshot["credential_environment_fields_present"] = sorted(
            name for name in ("CODEX_API_KEY", "OPENAI_API_KEY") if env.get(name)
        )
        home, home_errors = _external_home(env.get("ARENA_CODEX_HOME"), "ARENA_CODEX_HOME")
        errors.extend(home_errors)
        if home is not None:
            try:
                inventory, _ = credential_guard.inspect_source(driver, home)
                snapshot.update(
                    {
                        "auth_present": True,
                        "credential_source_schema": inventory["source_schema"],
                        "credential_secret_field_count": inventory["secret_field_count"],
                        "redacted_home_inventory_sha256": inventory[
                            "redacted_structural_inventory_sha256"
                        ],
                    }
                )
            except credential_guard.CredentialGuardError as exc:
                errors.append(f"Codex credential source invalid: {exc}")
    else:
        snapshot["credential_environment_fields_present"] = sorted(
            name for name in ("KIMI_API_KEY", "MOONSHOT_API_KEY") if env.get(name)
        )
        raw_home = env.get("ARENA_KIMI_HOME") or str(Path.home() / ".kimi-arena")
        home, home_errors = _external_home(raw_home, "ARENA_KIMI_HOME")
        errors.extend(home_errors)
        if home is not None:
            try:
                inventory, _ = credential_guard.inspect_source(driver, home)
                snapshot.update(
                    {
                        "credential_source_schema": inventory["source_schema"],
                        "credential_secret_field_count": inventory["secret_field_count"],
                        "redacted_config_sha256": inventory["redacted_structural_inventory_sha256"],
                        "redacted_home_inventory_sha256": inventory[
                            "redacted_structural_inventory_sha256"
                        ],
                    }
                )
            except credential_guard.CredentialGuardError as exc:
                errors.append(f"Kimi credential source invalid: {exc}")
    snapshot["sha256"] = sha256_bytes(canonical_json({key: value for key, value in snapshot.items() if key != "sha256"}))
    return snapshot, errors


def tracked_worktree_dirty() -> bool:
    return subprocess.run(
        ["git", "diff", "--quiet"], cwd=ROOT, check=False
    ).returncode != 0 or subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False
    ).returncode != 0


def preflight_manifest(manifest: dict[str, Any], condition_ids: set[str], env: dict[str, str]) -> dict[str, dict[str, Any]]:
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("manifest preflight failed:\n- " + "\n- ".join(errors))
    if tracked_worktree_dirty():
        raise ValueError("no-API treatment preflight failed:\n- harness has tracked worktree or index changes")
    snapshots: dict[str, dict[str, Any]] = {}
    configuration_lock = load_json(ROOT / CONFIG_LOCK_REL)
    frozen_set_sha = sha256_bytes(canonical_json(manifest.get("frozen_inputs") or []))
    for condition_id in sorted(condition_ids):
        condition = condition_map(manifest)[condition_id]
        condition_env = driver_environment(condition["driver"], env)
        if condition["driver"] == "kimi":
            condition_env["ARENA_KIMI_LABEL"] = condition["output_label"]
        snapshot, condition_errors = preflight_condition(condition, condition_env)
        snapshot["frozen_input_set_sha256"] = frozen_set_sha
        snapshot["sha256"] = sha256_bytes(
            canonical_json({key: value for key, value in snapshot.items() if key != "sha256"})
        )
        snapshots[condition_id] = snapshot
        errors.extend(condition_errors)
        expected = (configuration_lock.get("conditions") or {}).get(condition_id) or {}
        for key, expected_value in expected.items():
            if key == "isolated_home_policy":
                continue
            if snapshot.get(key) != expected_value:
                errors.append(
                    f"configuration lock mismatch for {condition_id}.{key}: expected {expected_value!r}, got {snapshot.get(key)!r}"
                )
    if errors:
        raise ValueError("no-API treatment preflight failed:\n- " + "\n- ".join(errors))
    return snapshots


def append_ledger(path: Path, row: dict[str, Any]) -> None:
    existing = []
    if path.is_file():
        existing, malformed = iter_jsonl(path)
        if malformed:
            raise ValueError(f"execution ledger is malformed at lines {malformed}")
    slot_id = row["slot_id"]
    if any(item.get("slot_id") == slot_id for item in existing):
        raise ValueError(f"execution ledger already contains {slot_id}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def write_attempt_failure(manifest: dict[str, Any], slot: dict[str, Any], value: dict[str, Any]) -> str:
    path = ROOT / manifest["bout_dir"] / "ATTEMPT_FAILURES" / f"{slot['slot_id']}.json"
    if path.exists():
        raise FileExistsError(f"refusing to overwrite attempt-failure receipt {path}")
    write_json(path, value)
    return relative(path)


def _credential_home_for(driver: str, env: dict[str, str]) -> Path:
    variable = {
        "claude": "ARENA_CLAUDE_HOME",
        "codex": "ARENA_CODEX_HOME",
        "kimi": "ARENA_KIMI_HOME",
    }[driver]
    raw = env.get(variable)
    if not raw:
        raise credential_guard.CredentialGuardError(f"{variable} is unavailable to the security scanner")
    return Path(raw).resolve()


def scan_run_credentials(driver: str, env: dict[str, str], run_dir: Path, receipt_name: str) -> dict[str, Any]:
    """Scan exact exposed credentials without putting their values on a command line."""
    receipt_path = run_dir / receipt_name
    if receipt_path.exists() or receipt_path.is_symlink():
        raise credential_guard.CredentialGuardError("target-created credential scan receipt path")
    environment_secrets = []
    if driver == "claude":
        environment_secrets = [
            env.get("ANTHROPIC_API_KEY", ""),
            env.get("ANTHROPIC_AUTH_TOKEN", ""),
        ]
    receipt = credential_guard.scan_artifacts(
        driver,
        _credential_home_for(driver, env),
        [run_dir],
        environment_secrets=environment_secrets,
    )
    write_json(receipt_path, receipt)
    if not receipt["pass"]:
        raise SecretLeakError("credential scan detected a leak or unsafe filesystem entry")
    return receipt


def quarantine_destination(manifest: dict[str, Any], slot: dict[str, Any]) -> Path:
    """Prepare an atomic, same-filesystem quarantine destination before target execution."""
    raw_base = os.environ.get("ARENA_QUARANTINE_DIR")
    unresolved = Path(raw_base).expanduser() if raw_base else Path.home() / ".agent-arena-quarantine"
    if unresolved.is_symlink():
        raise ValueError("secret quarantine root must not be a symlink")
    unresolved.mkdir(parents=True, mode=0o700, exist_ok=True)
    metadata = unresolved.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ValueError("secret quarantine root must be a real directory")
    base = unresolved.resolve(strict=True)
    try:
        base.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("secret quarantine must be outside the Agent Arena repository")
    if stat.S_IMODE(base.stat().st_mode) & 0o077:
        raise ValueError("secret quarantine root must not be accessible by group or other users")
    destination = base / manifest["experiment_id"] / slot["slot_id"]
    destination.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    destination.parent.chmod(0o700)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"refusing to overwrite secret quarantine {destination}")
    if destination.parent.stat().st_dev != ROOT.stat().st_dev:
        raise ValueError("secret quarantine must share a filesystem with the repository for atomic rename")
    return destination


def quarantine_run(manifest: dict[str, Any], slot: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    destination = quarantine_destination(manifest, slot)
    entry_count = 0
    regular_file_bytes = 0
    if run_dir.is_dir():
        for path in sorted(run_dir.rglob("*")):
            entry_count += 1
            try:
                metadata = path.lstat()
            except OSError:
                continue
            if stat.S_ISREG(metadata.st_mode):
                regular_file_bytes += metadata.st_size
    run_dir.rename(destination)
    receipt = {
        "schema_version": 1,
        "experiment_id": manifest["experiment_id"],
        "manifest_freeze_id": manifest["freeze_id"],
        "slot_id": slot["slot_id"],
        "reason": "security_quarantine_after_secret_scan",
        "quarantined_at": utc_now(),
        "quarantined_entry_count": entry_count,
        "quarantined_regular_file_bytes": regular_file_bytes,
        "content_published": False,
    }
    receipt_path = ROOT / manifest["bout_dir"] / "QUARANTINE" / f"{slot['slot_id']}.json"
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite quarantine receipt {receipt_path}")
    write_json(receipt_path, receipt)
    return {"succeeded": True, "receipt": relative(receipt_path)}


def write_quarantine_failure(
    manifest: dict[str, Any], slot: dict[str, Any], run_dir: Path, error: BaseException
) -> dict[str, Any]:
    """Preserve auditable failure state if the prevalidated atomic quarantine unexpectedly fails."""
    receipt_path = ROOT / manifest["bout_dir"] / "QUARANTINE" / f"{slot['slot_id']}.failed.json"
    if receipt_path.exists() or receipt_path.is_symlink():
        raise FileExistsError(f"refusing to overwrite quarantine-failure receipt {receipt_path}")
    write_json(
        receipt_path,
        {
            "schema_version": 1,
            "experiment_id": manifest["experiment_id"],
            "manifest_freeze_id": manifest["freeze_id"],
            "slot_id": slot["slot_id"],
            "reason": "atomic_security_quarantine_failed",
            "failed_at": utc_now(),
            "error_type": type(error).__name__,
            "run_dir_retained_for_manual_recovery": relative(run_dir),
            "content_published": False,
        },
    )
    return {"succeeded": False, "receipt": relative(receipt_path)}


def raw_attempt_has_attributable_activity(driver: str, run_dir: Path) -> bool:
    """Fail closed when deciding whether an interrupted attempt was pre-attribution."""
    if not run_dir.is_dir():
        return False
    events, malformed = iter_jsonl(run_dir / "transcript.jsonl")
    if malformed:
        return True
    try:
        output, _ = extract_final_output(driver, run_dir, events)
        calls, unknown = detect_tool_events(driver, events, run_dir)
    except (OSError, ValueError, json.JSONDecodeError):
        return True
    workspace = run_dir / "workspace.diff"
    return bool(output or calls or unknown or (workspace.is_file() and workspace.stat().st_size))


def terminate_process_group(process: subprocess.Popen[Any]) -> None:
    """Stop an interrupted driver and every target process in its session."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def validate_prior_attempt_provenance(manifest: dict[str, Any], ledger: list[dict[str, Any]]) -> list[str]:
    """Recheck immutable anchors before a resumed command may make another paid call."""
    errors: list[str] = []
    slots = {
        slot["slot_id"]: slot
        for slot in [*(manifest.get("schedule") or []), *(manifest.get("reserve_slots") or [])]
    }
    for row in ledger:
        if not isinstance(row, dict):
            continue
        slot = slots.get(row.get("slot_id"))
        if slot is None:
            continue
        if row.get("analysis_eligible") is True or row.get("artifact_manifest_sha256") is not None:
            _, row_errors = validate_run_provenance(manifest, slot, row)
            errors.extend(row_errors)
        for path_key, hash_key in (
            ("failure_receipt", "failure_receipt_sha256"),
            ("quarantine_receipt", "quarantine_receipt_sha256"),
        ):
            raw_path = row.get(path_key)
            if raw_path is None:
                continue
            try:
                path = (ROOT / str(raw_path)).resolve()
                path.relative_to(ROOT.resolve())
            except (OSError, ValueError):
                errors.append(f"{row.get('slot_id')}: unsafe {path_key}")
                continue
            if path.is_symlink() or not path.is_file():
                errors.append(f"{row.get('slot_id')}: missing regular {path_key}")
            elif not re.fullmatch(r"[0-9a-f]{64}", str(row.get(hash_key) or "")):
                errors.append(f"{row.get('slot_id')}: {path_key} lacks a content hash")
            elif sha256_path(path) != row.get(hash_key):
                errors.append(f"{row.get('slot_id')}: {path_key} content hash mismatch")
    return errors


def run_slots(
    manifest_path: Path,
    *,
    approval: str | None,
    requested_slots: set[str] | None,
    dry_run: bool,
    reserve_slot: str | None = None,
    replacement_for: str | None = None,
    exclusion_reason: str | None = None,
) -> None:
    manifest = load_json(manifest_path)
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("manifest invalid:\n- " + "\n- ".join(errors))
    if manifest["phase"] == "confirmatory" and not dry_run and approval != manifest["freeze_id"]:
        raise PermissionError(
            "confirmatory execution is embargoed; after explicit user approval, pass --approval " + manifest["freeze_id"]
        )
    schedule = manifest["schedule"]
    ledger_path = ROOT / manifest["bout_dir"] / "EXECUTION.jsonl"
    ledger, malformed = iter_jsonl(ledger_path) if ledger_path.is_file() else ([], [])
    if malformed:
        raise ValueError(f"execution ledger is malformed at lines {malformed}")
    ledger_errors = validate_execution_ledger(manifest, ledger)
    if ledger_errors:
        raise ValueError("execution ledger is invalid:\n- " + "\n- ".join(ledger_errors))
    provenance_errors = validate_prior_attempt_provenance(manifest, ledger)
    if provenance_errors:
        raise ValueError("prior attempt provenance is invalid:\n- " + "\n- ".join(provenance_errors))
    if reserve_slot:
        if requested_slots:
            raise ValueError("--reserve and --slot cannot be combined")
        if not replacement_for or not exclusion_reason:
            raise ValueError("reserve execution requires --replacement-for and --exclusion-reason")
        allowed_reasons = set(manifest["exclusions"]["replace_only"])
        if exclusion_reason not in allowed_reasons:
            raise ValueError(f"replacement reason is not preregistered: {exclusion_reason}")
        reserve = next((slot for slot in manifest.get("reserve_slots") or [] if slot["slot_id"] == reserve_slot), None)
        if reserve is None:
            raise ValueError("reserve slot is not in the frozen manifest")
        replaced_row = next((row for row in ledger if row.get("slot_id") == replacement_for), None)
        if replaced_row is None or replaced_row.get("analysis_eligible") is not False:
            raise ValueError("the replaced attempt must exist in the ledger and be objectively ineligible")
        if reserve["condition_id"] != replaced_row.get("condition_id"):
            raise ValueError("reserve and replaced attempt belong to different conditions")
        if exclusion_reason not in set(replaced_row.get("eligible_exclusion_reasons") or []):
            raise ValueError("replacement reason is not supported by the replaced attempt's recorded evidence")
        if any(row.get("replacement_for") == replacement_for for row in ledger):
            raise ValueError("the replaced attempt already has an executed replacement")
        if any(row.get("slot_id") == reserve_slot for row in ledger):
            raise ValueError("the selected reserve slot has already been attempted")
        condition_reserves = [
            slot
            for slot in manifest.get("reserve_slots") or []
            if slot["condition_id"] == reserve["condition_id"]
        ]
        attempted = {row.get("slot_id") for row in ledger}
        next_reserve = next((slot for slot in condition_reserves if slot["slot_id"] not in attempted), None)
        if next_reserve is None or next_reserve["slot_id"] != reserve_slot:
            raise ValueError("reserve execution must use the next frozen reserve index for its condition")
        runtime_reserve = dict(reserve)
        runtime_reserve["replacement_for"] = replacement_for
        runtime_reserve["exclusion_reason"] = exclusion_reason
        schedule = [runtime_reserve]
    else:
        attempted_primary = [
            row["slot_id"] for row in ledger if row.get("kind") == "primary"
        ]
        schedule = schedule[len(attempted_primary) :]
        if manifest["phase"] == "confirmatory":
            children = {
                row.get("replacement_for"): row
                for row in ledger
                if row.get("replacement_for") is not None
            }
            for primary_id in attempted_primary:
                row = next(item for item in ledger if item.get("slot_id") == primary_id)
                while row.get("analysis_eligible") is False and row.get("slot_id") in children:
                    row = children[row["slot_id"]]
                if row.get("analysis_eligible") is not True:
                    raise ValueError(
                        f"primary attempt {primary_id} has no eligible replacement; run its next reserve before resuming"
                    )
    if requested_slots and not reserve_slot:
        known = {slot["slot_id"] for slot in schedule}
        unknown = requested_slots - known
        if unknown:
            raise ValueError(f"requested slots are not pending primary slots: {sorted(unknown)}")
        selected = [slot for slot in schedule if slot["slot_id"] in requested_slots]
        if selected != schedule[: len(selected)]:
            raise ValueError("requested primary slots must be a contiguous prefix of the frozen pending order")
        schedule = selected
    if dry_run:
        for slot in schedule:
            command, _ = driver_command(manifest, slot)
            print(json.dumps({"slot_id": slot["slot_id"], "command": command}))
        return

    base_env = dict(os.environ)
    initial_preflight = preflight_manifest(manifest, {slot["condition_id"] for slot in schedule}, base_env)
    for slot in schedule:
        run_dir = output_dir_for(manifest, slot)
        if run_dir.exists():
            raise FileExistsError(f"refusing to overwrite {run_dir}")
        existing_ledger, malformed = iter_jsonl(ledger_path) if ledger_path.is_file() else ([], [])
        if malformed:
            raise ValueError(f"execution ledger is malformed at lines {malformed}")
        existing_errors = validate_execution_ledger(manifest, existing_ledger)
        existing_errors.extend(validate_prior_attempt_provenance(manifest, existing_ledger))
        if existing_errors:
            raise ValueError(
                "prior attempt provenance changed before the next call:\n- "
                + "\n- ".join(existing_errors)
            )
        if any(row.get("slot_id") == slot["slot_id"] for row in existing_ledger):
            raise ValueError(f"execution ledger already contains {slot['slot_id']}")
        prior_policy_signatures = {
            row.get("instruction_policy_signature_sha256")
            for row in existing_ledger
            if row.get("condition_id") == slot["condition_id"] and row.get("instruction_policy_signature_sha256")
        }
        if len(prior_policy_signatures) > 1:
            raise ValueError(f"execution ledger already contains policy drift for {slot['condition_id']}")
        expected_policy_signature = next(iter(prior_policy_signatures), None)
        command, env = driver_command(manifest, slot)
        current_preflight = preflight_manifest(manifest, {slot["condition_id"]}, env)[slot["condition_id"]]
        if current_preflight["sha256"] != initial_preflight[slot["condition_id"]]["sha256"]:
            raise ValueError(f"treatment preflight drifted before {slot['slot_id']}")
        quarantine_destination(manifest, slot)
        env["ARENA_HARNESS_COMMIT"] = current_preflight["harness_commit"]
        env["ARENA_HARNESS_TRACKED_DIRTY"] = "false"
        attempt_root, staged_run_dir, command, env = prepare_staged_driver(
            manifest, slot, env
        )
        started = utc_now()
        record: dict[str, Any] | None = None
        driver_exit: int | None = None
        driver_process_spawned = False
        target_process_started = False
        target_process_returned = False
        process: subprocess.Popen[Any] | None = None
        caught: BaseException | None = None
        quarantine: dict[str, Any] | None = None
        attributable_activity: bool | None = None
        cleanup_signal: int | None = None
        prior_dumpable = process_dumpable()
        dumpability_lowered = False
        watched_signals = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
        previous_signal_handlers = {signum: signal.getsignal(signum) for signum in watched_signals}

        def interrupt_active_attempt(signum: int, _frame: Any) -> None:
            for watched in watched_signals:
                signal.signal(watched, signal.SIG_IGN)
            raise OperatorTermination(signum)

        def record_cleanup_interruption(signum: int, _frame: Any) -> None:
            nonlocal cleanup_signal
            cleanup_signal = signum

        for signum in watched_signals:
            signal.signal(signum, interrupt_active_attempt)
        try:
            process_dumpable(0)
            dumpability_lowered = True
            process = subprocess.Popen(
                command,
                cwd=attempt_root,
                env=env,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            driver_process_spawned = True
            driver_exit = process.wait()
            recover_and_remove_staged_driver(attempt_root, staged_run_dir, run_dir)
            target_process_started = (run_dir / "target_started").is_file()
            target_process_returned = (run_dir / "target_returned").is_file()
            scan_run_credentials(
                condition_map(manifest)[slot["condition_id"]]["driver"],
                env,
                run_dir,
                "credential_scan.raw.json",
            )
            if driver_exit == 86:
                raise SecretLeakError("per-run credential-state scan failed")
            if driver_exit not in {0, None}:
                raise RuntimeError(f"driver wrapper exited with status {driver_exit}")
            record = observe_run(
                manifest,
                slot,
                run_dir,
                expected_policy_signature=expected_policy_signature,
                finalize_artifact_manifest=False,
            )
        except BaseException as exc:  # ledger preservation also covers operator interruption
            caught = exc
        finally:
            if process is not None:
                terminate_process_group(process)
                driver_exit = process.returncode
            if attempt_root.exists():
                try:
                    recover_and_remove_staged_driver(attempt_root, staged_run_dir, run_dir)
                except BaseException as stage_exc:
                    if caught is None or not isinstance(caught, (KeyboardInterrupt, SystemExit)):
                        caught = stage_exc
            if dumpability_lowered:
                try:
                    process_dumpable(prior_dumpable)
                except BaseException as dumpable_exc:
                    if caught is None or not isinstance(caught, (KeyboardInterrupt, SystemExit)):
                        caught = dumpable_exc
            target_process_started = target_process_started or (run_dir / "target_started").is_file()
            target_process_returned = target_process_returned or (run_dir / "target_returned").is_file()
            interrupted_before_cleanup = isinstance(caught, KeyboardInterrupt) or driver_exit in {
                -signal.SIGINT,
                -signal.SIGTERM,
                -signal.SIGHUP,
            }
            if interrupted_before_cleanup:
                attributable_activity = raw_attempt_has_attributable_activity(
                    condition_map(manifest)[slot["condition_id"]]["driver"], run_dir
                )
            for signum in watched_signals:
                signal.signal(signum, record_cleanup_interruption)
            if run_dir.is_dir():
                try:
                    runtime_scan_issues = credential_receipt_issues(
                        run_dir / "credential_scan.runtime.json",
                        condition_map(manifest)[slot["condition_id"]]["driver"],
                    )
                    if target_process_started and runtime_scan_issues:
                        raise credential_guard.CredentialGuardError(
                            "runtime credential-state scan evidence failed validation"
                        )
                    scan_run_credentials(
                        condition_map(manifest)[slot["condition_id"]]["driver"],
                        env,
                        run_dir,
                        "credential_scan.json",
                    )
                    if isinstance(caught, SecretLeakError):
                        raise caught
                    if record is not None:
                        write_artifact_manifest(manifest, slot, run_dir)
                except BaseException as scan_exc:
                    if caught is None or not isinstance(caught, (KeyboardInterrupt, SystemExit)):
                        caught = scan_exc
                    record = None
                    try:
                        quarantine = quarantine_run(manifest, slot, run_dir)
                    except BaseException as quarantine_exc:
                        if caught is None or not isinstance(caught, (KeyboardInterrupt, SystemExit)):
                            caught = quarantine_exc
                        try:
                            quarantine = write_quarantine_failure(
                                manifest, slot, run_dir, quarantine_exc
                            )
                        except BaseException as receipt_exc:
                            quarantine = {
                                "succeeded": False,
                                "receipt": None,
                                "receipt_error_type": type(receipt_exc).__name__,
                            }
        if record is not None:
            validity_state = record["validity"]["state"]
            analysis_eligible = record["validity"]["confirmatory_analysis_eligible"]
            objective_issues = record["validity"]["technical_issues"]
            eligible_reasons = eligible_exclusion_reasons(record)
            smoke_excluded = record["validity"]["smoke_excluded"]
            failure_receipt = None
        else:
            quarantine_succeeded = bool(quarantine and quarantine.get("succeeded"))
            validity_state = (
                "security_quarantined"
                if quarantine_succeeded
                else "security_quarantine_failed"
                if quarantine
                else "runner_or_normalization_failure"
            )
            analysis_eligible = False
            smoke_excluded = manifest["phase"] == "smoke"
            objective_issues = [
                "security quarantine after secret scan"
                if quarantine_succeeded
                else "atomic security quarantine failed; run halted for manual recovery"
                if quarantine
                else f"{type(caught).__name__ if caught else 'UnknownError'} during driver or normalization"
            ]
            eligible_reasons = ([
                "security_quarantine_after_secret_scan"
                if quarantine_succeeded
                else "corrupted_or_missing_raw_artifact_due_to_harness"
                if driver_process_spawned or target_process_started
                else "harness_crash_before_target_execution"
            ] if not quarantine or quarantine_succeeded else [])
            interrupted = isinstance(caught, KeyboardInterrupt) or driver_exit in {
                -signal.SIGINT,
                -signal.SIGTERM,
                -signal.SIGHUP,
            }
            if (
                interrupted
                and target_process_started
                and attributable_activity is False
            ):
                eligible_reasons.append(
                    "external_termination_before_attributable_target_completion"
                )
            eligible_reasons = sorted(set(eligible_reasons))
            failure_receipt = write_attempt_failure(
                manifest,
                slot,
                {
                    "schema_version": 1,
                    "slot_id": slot["slot_id"],
                    "started_at": started,
                    "finished_at": utc_now(),
                    "driver_exit": driver_exit,
                    "driver_process_spawned": driver_process_spawned,
                    "target_process_started": target_process_started,
                    "target_process_returned": target_process_returned,
                    "error_type": type(caught).__name__ if caught else "UnknownError",
                    "error_message": str(caught) if caught else "unknown driver or normalization failure",
                    "quarantine": quarantine,
                },
            )
        try:
            append_ledger(
                ledger_path,
                {
                    "schema_version": 1,
                    "slot_id": slot["slot_id"],
                    "phase": manifest["phase"],
                    "condition_id": slot["condition_id"],
                    "kind": slot.get("kind", "primary"),
                    "replacement_for": slot.get("replacement_for"),
                    "exclusion_reason": slot.get("exclusion_reason"),
                    "run_dir": relative(run_dir),
                    "started_at": started,
                    "finished_at": utc_now(),
                    "driver_exit": driver_exit,
                    "validity_state": validity_state,
                    "analysis_eligible": analysis_eligible,
                    "smoke_excluded": smoke_excluded,
                    "objective_issues": objective_issues,
                    "eligible_exclusion_reasons": eligible_reasons,
                    "preflight": current_preflight,
                    "failure_receipt": failure_receipt,
                    "failure_receipt_sha256": sha256_path(ROOT / failure_receipt) if failure_receipt else None,
                    "quarantine_receipt": quarantine.get("receipt") if quarantine else None,
                    "quarantine_receipt_sha256": (
                        sha256_path(ROOT / quarantine["receipt"])
                        if quarantine and quarantine.get("receipt")
                        else None
                    ),
                    "artifact_manifest_sha256": sha256_path(run_dir / "artifact_manifest.json")
                    if record is not None and (run_dir / "artifact_manifest.json").is_file()
                    else None,
                    "instruction_policy_signature_sha256": (
                        record["configuration"]["instruction_policy_signature"]["sha256"]
                        if record is not None
                        else None
                    ),
                },
            )
        finally:
            for signum, prior_handler in previous_signal_handlers.items():
                signal.signal(signum, prior_handler)
        if cleanup_signal is not None and caught is None:
            caught = OperatorTermination(cleanup_signal)
        if caught is not None:
            if isinstance(caught, (KeyboardInterrupt, SystemExit)):
                raise caught
            raise RuntimeError(f"attempt {slot['slot_id']} failed after its ledger row was preserved") from caught
        if record is not None and record["validity"]["state"] == "invalid_setup":
            raise RuntimeError(f"attempt {slot['slot_id']} failed the run-integrity gate; matrix halted")


def make_blind_packets(manifest_path: Path, output_dir: Path, key: str) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    if manifest.get("phase") != "confirmatory":
        raise ValueError("smoke outputs may not enter semantic-review packets")
    if len(key.encode()) < 32 or len(set(key)) < 8:
        raise ValueError("blinding key must contain at least 32 bytes and 8 distinct characters")
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("manifest invalid: " + "; ".join(errors))
    ledger_path = ROOT / manifest["bout_dir"] / "EXECUTION.jsonl"
    ledger, malformed = iter_jsonl(ledger_path) if ledger_path.is_file() else ([], [])
    if malformed:
        raise ValueError(f"execution ledger is malformed at lines {malformed}")
    effective, ledger_errors = select_effective_attempts(manifest, ledger)
    if ledger_errors:
        raise ValueError("execution ledger cannot produce a frozen matrix: " + "; ".join(ledger_errors))
    frozen_slots = {
        slot["slot_id"]: slot for slot in [*manifest["schedule"], *(manifest.get("reserve_slots") or [])]
    }
    packets = []
    mapping = []
    observed_run_ids: set[tuple[str, str]] = set()
    for primary in manifest["schedule"]:
        attempt_row = effective[primary["slot_id"]]
        attempt_slot = frozen_slots[attempt_row["slot_id"]]
        run_dir = ROOT / attempt_row["run_dir"]
        record, provenance_errors = validate_run_provenance(manifest, attempt_slot, attempt_row)
        if provenance_errors:
            raise ValueError("effective attempt provenance failed: " + "; ".join(provenance_errors))
        assert record is not None
        if not record["validity"]["confirmatory_analysis_eligible"]:
            raise ValueError(f"ledger eligibility disagrees with run record for {attempt_row.get('slot_id')}")
        driver = record["condition"]["driver"]
        identifier_key = {"claude": "session_id", "codex": "thread_id", "kimi": "session_id"}[driver]
        identifiers = ((record.get("configuration") or {}).get("run_identifiers") or {}).get(identifier_key) or []
        if len(identifiers) != 1:
            raise ValueError(f"effective attempt lacks exactly one {identifier_key}: {attempt_row.get('slot_id')}")
        identity = (driver, identifiers[0])
        if identity in observed_run_ids:
            raise ValueError(f"duplicate emitted run/session identifier: {driver}")
        observed_run_ids.add(identity)
        text = (run_dir / "final_output.txt").read_text()
        blind_id = "P-" + hmac.new(key.encode(), primary["slot_id"].encode(), hashlib.sha256).hexdigest()[:16]
        packets.append({"blind_id": blind_id, "output_sha256": sha256_bytes(text.encode()), "output": text})
        mapping.append(
            {
                "blind_id": blind_id,
                "primary_slot_id": primary["slot_id"],
                "attempt_slot_id": attempt_row["slot_id"],
                "condition_id": primary["condition_id"],
                "run_dir": relative(run_dir),
                "output_sha256": sha256_bytes(text.encode()),
            }
        )
    # HMAC-derived order prevents the public randomized schedule from revealing
    # condition labels by packet position. The custodian mapping stays withheld.
    packets.sort(key=lambda packet: packet["blind_id"])
    mapping.sort(key=lambda item: item["blind_id"])
    output_dir.mkdir(parents=True, exist_ok=False)
    review_dir = output_dir / "reviewer"
    custodian_dir = output_dir / "custodian"
    review_dir.mkdir(mode=0o755)
    custodian_dir.mkdir(mode=0o700)
    common = {"schema_version": 1, "experiment_id": manifest["experiment_id"], "manifest_freeze_id": manifest["freeze_id"]}
    write_json(review_dir / "review-packets.json", {**common, "packets": packets})
    map_path = custodian_dir / "blind-map.json"
    write_json(map_path, {**common, "mapping": mapping})
    map_path.chmod(0o600)
    return {"packets": packets, "mapping": mapping}


def _find_slot(manifest: dict[str, Any], slot_id: str) -> dict[str, Any]:
    for slot in manifest.get("schedule") or []:
        if slot.get("slot_id") == slot_id:
            return slot
    raise ValueError(f"slot not found: {slot_id}")


def command_manifest(args: argparse.Namespace) -> None:
    manifest = build_manifest(
        phase=args.phase,
        output=Path(args.output).resolve(),
        design=Path(args.design).resolve(),
        analysis_script=Path(args.analysis_script).resolve(),
        report_template=Path(args.report_template).resolve(),
        repeats=args.runs,
        seed=args.seed,
        frozen_at=args.frozen_at,
        reserve_per_condition=args.reserves,
        replace_draft=args.replace_draft,
    )
    print(manifest["freeze_id"])


def command_validate(args: argparse.Namespace) -> None:
    manifest = load_json(Path(args.manifest))
    errors = validate_manifest(manifest, check_files=not args.no_file_check)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        raise SystemExit(1)
    print(f"valid {manifest['phase']} manifest: {manifest['freeze_id']}")


def command_preflight(args: argparse.Namespace) -> None:
    manifest = load_json(Path(args.manifest))
    snapshots = preflight_manifest(manifest, set(condition_map(manifest)), dict(os.environ))
    print(json.dumps({"manifest_freeze_id": manifest["freeze_id"], "conditions": snapshots}, indent=2))


def command_observe(args: argparse.Namespace) -> None:
    manifest = load_json(Path(args.manifest))
    slot = _find_slot(manifest, args.slot)
    record = observe_run(manifest, slot, output_dir_for(manifest, slot))
    print(json.dumps(record["validity"], indent=2))


def command_verify(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    errors = verify_artifacts(run_dir)
    manifest_path = next(
        (parent / "MANIFEST.json" for parent in run_dir.parents if (parent / "MANIFEST.json").is_file()),
        None,
    )
    if manifest_path is None:
        errors.append("no enclosing frozen MANIFEST.json found")
    else:
        manifest = load_json(manifest_path)
        errors.extend(validate_manifest(manifest))
        ledger_path = manifest_path.parent / "EXECUTION.jsonl"
        ledger, malformed = iter_jsonl(ledger_path) if ledger_path.is_file() else ([], [])
        if malformed:
            errors.append(f"execution ledger malformed at lines {malformed}")
        errors.extend(validate_execution_ledger(manifest, ledger))
        try:
            run_rel = relative(run_dir)
        except ValueError:
            run_rel = ""
        rows = [row for row in ledger if row.get("run_dir") == run_rel]
        if len(rows) != 1:
            errors.append("run directory is not anchored exactly once in the execution ledger")
        else:
            slots = {
                slot["slot_id"]: slot
                for slot in [*(manifest.get("schedule") or []), *(manifest.get("reserve_slots") or [])]
            }
            slot = slots.get(rows[0].get("slot_id"))
            if slot is None:
                errors.append("execution ledger row does not reference a frozen slot")
            else:
                _, provenance_errors = validate_run_provenance(manifest, slot, rows[0])
                errors.extend(provenance_errors)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        raise SystemExit(1)
    print("artifact integrity: OK")


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="command", required=True)
    manifest = sub.add_parser("manifest", help="construct a frozen randomized manifest")
    manifest.add_argument("--phase", choices=("smoke", "confirmatory"), required=True)
    manifest.add_argument("--output", required=True)
    manifest.add_argument("--design", required=True)
    manifest.add_argument("--analysis-script", required=True)
    manifest.add_argument("--report-template", required=True)
    manifest.add_argument("--runs", type=int, required=True)
    manifest.add_argument("--reserves", type=int, default=5)
    manifest.add_argument("--seed", type=int, required=True)
    manifest.add_argument("--frozen-at", required=True)
    manifest.add_argument(
        "--replace-draft",
        action="store_true",
        help="replace only a same-experiment draft that has no run artifacts or execution ledger",
    )
    manifest.set_defaults(func=command_manifest)
    validate = sub.add_parser("validate", help="validate a frozen manifest and its inputs")
    validate.add_argument("manifest")
    validate.add_argument("--no-file-check", action="store_true")
    validate.set_defaults(func=command_validate)
    preflight = sub.add_parser("preflight", help="run every no-API treatment gate")
    preflight.add_argument("manifest")
    preflight.set_defaults(func=command_preflight)
    run = sub.add_parser("run", help="execute manifest slots serially")
    run.add_argument("manifest")
    run.add_argument("--approval")
    run.add_argument("--slot", action="append", dest="slots")
    run.add_argument("--reserve", dest="reserve_slot")
    run.add_argument("--replacement-for")
    run.add_argument("--exclusion-reason")
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(
        func=lambda args: run_slots(
            Path(args.manifest),
            approval=args.approval,
            requested_slots=set(args.slots) if args.slots else None,
            dry_run=args.dry_run,
            reserve_slot=args.reserve_slot,
            replacement_for=args.replacement_for,
            exclusion_reason=args.exclusion_reason,
        )
    )
    observe = sub.add_parser("observe", help="regenerate normalized evidence for one run")
    observe.add_argument("manifest")
    observe.add_argument("--slot", required=True)
    observe.set_defaults(func=command_observe)
    verify = sub.add_parser("verify-run", help="verify a run's content-addressed artifacts")
    verify.add_argument("run_dir")
    verify.set_defaults(func=command_verify)
    blind = sub.add_parser("blind", help="create label-free semantic-review packets")
    blind.add_argument("manifest")
    blind.add_argument("--output-dir", required=True)
    blind.add_argument("--key-env", default="ARENA_BLIND_KEY")
    blind.set_defaults(
        func=lambda args: print(
            json.dumps(
                {
                    "packet_count": len(
                        make_blind_packets(
                            Path(args.manifest),
                            Path(args.output_dir),
                            os.environ.get(args.key_env)
                            or (_ for _ in ()).throw(ValueError(f"missing blinding key in {args.key_env}")),
                        )["packets"]
                    )
                }
            )
        )
    )
    return cli


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    try:
        args.func(args)
    except (FileExistsError, PermissionError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
