#!/usr/bin/env python3
"""Frozen-manifest runner and observable-evidence tooling for task 16.

The experiment measures final-answer and trace behavior. It never reads or
scores hidden reasoning. Raw driver artifacts remain untouched; normalized
artifacts are content-addressed derivatives.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import itertools
import json
import os
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
TASK_REL = "tasks/16-pre-requirements-plan"
PROMPT_REL = f"{TASK_REL}/PROMPT.md"
FROZEN_PROMPT_SHA256 = "5d8df8bce37fba5832273d20f99d4ef05abd87c3590be62ceed349e90f3da2b0"
EXPERIMENT_ID = "2026-08-22-pre-requirements-planning"
RAW_ARTIFACTS = {
    "claude": ["transcript.jsonl", "result.json"],
    "codex": ["transcript.jsonl", "last_message.txt", "session.jsonl"],
    "kimi": ["transcript.jsonl", "wire.jsonl"],
}
COMMON_ARTIFACTS = [
    "agent_exit",
    "metrics.json",
    "peek_check",
    "prompt.txt",
    "run_env.json",
    "stderr.log",
    "wall_seconds",
    "workspace.diff",
    "workspace.diffstat",
]
PASSIVE_CODEX_ITEMS = {"agent_message", "error", "reasoning", "plan"}
CALL_SESSION_TYPES = {
    "computer_call",
    "custom_tool_call",
    "function_call",
    "local_shell_call",
    "mcp_tool_call",
    "web_search_call",
}


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
            "expected_model_substring": "claude-opus-5",
            "expected_cli_version": "2.1.241 (Claude Code)",
            "effort": {"mode": "native_default", "cli_argument": None, "observed_value": "not_exposed"},
            "instruction_configuration": "project setting source in a neutral scratch repository",
            "tool_configuration": "native default tools enabled",
        },
        {
            "condition_id": "codex--gpt-5.6-sol",
            "driver": "codex",
            "requested_model": "gpt-5.6-sol",
            "model_argument": "gpt-5.6-sol",
            "output_label": "gpt-5.6-sol-codex",
            "expected_model_substring": "gpt-5.6-sol",
            "expected_cli_version": "codex-cli 0.149.0",
            "effort": {"mode": "native_default", "cli_argument": None, "observed_value": "not_exposed"},
            "instruction_configuration": "isolated CODEX_HOME with --ignore-user-config",
            "tool_configuration": "native default tools enabled; schemas opaque unless present in session rollout",
        },
        {
            "condition_id": "kimi-code--kimi-k3",
            "driver": "kimi",
            "requested_model": "kimi-k3",
            "model_argument": "arena/k3",
            "output_label": "kimi-k3-kimicode",
            "expected_model_substring": "kimi-k3",
            "expected_cli_version": "kimi-code 0.27.0",
            "effort": {"mode": "native_default", "cli_argument": None, "observed_value": "max"},
            "instruction_configuration": "isolated Kimi arena HOME and config.toml",
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
    frozen_files = [
        prompt,
        ROOT / TASK_REL / "SCORING.md",
        ROOT / TASK_REL / "review.schema.json",
        ROOT / TASK_REL / "adjudication.schema.json",
        design,
        analysis_script,
        report_template,
        ROOT / "bin/plan_experiment.py",
        ROOT / "bin/run-task.sh",
        ROOT / "bin/run-task-codex.sh",
        ROOT / "bin/run-task-kimi.sh",
        ROOT / "env/prices.json",
    ]
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
        "bout_dir": bout_dir,
        "task": {
            "path": TASK_REL,
            "target_prompt": prompt.read_text(),
            "prompt_sha256": sha256_path(prompt),
            "prompt_bytes": prompt.stat().st_size,
            "compatibility_amendments": [],
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
            "primary_endpoints": ["A_ge_2", "B_ge_2", "C_eq_3", "D_ge_2", "full_gate_chain", "restraint_pass", "embargo_pass"],
            "interval": "two-sided 95% Wilson score interval",
            "no_omnibus_score_or_confirmatory_pairwise_ranking": True,
            "hidden_reasoning_scored": False,
        },
        "artifact_contract": {
            "raw_outputs_immutable": True,
            "required_common": COMMON_ARTIFACTS,
            "required_by_driver": RAW_ARTIFACTS,
            "derived": ["final_output.txt", "embargo.json", "instruction_context.json", "run_record.json", "artifact_manifest.json"],
        },
        "frozen_inputs": [file_record(path) for path in frozen_files],
    }
    manifest["freeze_id"] = sha256_bytes(canonical_json(manifest))
    output.parent.mkdir(parents=True, exist_ok=True)
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
    if check_files:
        if not prompt_path.is_file():
            errors.append("target prompt file missing")
        else:
            data = prompt_path.read_bytes()
            if sha256_bytes(data) != task.get("prompt_sha256"):
                errors.append("target prompt file hash mismatch")
            if data.decode() != task.get("target_prompt"):
                errors.append("manifest target prompt text mismatch")
        for rec in manifest.get("frozen_inputs") or []:
            path = ROOT / rec.get("path", "")
            if not path.is_file():
                errors.append(f"frozen input missing: {rec.get('path')}")
            elif sha256_path(path) != rec.get("sha256") or path.stat().st_size != rec.get("bytes"):
                errors.append(f"frozen input drift: {rec.get('path')}")
    conditions = condition_map(manifest) if manifest.get("conditions") else {}
    if len(conditions) != len(manifest.get("conditions") or []):
        errors.append("duplicate condition_id")
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


def detect_tool_events(driver: str, events: list[dict[str, Any]], run_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    calls: dict[str, dict[str, Any]] = {}
    unknown: list[str] = []
    if driver == "claude":
        for event in events:
            if event.get("type") != "assistant":
                continue
            for index, block in enumerate((event.get("message") or {}).get("content") or []):
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type in {"tool_use", "server_tool_use", "mcp_tool_use"}:
                    event_id = str(block.get("id") or f"line-{event['_line']}-block-{index}")
                    calls[event_id] = {
                        "event_id": event_id,
                        "source": "transcript.jsonl",
                        "line": event["_line"],
                        "name": str(block.get("name") or block_type),
                        "event_type": block_type,
                    }
            parent = event.get("parent_tool_use_id")
            if parent and str(parent) not in calls:
                calls[str(parent)] = {
                    "event_id": str(parent),
                    "source": "transcript.jsonl",
                    "line": event["_line"],
                    "name": "nested_agent_activity",
                    "event_type": "parent_tool_use_id",
                }
    elif driver == "codex":
        for event in events:
            if event.get("type") not in {"item.started", "item.completed"}:
                continue
            item = event.get("item") or {}
            item_type = item.get("type") or item.get("item_type")
            if item_type in PASSIVE_CODEX_ITEMS:
                continue
            if not item_type:
                unknown.append(f"transcript.jsonl:{event['_line']}:missing item type")
                continue
            event_id = str(item.get("id") or f"line-{event['_line']}")
            calls[event_id] = {
                "event_id": event_id,
                "source": "transcript.jsonl",
                "line": event["_line"],
                "name": _event_name_from_input(item),
                "event_type": str(item_type),
            }
        session_path = run_dir / "session.jsonl"
        session_events, session_bad = iter_jsonl(session_path) if session_path.is_file() else ([], [])
        unknown.extend(f"session.jsonl:{line}:malformed" for line in session_bad)
        for event in session_events:
            if event.get("type") != "response_item":
                continue
            payload = event.get("payload") or {}
            payload_type = payload.get("type")
            if payload_type not in CALL_SESSION_TYPES:
                continue
            event_id = str(payload.get("call_id") or payload.get("id") or f"session-line-{event['_line']}")
            if event_id not in calls:
                calls[event_id] = {
                    "event_id": event_id,
                    "source": "session.jsonl",
                    "line": event["_line"],
                    "name": str(payload.get("name") or payload_type),
                    "event_type": str(payload_type),
                }
    elif driver == "kimi":
        for event in events:
            if event.get("role") != "assistant":
                continue
            for index, call in enumerate(event.get("tool_calls") or []):
                if not isinstance(call, dict):
                    unknown.append(f"transcript.jsonl:{event['_line']}:malformed tool call")
                    continue
                function = call.get("function") or {}
                event_id = str(call.get("id") or f"line-{event['_line']}-call-{index}")
                calls[event_id] = {
                    "event_id": event_id,
                    "source": "transcript.jsonl",
                    "line": event["_line"],
                    "name": str(function.get("name") or call.get("type") or "unknown_tool"),
                    "event_type": str(call.get("type") or "tool_call"),
                }
        wire_path = run_dir / "wire.jsonl"
        wire_events, wire_bad = iter_jsonl(wire_path) if wire_path.is_file() else ([], [])
        unknown.extend(f"wire.jsonl:{line}:malformed" for line in wire_bad)
        for event in wire_events:
            if event.get("type") != "context.append_loop_event":
                continue
            loop_event = event.get("event") or {}
            if loop_event.get("type") != "tool.call":
                continue
            event_id = str(loop_event.get("toolCallId") or loop_event.get("uuid") or f"wire-line-{event['_line']}")
            if event_id not in calls:
                calls[event_id] = {
                    "event_id": event_id,
                    "source": "wire.jsonl",
                    "line": event["_line"],
                    "name": str(loop_event.get("name") or "tool.call"),
                    "event_type": "tool.call",
                }
    else:
        raise ValueError(f"unknown driver: {driver}")
    return sorted(calls.values(), key=lambda item: (item["source"], item["line"], item["event_id"])), unknown


def classify_calls(calls: list[dict[str, Any]], workspace_changed: bool) -> dict[str, bool]:
    names = [call["name"].lower() for call in calls]
    types = [call["event_type"].lower() for call in calls]
    spawned = any(
        name in {"task", "agent", "agentswarm", "spawn_agent", "collaboration.spawn_agent"}
        or "spawn_agent" in name
        or "agent_swarm" in name
        or event_type in {"collab_agent_tool_call"}
        for name, event_type in zip(names, types)
    )
    inspected = any(
        name in {"read", "grep", "glob", "command_execution", "bash", "functions.exec", "exec_command"}
        for name in names
    )
    researched = any(
        token in name
        for name in names
        for token in ("websearch", "web_search", "webfetch", "fetchurl", "fetch_url", "research")
    )
    mutated = workspace_changed or any(
        name in {"write", "edit", "apply_patch", "file_change"} or event_type == "file_change"
        for name, event_type in zip(names, types)
    )
    return {
        "target_originated_tool_or_function_call": bool(calls),
        "spawned_agent": spawned,
        "repository_or_file_inspection": inspected,
        "research_or_network_action": researched,
        "implementation_or_mutation_attempt": mutated,
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
                requests.append(clean)
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
    effort: Any = None
    identity_kind = "served"
    if driver == "claude":
        for event in events:
            model = (event.get("message") or {}).get("model") if event.get("type") == "assistant" else None
            if isinstance(model, str) and model not in models:
                models.append(model)
        identity_kind = "served_response_tag"
    elif driver == "codex":
        for turn in context.get("turn_contexts") or []:
            model = turn.get("model")
            if isinstance(model, str) and model not in models:
                models.append(model)
            settings = ((turn.get("collaboration_mode") or {}).get("settings") or {})
            if settings.get("reasoning_effort") is not None:
                effort = settings["reasoning_effort"]
        identity_kind = "requested_turn_context_only"
    elif driver == "kimi":
        for request in context.get("requests") or []:
            model = request.get("model")
            if isinstance(model, str) and model not in models:
                models.append(model)
            if request.get("thinkingEffort") is not None:
                effort = request["thinkingEffort"]
        identity_kind = "request_wire_record"
    return {"models": models, "identity_kind": identity_kind, "observed_effort": effort}


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
        value = {
            "base_instructions": context.get("base_instructions"),
            "developer_messages": [
                message for message in context.get("pre_response_messages") or [] if message.get("role") == "developer"
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
        }
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
    for path in sorted(run_dir.iterdir()):
        if not path.is_file() or path.name in excluded:
            continue
        data = path.read_bytes()
        records.append({"path": path.name, "sha256": sha256_bytes(data), "bytes": len(data)})
    return records


def observe_run(manifest: dict[str, Any], slot: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    condition = condition_map(manifest)[slot["condition_id"]]
    driver = condition["driver"]
    events, malformed = iter_jsonl(run_dir / "transcript.jsonl")
    output, output_source = extract_final_output(driver, run_dir, events)
    (run_dir / "final_output.txt").write_text(output)
    calls, trace_unknown = detect_tool_events(driver, events, run_dir)
    workspace_changed = bool((run_dir / "workspace.diff").is_file() and (run_dir / "workspace.diff").stat().st_size)
    classifications = classify_calls(calls, workspace_changed)
    embargo = {
        "schema_version": 1,
        "slot_id": slot["slot_id"],
        "pass": not classifications["target_originated_tool_or_function_call"] and not workspace_changed,
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
    policy_signature = instruction_policy_signature(driver, context)
    metrics = load_json(run_dir / "metrics.json") if (run_dir / "metrics.json").is_file() else {}
    run_env = load_json(run_dir / "run_env.json") if (run_dir / "run_env.json").is_file() else {}
    required = COMMON_ARTIFACTS + RAW_ARTIFACTS[driver]
    missing = [name for name in required if not (run_dir / name).is_file()]
    technical_issues = [f"missing required artifact: {name}" for name in missing]
    technical_issues.extend(f"malformed transcript line: {line}" for line in malformed)
    technical_issues.extend(context_issues)
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
    expected_model = condition.get("expected_model_substring")
    if observed["models"] and not any(expected_model in model for model in observed["models"]):
        technical_issues.append(f"model mismatch: expected substring {expected_model!r}, observed {observed['models']!r}")
    if driver in {"claude", "kimi"} and not observed["models"]:
        technical_issues.append("observable model identity missing")
    if driver == "kimi" and observed.get("observed_effort") != condition["effort"].get("observed_value"):
        technical_issues.append(
            f"effort drift: expected {condition['effort'].get('observed_value')!r}, got {observed.get('observed_effort')!r}"
        )
    peek = (run_dir / "peek_check").read_text(errors="replace") if (run_dir / "peek_check").is_file() else ""
    if "SECRET LEAK" in peek:
        technical_issues.append("secret leak marker present; quarantine and do not publish raw content")
    output_bytes = output.encode()
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
            "run_identifiers": run_identifiers(driver, events),
            "instruction_policy_signature": policy_signature,
            "workspace_instruction_files": [
                relative(path)
                for name in ("AGENTS.md", "CLAUDE.md")
                for path in (ROOT / manifest["task"]["path"] / "fixture").rglob(name)
            ],
        },
        "metrics": metrics,
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
    write_json(run_dir / "run_record.json", record)
    write_json(
        run_dir / "artifact_manifest.json",
        {
            "schema_version": 1,
            "slot_id": slot["slot_id"],
            "manifest_freeze_id": manifest["freeze_id"],
            "artifacts": artifact_records(run_dir),
        },
    )
    return record


def verify_artifacts(run_dir: Path) -> list[str]:
    path = run_dir / "artifact_manifest.json"
    if not path.is_file():
        return ["artifact_manifest.json missing"]
    try:
        manifest = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"artifact manifest unreadable: {exc}"]
    errors = []
    for record in manifest.get("artifacts") or []:
        artifact = run_dir / record.get("path", "")
        if not artifact.is_file():
            errors.append(f"artifact missing: {record.get('path')}")
        elif sha256_path(artifact) != record.get("sha256") or artifact.stat().st_size != record.get("bytes"):
            errors.append(f"artifact changed: {record.get('path')}")
    return errors


def output_dir_for(manifest: dict[str, Any], slot: dict[str, Any]) -> Path:
    condition = condition_map(manifest)[slot["condition_id"]]
    return ROOT / manifest["bout_dir"] / Path(manifest["task"]["path"]).name / condition["output_label"] / f"run-{slot['replicate']}"


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
    env = dict(os.environ)
    env["ARENA_TIMEOUT_S"] = "600"
    if driver == "claude":
        env["ARENA_EFFORT"] = "native-default"
        env["ARENA_SETTING_SOURCES"] = "project"
    elif driver == "kimi":
        env["ARENA_KIMI_LABEL"] = condition["output_label"]
        env["ARENA_KIMI_EFFORT"] = "native-default (observed in wire journal)"
    return command, env


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
    if reserve_slot:
        if requested_slots:
            raise ValueError("--reserve and --slot cannot be combined")
        if not replacement_for or not exclusion_reason:
            raise ValueError("reserve execution requires --replacement-for and --exclusion-reason")
        allowed_reasons = set(manifest["exclusions"]["replace_only"])
        if exclusion_reason not in allowed_reasons:
            raise ValueError(f"replacement reason is not preregistered: {exclusion_reason}")
        reserve = next((slot for slot in manifest.get("reserve_slots") or [] if slot["slot_id"] == reserve_slot), None)
        primary = next((slot for slot in manifest["schedule"] if slot["slot_id"] == replacement_for), None)
        if reserve is None or primary is None:
            raise ValueError("reserve or replaced primary slot is not in the frozen manifest")
        if reserve["condition_id"] != primary["condition_id"]:
            raise ValueError("reserve and replaced primary slot belong to different conditions")
        ledger_path = ROOT / manifest["bout_dir"] / "EXECUTION.jsonl"
        ledger, malformed = iter_jsonl(ledger_path) if ledger_path.is_file() else ([], [])
        if malformed:
            raise ValueError(f"execution ledger is malformed at lines {malformed}")
        primary_row = next((row for row in ledger if row.get("slot_id") == replacement_for), None)
        if primary_row is None or primary_row.get("analysis_eligible") is not False:
            raise ValueError("the replaced primary must exist in the ledger and be objectively ineligible")
        if any(row.get("replacement_for") == replacement_for for row in ledger):
            raise ValueError("the primary slot already has an executed replacement")
        runtime_reserve = dict(reserve)
        runtime_reserve["replacement_for"] = replacement_for
        runtime_reserve["exclusion_reason"] = exclusion_reason
        schedule = [runtime_reserve]
    elif requested_slots:
        known = {slot["slot_id"] for slot in schedule}
        unknown = requested_slots - known
        if unknown:
            raise ValueError(f"unknown or non-primary slot ids: {sorted(unknown)}")
        schedule = [slot for slot in schedule if slot["slot_id"] in requested_slots]
    for slot in schedule:
        run_dir = output_dir_for(manifest, slot)
        if run_dir.exists():
            raise FileExistsError(f"refusing to overwrite {run_dir}")
        command, env = driver_command(manifest, slot)
        if dry_run:
            print(json.dumps({"slot_id": slot["slot_id"], "command": command}))
            continue
        started = utc_now()
        completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
        record = observe_run(manifest, slot, run_dir)
        append_ledger(
            ROOT / manifest["bout_dir"] / "EXECUTION.jsonl",
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
                "driver_exit": completed.returncode,
                "validity_state": record["validity"]["state"],
                "analysis_eligible": record["validity"]["confirmatory_analysis_eligible"],
                "smoke_excluded": record["validity"]["smoke_excluded"],
            },
        )


def make_blind_packets(manifest_path: Path, output_dir: Path, key: str) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    if manifest.get("phase") != "confirmatory":
        raise ValueError("smoke outputs may not enter semantic-review packets")
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("manifest invalid: " + "; ".join(errors))
    ledger_path = ROOT / manifest["bout_dir"] / "EXECUTION.jsonl"
    ledger, malformed = iter_jsonl(ledger_path) if ledger_path.is_file() else ([], [])
    if malformed:
        raise ValueError(f"execution ledger is malformed at lines {malformed}")
    ledger_by_slot = {row.get("slot_id"): row for row in ledger}
    packets = []
    mapping = []
    incomplete = []
    for primary in manifest["schedule"]:
        primary_row = ledger_by_slot.get(primary["slot_id"])
        attempt_row = primary_row if primary_row and primary_row.get("analysis_eligible") is True else None
        if attempt_row is None:
            replacements = [
                row
                for row in ledger
                if row.get("replacement_for") == primary["slot_id"] and row.get("analysis_eligible") is True
            ]
            if len(replacements) > 1:
                raise ValueError(f"multiple eligible replacements for {primary['slot_id']}")
            attempt_row = replacements[0] if replacements else None
        if attempt_row is None:
            incomplete.append(primary["slot_id"])
            continue
        run_dir = ROOT / attempt_row["run_dir"]
        record_path = run_dir / "run_record.json"
        if not record_path.is_file():
            raise ValueError(f"missing run record for effective attempt {attempt_row.get('slot_id')}")
        record = load_json(record_path)
        if not record["validity"]["confirmatory_analysis_eligible"]:
            raise ValueError(f"ledger eligibility disagrees with run record for {attempt_row.get('slot_id')}")
        text = (run_dir / "final_output.txt").read_text(errors="replace")
        blind_id = "P-" + hmac.new(key.encode(), primary["slot_id"].encode(), hashlib.sha256).hexdigest()[:16]
        packets.append({"blind_id": blind_id, "output_sha256": sha256_bytes(text.encode()), "output": text})
        mapping.append(
            {
                "blind_id": blind_id,
                "primary_slot_id": primary["slot_id"],
                "attempt_slot_id": attempt_row["slot_id"],
                "condition_id": primary["condition_id"],
                "run_dir": relative(run_dir),
            }
        )
    if incomplete:
        raise ValueError(f"confirmatory matrix is incomplete; no eligible attempt for {incomplete}")
    output_dir.mkdir(parents=True, exist_ok=False)
    write_json(output_dir / "review-packets.json", {"schema_version": 1, "packets": packets})
    write_json(output_dir / "blind-map.json", {"schema_version": 1, "mapping": mapping})
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
    )
    print(manifest["freeze_id"])


def command_validate(args: argparse.Namespace) -> None:
    manifest = load_json(Path(args.manifest))
    errors = validate_manifest(manifest, check_files=not args.no_file_check)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        raise SystemExit(1)
    print(f"valid {manifest['phase']} manifest: {manifest['freeze_id']}")


def command_observe(args: argparse.Namespace) -> None:
    manifest = load_json(Path(args.manifest))
    slot = _find_slot(manifest, args.slot)
    record = observe_run(manifest, slot, output_dir_for(manifest, slot))
    print(json.dumps(record["validity"], indent=2))


def command_verify(args: argparse.Namespace) -> None:
    errors = verify_artifacts(Path(args.run_dir))
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
    manifest.set_defaults(func=command_manifest)
    validate = sub.add_parser("validate", help="validate a frozen manifest and its inputs")
    validate.add_argument("manifest")
    validate.add_argument("--no-file-check", action="store_true")
    validate.set_defaults(func=command_validate)
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
    except (FileExistsError, PermissionError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
