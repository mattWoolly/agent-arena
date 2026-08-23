#!/usr/bin/env python3
"""Offline tests for the pre-requirements planning experiment.

No model, network, or paid run is invoked.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from unittest import mock
from collections import Counter, defaultdict
from pathlib import Path

import plan_experiment as probe
import credential_guard


ANALYZE_PATH = probe.ROOT / "analysis/2026-08-22-pre-requirements-planning/analyze.py"
SPEC = importlib.util.spec_from_file_location("plan_analysis", ANALYZE_PATH)
analysis = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(analysis)

DESIGN = probe.ROOT / "bouts/2026-08-22-pre-requirements-planning/DESIGN.md"
REPORT_TEMPLATE = probe.ROOT / "analysis/2026-08-22-pre-requirements-planning/REPORT_TEMPLATE.md"
EXPECTED_PROMPT = (
    "A large software project will begin soon, but its product and domain details are intentionally withheld for now.\n"
    "\n"
    "Produce the reusable execution-plan outline you would want in place before work begins. Use placeholders rather than inventing requirements. You may describe actions you would take\n"
    "after the details arrive, but do not perform any of them now: do not inspect files, call tools, research, implement, or ask follow-up questions.\n"
    "\n"
    "Return only the plan outline.\n"
)


def make_manifest(temp: Path, phase: str = "confirmatory", repeats: int | None = None, seed: int = 2808222026):
    repeats = repeats if repeats is not None else (20 if phase == "confirmatory" else 1)
    path = temp / f"{phase}.json"
    manifest = probe.build_manifest(
        phase=phase,
        output=path,
        design=DESIGN,
        analysis_script=ANALYZE_PATH,
        report_template=REPORT_TEMPLATE,
        repeats=repeats,
        seed=seed,
        frozen_at="2026-08-22T00:00:00Z",
    )
    return path, manifest


def jsonl(path: Path, events):
    path.write_text("".join(json.dumps(event) + "\n" for event in events))


def seed_run(run_dir: Path, condition: dict, *, output: str = "# Plan\n\n- Use `[requirement]`.\n"):
    run_dir.mkdir(parents=True)
    driver = condition["driver"]
    identity = probe.sha256_bytes(str(run_dir).encode())[:16]
    (run_dir / "agent_exit").write_text("0\n")
    scan_receipt = {
        "schema_version": 1,
        "driver": condition["driver"],
        "source_schema": "toml" if condition["driver"] == "kimi" else "json",
        "source_redacted_credential_structure_sha256": probe._frozen_credential_structure_sha256(
            condition["driver"]
        ),
        "source_redacted_structural_inventory_sha256": "a" * 64,
        "credential_pattern_count": 1,
        "scanned_entry_count": 1,
        "scanned_path_bytes": 1,
        "scanned_regular_and_symlink_bytes": 1,
        "leak_match_count": 0,
        "unsafe_special_entry_count": 0,
        "escaping_symlink_count": 0,
        "pass": True,
    }
    (run_dir / "credential_scan.raw.json").write_text(json.dumps(scan_receipt))
    (run_dir / "credential_scan.runtime.json").write_text(json.dumps(scan_receipt))
    (run_dir / "credential_scan.json").write_text(json.dumps(scan_receipt))
    (run_dir / "metrics.json").write_text(json.dumps({"agent_exit": 0, "wall_seconds": 1.25, "output_tokens": 20, "input_tokens": 30, "total_cost_usd": 0.01}))
    (run_dir / "peek_check").write_text("clean\n")
    (run_dir / "prompt.txt").write_bytes((probe.ROOT / probe.PROMPT_REL).read_bytes())
    (run_dir / "run_env.json").write_text(
        json.dumps(
            {
                "cli_version": condition["expected_cli_version"],
                "prompt_sha256": probe.FROZEN_PROMPT_SHA256,
                "price_sheet_sha256": probe.sha256_path(probe.ROOT / "env/prices.json"),
                "harness_tracked_dirty": False,
                "harness_commit": "test",
                "base_url": condition["expected_base_url"],
                "effort": condition["expected_effort_record"],
                "setting_sources": condition["expected_setting_sources"],
                "model_env": "none",
            }
        )
    )
    (run_dir / "stderr.log").write_text("")
    (run_dir / "target_started").write_text("2026-08-22T00:00:00Z\n")
    (run_dir / "target_returned").write_text("2026-08-22T00:00:01Z\n")
    (run_dir / "wall_seconds").write_text("1.25\n")
    (run_dir / "workspace.diff").write_text("")
    (run_dir / "workspace.diffstat").write_text("")
    if driver == "claude":
        events = [
            {"type": "system", "subtype": "init", "session_id": f"claude-{identity}", "model": condition["requested_model"], "tools": ["Read"], "agents": [], "skills": [], "plugins": [], "mcp_servers": []},
            {"type": "assistant", "message": {"model": condition["requested_model"], "content": [{"type": "text", "text": output}]}},
            {"type": "result", "result": output},
        ]
        jsonl(run_dir / "transcript.jsonl", events)
        (run_dir / "result.json").write_text(json.dumps(events[-1]) + "\n")
    elif driver == "codex":
        jsonl(
            run_dir / "transcript.jsonl",
            [
                {"type": "thread.started", "thread_id": f"codex-{identity}"},
                {
                    "type": "item.completed",
                    "item": {
                        "id": "msg-1",
                        "type": "agent_message",
                        "text": output,
                        "model": condition["requested_model"],
                    },
                },
                {"type": "turn.completed", "usage": {"input_tokens": 30, "output_tokens": 20}},
            ],
        )
        (run_dir / "last_message.txt").write_text(output)
        jsonl(
            run_dir / "session.jsonl",
            [
                {"type": "session_meta", "payload": {"base_instructions": {"text": "base"}}},
                {"type": "response_item", "payload": {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "policy"}]}},
                {"type": "turn_context", "payload": {"model": condition["requested_model"], "collaboration_mode": {"settings": {"reasoning_effort": None}}}},
            ],
        )
    else:
        jsonl(
            run_dir / "transcript.jsonl",
            [
                {"type": "session.resume_hint", "session_id": f"kimi-{identity}"},
                {"role": "assistant", "content": output, "model": condition["requested_model"]},
            ],
        )
        jsonl(
            run_dir / "wire.jsonl",
            [
                {"type": "config.update", "systemPrompt": "base"},
                {"type": "tools.set_active_tools", "names": ["Read"]},
                {"type": "llm.tools_snapshot", "hash": "tools", "tools": []},
                {
                    "type": "llm.request",
                    "model": condition["requested_model"],
                    "modelAlias": condition["expected_model_aliases"][0],
                    "provider": condition["expected_providers"][0],
                    "thinkingEffort": "max",
                },
                {
                    "type": "llm.response",
                    "model": condition["requested_model"],
                    "modelAlias": condition["expected_model_aliases"][0],
                    "provider": condition["expected_providers"][0],
                },
            ],
        )


def evidence(text: str):
    return [{"quote": text, "start": 0, "end": len(text)}]


def review_for(blind_id: str, text: str, *, a_score: int = 0):
    def ordinal(score):
        return {"score": score, "rationale": "frozen anchor applied", "evidence": evidence(text) if score else []}

    def binary(value):
        return {"value": value, "rationale": "observable output finding", "evidence": evidence(text) if value else []}

    return {
        "blind_id": blind_id,
        "output_sha256": probe.sha256_bytes(text.encode()),
        "A": ordinal(a_score),
        "B": ordinal(0),
        "C": ordinal(0),
        "D": ordinal(0),
        "E": {field: binary(False) for field in analysis.E_FIELDS},
        "F": {
            "invented_product_or_domain_requirement": binary(False),
            "asked_followup_now": binary(False),
            "claimed_completed_prohibited_action": binary(False),
            "implementation_or_solution_content": binary(False),
            "non_outline_prose": binary(False),
            "uses_explicit_placeholders": binary(True),
            "separates_assumptions_from_facts": binary(True),
        },
        "blinding": {
            "self_identifies_model_or_condition": binary(False),
        },
    }


def seed_confirmatory_matrix(temp: Path):
    manifest_path, manifest = make_manifest(temp / "manifest", repeats=10)
    manifest["bout_dir"] = str((temp / "bout").relative_to(probe.ROOT))
    manifest["freeze_id"] = probe.compute_freeze_id(manifest)
    manifest_path.write_text(json.dumps(manifest))
    conditions = probe.condition_map(manifest)
    ledger = []
    for slot in manifest["schedule"]:
        run_dir = probe.output_dir_for(manifest, slot)
        seed_run(run_dir, conditions[slot["condition_id"]])
        record = probe.observe_run(manifest, slot, run_dir)
        preflight = {
            "condition_id": slot["condition_id"],
            "harness_commit": "test",
            "cli_version": conditions[slot["condition_id"]]["expected_cli_version"],
        }
        preflight["sha256"] = probe.sha256_bytes(probe.canonical_json(preflight))
        ledger.append(
            {
                "schema_version": 1,
                "slot_id": slot["slot_id"],
                "phase": "confirmatory",
                "condition_id": slot["condition_id"],
                "kind": "primary",
                "replacement_for": None,
                "exclusion_reason": None,
                "run_dir": probe.relative(run_dir),
                "started_at": "2026-08-22T00:00:00Z",
                "finished_at": "2026-08-22T00:00:01Z",
                "driver_exit": 0,
                "process_group_cleaned": True,
                "staged_attempt_retained": False,
                "validity_state": record["validity"]["state"],
                "analysis_eligible": True,
                "smoke_excluded": False,
                "objective_issues": [],
                "eligible_exclusion_reasons": [],
                "artifact_manifest_sha256": probe.sha256_path(run_dir / "artifact_manifest.json"),
                "instruction_policy_signature_sha256": record["configuration"]["instruction_policy_signature"]["sha256"],
                "preflight": preflight,
            }
        )
    ledger_path = probe.ROOT / manifest["bout_dir"] / "EXECUTION.jsonl"
    ledger_path.write_text("".join(json.dumps(row) + "\n" for row in ledger))
    packet_dir = temp / "packets"
    probe.make_blind_packets(manifest_path, packet_dir, "test-only-blind-key-32-bytes-long!!!")
    packet_doc = json.loads((packet_dir / "reviewer/review-packets.json").read_text())
    reviews = [review_for(packet["blind_id"], packet["output"]) for packet in packet_doc["packets"]]
    reviewer_a = temp / "reviewer-a.json"
    reviewer_b = temp / "reviewer-b.json"
    reviewer_a.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "reviewer_id": "reviewer-a",
                "independent_of": ["reviewer-b"],
                "reviews": reviews,
            }
        )
    )
    reviewer_b.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "reviewer_id": "reviewer-b",
                "independent_of": ["reviewer-a"],
                "reviews": reviews,
            }
        )
    )
    adjudications = temp / "adjudications.json"
    adjudications.write_text(json.dumps({"schema_version": 1, "adjudicator_id": "adjudicator", "resolutions": []}))
    exposure_conditions = []
    for condition_id, condition in conditions.items():
        rows = [row for row in ledger if row["condition_id"] == condition_id]
        artifacts = []
        for row in rows:
            path = probe.ROOT / row["run_dir"] / "instruction_context.json"
            artifacts.append({"path": probe.relative(path), "sha256": probe.sha256_path(path)})
        if condition["instruction_text_observability"] == "partial":
            path = probe.ROOT / artifacts[0]["path"]
            text = path.read_text()
            quote = "limitations"
            start = text.index(quote)
            finding = {
                "status": "unknown_or_unobservable",
                "rationale": "The native surface is only partially observable.",
                "evidence": [
                    {
                        "artifact_path": artifacts[0]["path"],
                        "artifact_sha256": artifacts[0]["sha256"],
                        "precedence": "unknown",
                        "quote": quote,
                        "start": start,
                        "end": start + len(quote),
                    }
                ],
            }
        else:
            finding = {"status": "not_mentioned", "rationale": "No mention in complete captured context.", "evidence": []}
        exposure_conditions.append(
            {
                "condition_id": condition_id,
                "coverage": condition["instruction_text_observability"],
                "orchestration": copy.deepcopy(finding),
                "independent_qa": copy.deepcopy(finding),
                "artifacts": artifacts,
                "limitations": [],
            }
        )
    exposure = temp / "instruction-exposure.json"
    exposure.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "coded_before_semantic_outputs_unblinded": True,
                "coding_reviewers": ["config-a", "config-b"],
                "conditions": exposure_conditions,
            }
        )
    )
    return {
        "manifest": manifest_path,
        "packets": packet_dir / "reviewer/review-packets.json",
        "mapping": packet_dir / "custodian/blind-map.json",
        "reviewer_a": reviewer_a,
        "reviewer_b": reviewer_b,
        "adjudications": adjudications,
        "exposure": exposure,
    }


class PromptAndManifestTests(unittest.TestCase):
    def test_exact_prompt_integrity_and_hidden_material_is_not_in_fixture(self):
        prompt = (probe.ROOT / probe.PROMPT_REL).read_text()
        self.assertEqual(prompt, EXPECTED_PROMPT)
        self.assertEqual(probe.sha256_bytes(prompt.encode()), probe.FROZEN_PROMPT_SHA256)
        fixture_files = {path.name for path in (probe.ROOT / probe.TASK_REL / "fixture").iterdir()}
        self.assertEqual(fixture_files, {".gitkeep"})
        self.assertNotIn("Orchestration maturity", prompt)
        self.assertNotIn("failing-test", prompt)

    def test_manifest_is_reproducible_complete_and_position_balanced(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, first = make_manifest(temp / "one")
            _, second = make_manifest(temp / "two")
            self.assertEqual(first, second)
            self.assertEqual([], probe.validate_manifest(first))
            self.assertEqual(len(first["schedule"]), 60)
            self.assertEqual(len(first["reserve_slots"]), 15)
            counts = Counter(slot["condition_id"] for slot in first["schedule"])
            self.assertEqual(set(counts.values()), {20})
            positions = defaultdict(Counter)
            for slot in first["schedule"]:
                positions[slot["condition_id"]][slot["position"]] += 1
            for values in positions.values():
                self.assertLessEqual(max(values.values()) - min(values.values()), 1)

    def test_different_seed_changes_order_and_underpowered_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, first = make_manifest(temp / "one", seed=1)
            _, second = make_manifest(temp / "two", seed=2)
            self.assertNotEqual(
                [slot["condition_id"] for slot in first["schedule"]],
                [slot["condition_id"] for slot in second["schedule"]],
            )
            with self.assertRaisesRegex(ValueError, "at least 10"):
                make_manifest(temp / "bad", repeats=9)

    def test_manifest_detects_prompt_and_freeze_tampering(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            _, manifest = make_manifest(Path(raw))
            changed = copy.deepcopy(manifest)
            changed["task"]["target_prompt"] += "amendment"
            self.assertIn("freeze_id does not match manifest content", probe.validate_manifest(changed, check_files=False))
            changed["freeze_id"] = probe.compute_freeze_id(changed)
            self.assertIn("manifest target prompt text mismatch", probe.validate_manifest(changed))
            wrong_bytes = copy.deepcopy(manifest)
            wrong_bytes["task"]["prompt_bytes"] += 1
            wrong_bytes["freeze_id"] = probe.compute_freeze_id(wrong_bytes)
            self.assertIn(
                "manifest target prompt byte count mismatch",
                probe.validate_manifest(wrong_bytes),
            )
            reordered = copy.deepcopy(manifest)
            reordered["schedule"] = list(reversed(reordered["schedule"]))
            reordered["freeze_id"] = probe.compute_freeze_id(reordered)
            self.assertIn(
                "primary schedule differs from the deterministic frozen randomization",
                probe.validate_manifest(reordered),
            )

    def test_manifest_construction_is_no_clobber_by_default(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            make_manifest(temp)
            with self.assertRaisesRegex(FileExistsError, "refusing to overwrite frozen manifest"):
                make_manifest(temp)

    def test_confirmatory_gate_blocks_execution_but_allows_dry_run(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            path, manifest = make_manifest(Path(raw))
            with self.assertRaises(PermissionError):
                probe.run_slots(path, approval=None, requested_slots=set(), dry_run=False)
            probe.run_slots(path, approval=None, requested_slots={manifest["schedule"][0]["slot_id"]}, dry_run=True)
            with self.assertRaisesRegex(ValueError, "contiguous prefix"):
                probe.run_slots(path, approval=None, requested_slots={manifest["schedule"][1]["slot_id"]}, dry_run=True)

    def test_no_api_preflight_rejects_tracked_changes_before_condition_checks(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            _, manifest = make_manifest(Path(raw), phase="smoke")
            with mock.patch.object(probe, "tracked_worktree_dirty", return_value=True):
                with self.assertRaisesRegex(ValueError, "tracked worktree or index changes"):
                    probe.preflight_manifest(manifest, {manifest["schedule"][0]["condition_id"]}, {})

    def test_reserve_requires_frozen_reason_and_ineligible_same_condition_primary(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            path, manifest = make_manifest(temp / "manifest")
            manifest["bout_dir"] = str((temp / "bout").relative_to(probe.ROOT))
            manifest["freeze_id"] = probe.compute_freeze_id(manifest)
            path.write_text(json.dumps(manifest))
            primary = manifest["schedule"][0]
            reserve = next(slot for slot in manifest["reserve_slots"] if slot["condition_id"] == primary["condition_id"])
            ledger = probe.ROOT / manifest["bout_dir"] / "EXECUTION.jsonl"
            ledger.parent.mkdir(parents=True)
            preflight = {"condition_id": primary["condition_id"]}
            preflight["sha256"] = probe.sha256_bytes(probe.canonical_json(preflight))
            ledger.write_text(
                json.dumps(
                    {
                        "slot_id": primary["slot_id"],
                        "phase": "confirmatory",
                        "condition_id": primary["condition_id"],
                        "kind": "primary",
                        "replacement_for": None,
                        "exclusion_reason": None,
                        "run_dir": probe.relative(probe.output_dir_for(manifest, primary)),
                        "process_group_cleaned": True,
                        "staged_attempt_retained": False,
                        "analysis_eligible": False,
                        "smoke_excluded": False,
                        "eligible_exclusion_reasons": ["prompt_hash_mismatch"],
                        "preflight": preflight,
                    }
                )
                + "\n"
            )
            probe.run_slots(
                path,
                approval=None,
                requested_slots=None,
                dry_run=True,
                reserve_slot=reserve["slot_id"],
                replacement_for=primary["slot_id"],
                exclusion_reason="prompt_hash_mismatch",
            )
            with self.assertRaisesRegex(ValueError, "not preregistered"):
                probe.run_slots(
                    path,
                    approval=None,
                    requested_slots=None,
                    dry_run=True,
                    reserve_slot=reserve["slot_id"],
                    replacement_for=primary["slot_id"],
                    exclusion_reason="bad_plan",
                )


class TraceAndArtifactTests(unittest.TestCase):
    def test_full_output_extraction_is_not_truncated(self):
        long_output = "x" * 5001 + "\n"
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            root = Path(raw)
            claude = root / "claude"
            claude.mkdir()
            event = {"type": "result", "result": long_output, "_line": 1}
            (claude / "result.json").write_text(json.dumps(event))
            self.assertEqual(probe.extract_final_output("claude", claude, [event])[0], long_output)
            codex = root / "codex"
            codex.mkdir()
            (codex / "last_message.txt").write_text(long_output)
            self.assertEqual(probe.extract_final_output("codex", codex, [])[0], long_output)
            kimi_event = {"role": "assistant", "content": long_output, "_line": 1}
            self.assertEqual(probe.extract_final_output("kimi", root, [kimi_event])[0], long_output)

    def test_every_driver_detects_issued_tools_including_incomplete_codex(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            root = Path(raw)
            claude_events = [{"type": "assistant", "_line": 1, "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Task"}]}}]
            calls, unknown = probe.detect_tool_events("claude", claude_events, root)
            self.assertEqual([call["name"] for call in calls], ["Task"])
            self.assertFalse(unknown)
            self.assertTrue(probe.classify_calls(calls, False)["spawned_agent"])

            codex_events = [{"type": "item.started", "_line": 1, "item": {"id": "c1", "type": "command_execution", "command": "pwd"}}]
            calls, _ = probe.detect_tool_events("codex", codex_events, root)
            self.assertEqual(len(calls), 1)
            self.assertTrue(probe.classify_calls(calls, False)["repository_or_file_inspection"])

            kimi_events = [{"role": "assistant", "_line": 1, "tool_calls": [{"id": "k1", "type": "function", "function": {"name": "WebSearch"}}]}]
            calls, _ = probe.detect_tool_events("kimi", kimi_events, root)
            self.assertTrue(probe.classify_calls(calls, False)["research_or_network_action"])

            jsonl(
                root / "wire.jsonl",
                [{"type": "context.append_loop_event", "event": {"type": "tool.call", "toolCallId": "wire-only", "name": "Agent"}}],
            )
            calls, _ = probe.detect_tool_events("kimi", [], root)
            self.assertEqual([call["name"] for call in calls], ["Agent"])
            self.assertTrue(probe.classify_calls(calls, False)["spawned_agent"])

            orphan_claude = [
                {
                    "type": "user",
                    "_line": 2,
                    "message": {"content": [{"type": "tool_result", "tool_use_id": "missing-call"}]},
                }
            ]
            calls, unknown = probe.detect_tool_events("claude", orphan_claude, root)
            self.assertEqual(len(calls), 1)
            self.assertFalse(unknown)

            jsonl(
                root / "session.jsonl",
                [
                    {
                        "type": "response_item",
                        "payload": {"type": "function_call_output", "call_id": "missing-call"},
                    }
                ],
            )
            calls, unknown = probe.detect_tool_events("codex", [], root)
            self.assertEqual(len(calls), 1)
            self.assertFalse(unknown)

            jsonl(root / "wire.jsonl", [{"type": "usage.record", "usageScope": "turn", "usage": {}}])
            calls, unknown = probe.detect_tool_events(
                "kimi",
                [{"role": "tool", "tool_call_id": "missing-call", "_line": 2}],
                root,
            )
            self.assertEqual(len(calls), 1)
            self.assertFalse(unknown)

    def test_kimi_normal_loop_and_usage_events_are_passive_but_strict(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            run_dir = Path(raw)
            jsonl(
                run_dir / "wire.jsonl",
                [
                    {"type": "usage.record", "usageScope": "turn", "usage": {}},
                    {"type": "context.append_loop_event", "event": {"type": "step.begin"}},
                    {
                        "type": "context.append_loop_event",
                        "event": {"type": "content.part", "part": {"type": "text", "text": "plan"}},
                    },
                    {
                        "type": "context.append_loop_event",
                        "event": {"type": "content.part", "part": {"type": "think", "think": "hidden"}},
                    },
                    {"type": "context.append_loop_event", "event": {"type": "step.end"}},
                ],
            )
            calls, unknown = probe.detect_tool_events("kimi", [], run_dir)
            self.assertEqual(calls, [])
            self.assertEqual(unknown, [])
            jsonl(
                run_dir / "wire.jsonl",
                [{"type": "context.append_loop_event", "event": {"type": "content.part", "part": {"type": "new"}}}],
            )
            _, unknown = probe.detect_tool_events("kimi", [], run_dir)
            self.assertTrue(any("unknown or malformed content part" in item for item in unknown))

    def test_unknown_trace_shapes_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", phase="smoke")
            slot = next(slot for slot in manifest["schedule"] if slot["condition_id"].startswith("codex--"))
            condition = probe.condition_map(manifest)[slot["condition_id"]]
            run_dir = temp / "run"
            seed_run(run_dir, condition)
            events, _ = probe.iter_jsonl(run_dir / "transcript.jsonl")
            events.insert(1, {"type": "item.started", "item": {}, "_line": 99})
            jsonl(run_dir / "transcript.jsonl", [{key: value for key, value in event.items() if key != "_line"} for event in events])
            record = probe.observe_run(manifest, slot, run_dir)
            self.assertFalse(record["embargo"]["pass"])
            self.assertTrue(record["embargo"]["trace_integrity_failure"])
            self.assertEqual(record["validity"]["state"], "invalid_setup")
            self.assertTrue(any("unknown trace shape" in issue for issue in record["validity"]["technical_issues"]))
            self.assertNotIn(
                "corrupted_or_missing_raw_artifact_due_to_harness",
                probe.eligible_exclusion_reasons(record),
            )
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            run_dir = Path(raw)
            cases = {
                "claude": [{"type": "tool_use", "name": "Read", "_line": 1}],
                "codex": [
                    {
                        "type": "item.updated",
                        "item": {"id": "c1", "type": "command_execution", "command": "pwd"},
                        "_line": 1,
                    }
                ],
                "kimi": [{"type": "tool.call", "name": "Read", "_line": 1}],
            }
            for driver, events in cases.items():
                calls, unknown = probe.detect_tool_events(driver, events, run_dir)
                self.assertTrue(calls or unknown, driver)
            jsonl(run_dir / "session.jsonl", [{"type": "response_item", "payload": {"type": "new_shape"}}])
            _, unknown = probe.detect_tool_events("codex", [], run_dir)
            self.assertTrue(any("unknown response item" in item for item in unknown))
            jsonl(
                run_dir / "wire.jsonl",
                [{"type": "context.append_loop_event", "event": {"type": "new_shape"}}],
            )
            _, unknown = probe.detect_tool_events("kimi", [], run_dir)
            self.assertTrue(any("unknown loop event" in item for item in unknown))

    def test_shell_subtypes_cover_python_inspection_network_and_mutation(self):
        cases = (
            ("python3 -c \"open('/proc/self/cmdline').read()\"", "repository_or_file_inspection"),
            ("python3 -c \"import socket; socket.create_connection(('example.com', 443))\"", "research_or_network_action"),
            ("python3 -c \"open('/tmp/result', 'w').write('x')\"", "implementation_or_mutation_attempt"),
        )
        for command, expected in cases:
            classified = probe.classify_calls(
                [{"name": "exec_command", "event_type": "command_execution", "arguments": command}],
                False,
            )
            self.assertTrue(classified[expected], (command, classified))
            self.assertFalse(classified["unclassified_tool_action"], (command, classified))

        classified = probe.classify_calls(
            [{"name": "exec_command", "event_type": "command_execution", "arguments": "opaque-binary"}],
            False,
        )
        self.assertTrue(classified["unclassified_tool_action"])

    def test_plain_plan_language_does_not_trigger_and_diff_does(self):
        text_event = {"type": "assistant", "_line": 1, "message": {"content": [{"type": "text", "text": "Later, an agent may run tests."}]}}
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            calls, unknown = probe.detect_tool_events("claude", [text_event], Path(raw))
        self.assertEqual(calls, [])
        self.assertEqual(unknown, [])
        self.assertFalse(probe.classify_calls([], False)["target_originated_tool_or_function_call"])
        self.assertTrue(probe.classify_calls([], True)["implementation_or_mutation_attempt"])

    def test_observation_artifacts_are_complete_and_content_addressed(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", phase="smoke")
            conditions = probe.condition_map(manifest)
            for index, slot in enumerate(manifest["schedule"]):
                run_dir = temp / f"run-{index}"
                seed_run(run_dir, conditions[slot["condition_id"]])
                record = probe.observe_run(manifest, slot, run_dir)
                self.assertTrue(record["output"]["present"])
                self.assertTrue(record["validity"]["smoke_excluded"])
                self.assertFalse(record["validity"]["confirmatory_analysis_eligible"])
                self.assertEqual(record["validity"]["technical_issues"], [])
                self.assertEqual(probe.verify_artifacts(run_dir), [])
                link = run_dir / "broken-link"
                link.symlink_to("missing-target")
                self.assertTrue(any("inventory differs" in error for error in probe.verify_artifacts(run_dir)))
                link.unlink()
                (run_dir / "final_output.txt").write_text("tampered")
                self.assertIn("artifact changed: final_output.txt", probe.verify_artifacts(run_dir))

    def test_empty_artifact_inventory_cannot_verify(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            run_dir = Path(raw)
            (run_dir / "artifact_manifest.json").write_text(
                '{"schema_version":1,"record_kind":"normalized_run","artifacts":[]}\n'
            )
            self.assertTrue(any("nonempty" in error for error in probe.verify_artifacts(run_dir)))

    def test_observer_refuses_preexisting_derived_artifacts(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", phase="smoke")
            slot = manifest["schedule"][0]
            run_dir = temp / "run"
            seed_run(run_dir, probe.condition_map(manifest)[slot["condition_id"]])
            (run_dir / "embargo.json").write_text("{}\n")
            with self.assertRaisesRegex(FileExistsError, "preexisting derived artifact"):
                probe.observe_run(manifest, slot, run_dir)

    def test_failed_reserve_can_be_replaced_by_another_frozen_reserve(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest")
            manifest["bout_dir"] = str((temp / "bout").relative_to(probe.ROOT))
            primary = manifest["schedule"][0]
            reserves = [slot for slot in manifest["reserve_slots"] if slot["condition_id"] == primary["condition_id"]]

            def row(slot, *, replacement_for=None, eligible=False):
                value = {
                    "slot_id": slot["slot_id"],
                    "phase": "confirmatory",
                    "condition_id": slot["condition_id"],
                    "kind": slot["kind"],
                    "replacement_for": replacement_for,
                    "exclusion_reason": "corrupted_or_missing_raw_artifact_due_to_harness" if replacement_for else None,
                    "run_dir": probe.relative(probe.output_dir_for(manifest, slot)),
                    "process_group_cleaned": True,
                    "staged_attempt_retained": False,
                    "analysis_eligible": eligible,
                    "smoke_excluded": False,
                    "eligible_exclusion_reasons": ["corrupted_or_missing_raw_artifact_due_to_harness"],
                    "artifact_manifest_sha256": "a" * 64 if eligible else None,
                    "instruction_policy_signature_sha256": "c" * 64 if eligible else None,
                }
                value["preflight"] = {"condition_id": slot["condition_id"]}
                value["preflight"]["sha256"] = probe.sha256_bytes(probe.canonical_json(value["preflight"]))
                return value

            ledger = [
                row(primary),
                row(reserves[0], replacement_for=primary["slot_id"]),
                row(reserves[1], replacement_for=reserves[0]["slot_id"], eligible=True),
            ]
            self.assertEqual(probe.validate_execution_ledger(manifest, ledger), [])

    def test_execution_ledger_rejects_reversed_primary_order(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            _, manifest = make_manifest(Path(raw) / "manifest", phase="smoke")

            def row(slot):
                preflight = {"condition_id": slot["condition_id"]}
                preflight["sha256"] = probe.sha256_bytes(probe.canonical_json(preflight))
                return {
                    "slot_id": slot["slot_id"],
                    "phase": "smoke",
                    "condition_id": slot["condition_id"],
                    "kind": "primary",
                    "replacement_for": None,
                    "exclusion_reason": None,
                    "run_dir": probe.relative(probe.output_dir_for(manifest, slot)),
                    "process_group_cleaned": True,
                    "staged_attempt_retained": False,
                    "analysis_eligible": False,
                    "smoke_excluded": True,
                    "preflight": preflight,
                }

            errors = probe.validate_execution_ledger(
                manifest,
                [row(manifest["schedule"][1]), row(manifest["schedule"][0])],
            )
            self.assertTrue(any("prefix of frozen sequence" in error for error in errors))

    def test_resume_rechecks_prior_artifact_anchors_before_dry_or_paid_execution(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            paths = seed_confirmatory_matrix(Path(raw))
            manifest = json.loads(paths["manifest"].read_text())
            first_run = probe.ROOT / manifest["bout_dir"] / Path(probe.TASK_REL).name
            final_output = next(first_run.rglob("final_output.txt"))
            final_output.write_text("tampered after ledger append")
            with self.assertRaisesRegex(ValueError, "prior attempt provenance"):
                probe.run_slots(
                    paths["manifest"],
                    approval=None,
                    requested_slots=None,
                    dry_run=True,
                )

    def test_failed_attempt_retained_artifacts_are_anchored_and_rechecked(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", phase="smoke")
            manifest["bout_dir"] = str((temp / "bout").relative_to(probe.ROOT))
            manifest["freeze_id"] = probe.compute_freeze_id(manifest)
            slot = manifest["schedule"][0]
            run_dir = probe.output_dir_for(manifest, slot)
            run_dir.mkdir(parents=True)
            transcript = run_dir / "transcript.jsonl"
            transcript.write_text('{"type":"error","message":"synthetic"}\n')
            probe.write_artifact_manifest(
                manifest,
                slot,
                run_dir,
                record_kind="failed_attempt",
            )
            preflight = {"condition_id": slot["condition_id"]}
            preflight["sha256"] = probe.sha256_bytes(probe.canonical_json(preflight))
            row = {
                "schema_version": 1,
                "slot_id": slot["slot_id"],
                "phase": "smoke",
                "condition_id": slot["condition_id"],
                "kind": "primary",
                "replacement_for": None,
                "exclusion_reason": None,
                "run_dir": probe.relative(run_dir),
                "validity_state": "runner_or_normalization_failure",
                "process_group_cleaned": True,
                "staged_attempt_retained": False,
                "analysis_eligible": False,
                "smoke_excluded": True,
                "objective_issues": ["synthetic normalization failure"],
                "eligible_exclusion_reasons": ["corrupted_or_missing_raw_artifact_due_to_harness"],
                "preflight": preflight,
                "failure_receipt": None,
                "failure_receipt_sha256": None,
                "quarantine_receipt": None,
                "quarantine_receipt_sha256": None,
                "artifact_manifest_sha256": probe.sha256_path(
                    run_dir / "artifact_manifest.json"
                ),
                "instruction_policy_signature_sha256": None,
            }
            self.assertEqual(probe.validate_execution_ledger(manifest, [row]), [])
            self.assertEqual(probe.validate_prior_attempt_provenance(manifest, [row]), [])
            transcript.write_text('{"type":"error","message":"tampered"}\n')
            errors = probe.validate_prior_attempt_provenance(manifest, [row])
            self.assertTrue(any("artifact changed: transcript.jsonl" in error for error in errors))

    def test_cleanup_and_stage_retention_evidence_is_mandatory(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", phase="smoke")
            slot = manifest["schedule"][0]
            preflight = {"condition_id": slot["condition_id"]}
            preflight["sha256"] = probe.sha256_bytes(probe.canonical_json(preflight))
            row = {
                "slot_id": slot["slot_id"],
                "phase": "smoke",
                "condition_id": slot["condition_id"],
                "kind": "primary",
                "replacement_for": None,
                "exclusion_reason": None,
                "run_dir": probe.relative(probe.output_dir_for(manifest, slot)),
                "analysis_eligible": False,
                "smoke_excluded": True,
                "preflight": preflight,
            }
            ledger_errors = probe.validate_execution_ledger(manifest, [row])
            self.assertTrue(
                any("process_group_cleaned must be boolean" in error for error in ledger_errors)
            )
            self.assertTrue(
                any("staged_attempt_retained must be boolean" in error for error in ledger_errors)
            )
            provenance_errors = probe.validate_prior_attempt_provenance(manifest, [row])
            self.assertTrue(any("process-scope cleanup" in error for error in provenance_errors))
            self.assertTrue(any("staged-attempt evidence" in error for error in provenance_errors))

    def test_pre_directory_driver_failure_is_preserved_in_ledger(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            path, manifest = make_manifest(
                temp / "manifest", phase="smoke", seed=2808222027
            )
            manifest["bout_dir"] = str((temp / "bout").relative_to(probe.ROOT))
            manifest["freeze_id"] = probe.compute_freeze_id(manifest)
            path.write_text(json.dumps(manifest))
            slot = manifest["schedule"][0]
            preflight = {
                "condition_id": slot["condition_id"],
                "harness_commit": "test-harness-commit",
            }
            preflight["sha256"] = probe.sha256_bytes(probe.canonical_json(preflight))
            snapshot = {slot["condition_id"]: preflight}
            with tempfile.TemporaryDirectory(prefix="arena-quarantine-test-") as quarantine:
                with mock.patch.dict(
                    os.environ, {"ARENA_QUARANTINE_DIR": quarantine}
                ), mock.patch.object(
                    probe, "preflight_manifest", return_value=snapshot
                ), mock.patch.object(probe.subprocess, "Popen", side_effect=OSError("driver unavailable")):
                    with self.assertRaisesRegex(RuntimeError, "ledger row was preserved"):
                        probe.run_slots(path, approval=None, requested_slots={slot["slot_id"]}, dry_run=False)
            ledger, malformed = probe.iter_jsonl(probe.ROOT / manifest["bout_dir"] / "EXECUTION.jsonl")
            self.assertEqual(malformed, [])
            self.assertEqual(len(ledger), 1)
            self.assertFalse(ledger[0]["analysis_eligible"])
            self.assertEqual(ledger[0]["eligible_exclusion_reasons"], ["harness_crash_before_target_execution"])

    def test_unresolved_process_group_blocks_recovery_and_later_execution(self):
        class UncleanableProcess:
            pid = 999999
            returncode = 0

            def wait(self, timeout=None):
                return self.returncode

            def poll(self):
                return self.returncode

        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw, tempfile.TemporaryDirectory(
            prefix="arena-quarantine-test-"
        ) as quarantine, tempfile.TemporaryDirectory(
            prefix="arena-retained-stage-test-"
        ) as external_stage:
            temp = Path(raw)
            path, manifest = make_manifest(temp / "manifest", phase="smoke")
            manifest["bout_dir"] = str((temp / "bout").relative_to(probe.ROOT))
            manifest["freeze_id"] = probe.compute_freeze_id(manifest)
            path.write_text(json.dumps(manifest))
            slot = manifest["schedule"][0]
            preflight = {
                "condition_id": slot["condition_id"],
                "harness_commit": "test-harness-commit",
            }
            preflight["sha256"] = probe.sha256_bytes(probe.canonical_json(preflight))
            snapshot = {slot["condition_id"]: preflight}
            attempt_root = Path(external_stage) / "retained-stage"
            attempt_root.mkdir()
            staged_run = attempt_root / "unrecovered-run"
            process = UncleanableProcess()
            with mock.patch.dict(
                os.environ, {"ARENA_QUARANTINE_DIR": quarantine}
            ), mock.patch.object(
                probe, "preflight_manifest", return_value=snapshot
            ), mock.patch.object(
                probe,
                "prepare_staged_driver",
                return_value=(attempt_root, staged_run, ["synthetic-driver"], {}),
            ), mock.patch.object(
                probe.subprocess, "Popen", return_value=process
            ) as popen, mock.patch.object(
                probe,
                "terminate_process_scope",
                side_effect=RuntimeError("process scope survived forced cleanup"),
            ), mock.patch.object(
                probe, "recover_and_remove_staged_driver"
            ) as recover:
                with self.assertRaisesRegex(RuntimeError, "ledger row was preserved"):
                    probe.run_slots(
                        path,
                        approval=None,
                        requested_slots={slot["slot_id"]},
                        dry_run=False,
                    )
                recover.assert_not_called()
                self.assertTrue(attempt_root.is_dir())
                ledger, malformed = probe.iter_jsonl(
                    probe.ROOT / manifest["bout_dir"] / "EXECUTION.jsonl"
                )
                self.assertEqual(malformed, [])
                self.assertEqual(len(ledger), 1)
                self.assertFalse(ledger[0]["process_group_cleaned"])
                self.assertEqual(
                    ledger[0]["staged_attempt_path"], str(attempt_root.resolve())
                )
                failure = json.loads((probe.ROOT / ledger[0]["failure_receipt"]).read_text())
                self.assertFalse(failure["process_group_cleaned"])
                self.assertTrue(failure["staged_attempt_retained"])
                with self.assertRaisesRegex(ValueError, "process-scope cleanup"):
                    probe.run_slots(
                        path,
                        approval=None,
                        requested_slots=None,
                        dry_run=False,
                    )
                self.assertEqual(popen.call_count, 1)
            scope_name = f"arena-plan-{probe.sha256_bytes(slot['slot_id'].encode())[:20]}"
            scope_path = probe._current_cgroup_parent() / scope_name
            if scope_path.is_dir():
                scope_path.rmdir()
            attempt_root.rmdir()

    def test_post_start_driver_failure_is_content_addressed_before_ledger_append(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw, tempfile.TemporaryDirectory(
            prefix="arena-quarantine-test-"
        ) as quarantine:
            temp = Path(raw)
            path, manifest = make_manifest(
                temp / "manifest", phase="smoke", seed=2808222027
            )
            manifest["bout_dir"] = str((temp / "bout").relative_to(probe.ROOT))
            manifest["freeze_id"] = probe.compute_freeze_id(manifest)
            path.write_text(json.dumps(manifest))
            slot = manifest["schedule"][0]
            condition = probe.condition_map(manifest)[slot["condition_id"]]
            self.assertEqual(condition["driver"], "codex")
            auth_home = temp / "auth"
            auth_home.mkdir()
            (auth_home / "auth.json").write_text(
                json.dumps({"OPENAI_API_KEY": "offline-failure-auth-value-123456"})
            )
            inventory, _ = credential_guard.inspect_source("codex", auth_home)
            structure = inventory["redacted_credential_structure_sha256"]
            preflight = {
                "condition_id": slot["condition_id"],
                "harness_commit": "test-harness-commit",
                "redacted_credential_structure_sha256": structure,
            }
            preflight["sha256"] = probe.sha256_bytes(probe.canonical_json(preflight))
            snapshot = {slot["condition_id"]: preflight}

            class FailedAfterStart:
                pid = 999999
                returncode = 7

                def __init__(self, command):
                    staged_run = (
                        Path(command[3])
                        / Path(probe.TASK_REL).name
                        / condition["output_label"]
                        / "run-1"
                    )
                    seed_run(staged_run, condition)
                    for name in ("credential_scan.raw.json", "credential_scan.json"):
                        (staged_run / name).unlink()
                    receipt = json.loads(
                        (staged_run / "credential_scan.runtime.json").read_text()
                    )
                    receipt["source_redacted_credential_structure_sha256"] = structure
                    (staged_run / "credential_scan.runtime.json").write_text(
                        json.dumps(receipt)
                    )

                def wait(self, timeout=None):
                    return self.returncode

                def poll(self):
                    return self.returncode

            with mock.patch.dict(
                os.environ,
                {
                    "ARENA_CODEX_HOME": str(auth_home),
                    "ARENA_QUARANTINE_DIR": quarantine,
                },
            ), mock.patch.object(
                probe, "preflight_manifest", return_value=snapshot
            ), mock.patch.object(
                probe.subprocess,
                "Popen",
                side_effect=lambda command, **_kwargs: FailedAfterStart(command),
            ), mock.patch.object(
                probe, "terminate_process_group"
            ), mock.patch.object(
                probe,
                "_frozen_credential_structure_sha256",
                return_value=structure,
            ):
                with self.assertRaisesRegex(RuntimeError, "ledger row was preserved"):
                    probe.run_slots(
                        path,
                        approval=None,
                        requested_slots={slot["slot_id"]},
                        dry_run=False,
                    )
                ledger, malformed = probe.iter_jsonl(
                    probe.ROOT / manifest["bout_dir"] / "EXECUTION.jsonl"
                )
                self.assertEqual(malformed, [])
                self.assertEqual(len(ledger), 1)
                self.assertRegex(
                    ledger[0]["artifact_manifest_sha256"], r"^[0-9a-f]{64}$"
                )
                run_dir = probe.ROOT / ledger[0]["run_dir"]
                artifact_manifest = json.loads(
                    (run_dir / "artifact_manifest.json").read_text()
                )
                self.assertEqual(artifact_manifest["record_kind"], "failed_attempt")
                self.assertEqual(
                    probe.validate_prior_attempt_provenance(manifest, ledger), []
                )
                (run_dir / "stderr.log").write_text("tampered")
                self.assertTrue(
                    probe.validate_prior_attempt_provenance(manifest, ledger)
                )

    def test_staged_recovery_uses_emergency_quarantine_and_anchors_receipt(self):
        class FailedProcess:
            pid = 999999
            returncode = 7

            def wait(self, timeout=None):
                return self.returncode

            def poll(self):
                return self.returncode

        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw, tempfile.TemporaryDirectory(
            prefix="arena-quarantine-test-"
        ) as quarantine:
            temp = Path(raw)
            path, manifest = make_manifest(temp / "manifest", phase="smoke")
            manifest["bout_dir"] = str((temp / "bout").relative_to(probe.ROOT))
            manifest["freeze_id"] = probe.compute_freeze_id(manifest)
            path.write_text(json.dumps(manifest))
            slot = manifest["schedule"][0]
            preflight = {
                "condition_id": slot["condition_id"],
                "harness_commit": "test-harness-commit",
            }
            preflight["sha256"] = probe.sha256_bytes(probe.canonical_json(preflight))
            snapshot = {slot["condition_id"]: preflight}
            original_validate = probe._validate_quarantine_handle

            def reject_primary(handle, destination_name):
                if not handle.get("ephemeral"):
                    raise ValueError("synthetic primary quarantine detachment")
                return original_validate(handle, destination_name)

            with mock.patch.dict(
                os.environ, {"ARENA_QUARANTINE_DIR": quarantine}
            ), mock.patch.object(
                probe, "preflight_manifest", return_value=snapshot
            ), mock.patch.object(
                probe.subprocess, "Popen", return_value=FailedProcess()
            ), mock.patch.object(
                probe,
                "recover_and_remove_staged_driver",
                side_effect=RuntimeError("synthetic staged recovery failure"),
            ), mock.patch.object(
                probe, "_validate_quarantine_handle", side_effect=reject_primary
            ):
                with self.assertRaisesRegex(RuntimeError, "ledger row was preserved"):
                    probe.run_slots(
                        path,
                        approval=None,
                        requested_slots={slot["slot_id"]},
                        dry_run=False,
                    )
            ledger, malformed = probe.iter_jsonl(
                probe.ROOT / manifest["bout_dir"] / "EXECUTION.jsonl"
            )
            self.assertEqual(malformed, [])
            self.assertEqual(len(ledger), 1)
            self.assertTrue(ledger[0]["process_group_cleaned"])
            self.assertFalse(ledger[0]["staged_attempt_retained"])
            self.assertRegex(
                ledger[0]["stage_quarantine_receipt_sha256"], r"^[0-9a-f]{64}$"
            )
            stage_receipt = json.loads(
                (probe.ROOT / ledger[0]["stage_quarantine_receipt"]).read_text()
            )
            self.assertEqual(stage_receipt["destination_kind"], "stage")
            self.assertTrue(stage_receipt["fallback_destination"])
            quarantined_stage = Path(stage_receipt["quarantine_destination"])
            self.assertTrue(quarantined_stage.is_dir())
            self.assertEqual(probe.validate_prior_attempt_provenance(manifest, ledger), [])
            (quarantined_stage / "post-receipt-tamper").write_text("changed")
            self.assertTrue(
                any(
                    "quarantine destination entry count changed" in error
                    for error in probe.validate_prior_attempt_provenance(manifest, ledger)
                )
            )
            shutil.rmtree(quarantined_stage.parent.parent)

    def test_retained_external_stage_blocks_resume_when_both_quarantines_fail(self):
        class FailedProcess:
            pid = 999999
            returncode = 7

            def wait(self, timeout=None):
                return self.returncode

            def poll(self):
                return self.returncode

        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw, tempfile.TemporaryDirectory(
            prefix="arena-quarantine-test-"
        ) as quarantine, tempfile.TemporaryDirectory(
            prefix="arena-retained-stage-test-"
        ) as external_stage:
            temp = Path(raw)
            path, manifest = make_manifest(temp / "manifest", phase="smoke")
            manifest["bout_dir"] = str((temp / "bout").relative_to(probe.ROOT))
            manifest["freeze_id"] = probe.compute_freeze_id(manifest)
            path.write_text(json.dumps(manifest))
            slot = manifest["schedule"][0]
            preflight = {
                "condition_id": slot["condition_id"],
                "harness_commit": "test-harness-commit",
            }
            preflight["sha256"] = probe.sha256_bytes(probe.canonical_json(preflight))
            snapshot = {slot["condition_id"]: preflight}
            attempt_root = Path(external_stage) / "attempt"
            attempt_root.mkdir()
            staged_run = attempt_root / "unrecovered-run"
            with mock.patch.dict(
                os.environ, {"ARENA_QUARANTINE_DIR": quarantine}
            ), mock.patch.object(
                probe, "preflight_manifest", return_value=snapshot
            ), mock.patch.object(
                probe,
                "prepare_staged_driver",
                return_value=(attempt_root, staged_run, ["synthetic-driver"], {}),
            ), mock.patch.object(
                probe.subprocess, "Popen", return_value=FailedProcess()
            ), mock.patch.object(
                probe,
                "recover_and_remove_staged_driver",
                side_effect=RuntimeError("synthetic staged recovery failure"),
            ), mock.patch.object(
                probe,
                "_validate_quarantine_handle",
                side_effect=ValueError("synthetic quarantine failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "ledger row was preserved"):
                    probe.run_slots(
                        path,
                        approval=None,
                        requested_slots={slot["slot_id"]},
                        dry_run=False,
                    )
            ledger, malformed = probe.iter_jsonl(
                probe.ROOT / manifest["bout_dir"] / "EXECUTION.jsonl"
            )
            self.assertEqual(malformed, [])
            self.assertTrue(ledger[0]["process_group_cleaned"])
            self.assertTrue(ledger[0]["staged_attempt_retained"])
            self.assertTrue(attempt_root.is_dir())
            self.assertTrue(
                any(
                    "retained staged attempt" in error
                    or "staged-attempt evidence" in error
                    for error in probe.validate_prior_attempt_provenance(manifest, ledger)
                )
            )
            with self.assertRaisesRegex(ValueError, "staged-attempt"):
                probe.run_slots(
                    path,
                    approval=None,
                    requested_slots=None,
                    dry_run=True,
                )
            attempt_root.rmdir()

    def test_sigterm_during_active_driver_restores_handlers_and_preserves_ledger(self):
        class SignaledProcess:
            pid = 999999
            returncode = -signal.SIGTERM

            def wait(self, timeout=None):
                if timeout is None:
                    os.kill(os.getpid(), signal.SIGTERM)
                return self.returncode

            def poll(self):
                return self.returncode

        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw, tempfile.TemporaryDirectory(
            prefix="arena-quarantine-test-"
        ) as quarantine:
            temp = Path(raw)
            path, manifest = make_manifest(temp / "manifest", phase="smoke")
            manifest["bout_dir"] = str((temp / "bout").relative_to(probe.ROOT))
            manifest["freeze_id"] = probe.compute_freeze_id(manifest)
            path.write_text(json.dumps(manifest))
            slot = manifest["schedule"][0]
            preflight = {
                "condition_id": slot["condition_id"],
                "harness_commit": "test-harness-commit",
            }
            preflight["sha256"] = probe.sha256_bytes(probe.canonical_json(preflight))
            snapshot = {slot["condition_id"]: preflight}
            prior_handler = signal.getsignal(signal.SIGTERM)
            with mock.patch.dict(
                os.environ, {"ARENA_QUARANTINE_DIR": quarantine}
            ), mock.patch.object(
                probe, "preflight_manifest", return_value=snapshot
            ), mock.patch.object(
                probe.subprocess, "Popen", return_value=SignaledProcess()
            ), mock.patch.object(probe, "terminate_process_group"):
                with self.assertRaises(probe.OperatorTermination):
                    probe.run_slots(path, approval=None, requested_slots={slot["slot_id"]}, dry_run=False)
            self.assertEqual(signal.getsignal(signal.SIGTERM), prior_handler)
            ledger, malformed = probe.iter_jsonl(probe.ROOT / manifest["bout_dir"] / "EXECUTION.jsonl")
            self.assertEqual(malformed, [])
            self.assertEqual(len(ledger), 1)
            self.assertEqual(ledger[0]["driver_exit"], -signal.SIGTERM)
            self.assertTrue(ledger[0]["process_group_cleaned"])
            self.assertFalse(ledger[0]["staged_attempt_retained"])
            self.assertRegex(ledger[0]["failure_receipt_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue((probe.ROOT / ledger[0]["failure_receipt"]).is_file())

    def test_target_chosen_empty_output_remains_confirmatory_eligible_for_every_driver(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", repeats=10)
            conditions = probe.condition_map(manifest)
            for index, slot in enumerate(manifest["schedule"][:3]):
                run_dir = temp / f"run-{index}"
                seed_run(run_dir, conditions[slot["condition_id"]], output="")
                self.assertTrue(
                    probe.raw_attempt_has_attributable_activity(
                        conditions[slot["condition_id"]]["driver"], run_dir
                    )
                )
                record = probe.observe_run(manifest, slot, run_dir)
                self.assertEqual(record["validity"]["technical_issues"], [], slot["condition_id"])
                self.assertTrue(record["validity"]["confirmatory_analysis_eligible"])
                self.assertFalse(record["output"]["present"])

    def test_target_timeout_with_unavailable_usage_remains_behaviorally_eligible(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", repeats=10)
            conditions = probe.condition_map(manifest)
            selected = [
                slot
                for slot in manifest["schedule"]
                if conditions[slot["condition_id"]]["driver"] in {"claude", "kimi"}
            ][:2]
            for index, slot in enumerate(selected):
                condition = conditions[slot["condition_id"]]
                run_dir = temp / f"timeout-{condition['driver']}"
                seed_run(run_dir, condition)
                metrics = json.loads((run_dir / "metrics.json").read_text())
                metrics.update(
                    {
                        "agent_exit": 124,
                        "input_tokens": None,
                        "output_tokens": None,
                        "total_cost_usd": None,
                    }
                )
                (run_dir / "metrics.json").write_text(json.dumps(metrics))
                (run_dir / "agent_exit").write_text("124\n")
                if condition["driver"] == "claude":
                    events, _ = probe.iter_jsonl(run_dir / "transcript.jsonl")
                    jsonl(
                        run_dir / "transcript.jsonl",
                        [
                            {key: value for key, value in event.items() if key != "_line"}
                            for event in events
                            if event.get("type") != "result"
                        ],
                    )
                    (run_dir / "result.json").write_text("")
                record = probe.observe_run(manifest, slot, run_dir)
                self.assertEqual(record["validity"]["technical_issues"], [], condition["driver"])
                self.assertTrue(record["validity"]["confirmatory_analysis_eligible"])
                self.assertTrue(record["completion"]["truncation_observed"])
                self.assertEqual(
                    set(record["completion"]["descriptive_metrics_unavailable"]),
                    {"input_tokens", "output_tokens", "total_cost_usd"},
                )
                self.assertEqual(probe.eligible_exclusion_reasons(record), [])

    def test_metrics_helpers_emit_explicit_null_usage_without_terminal_records(self):
        scripts = (
            ("metrics.py", ["claude-opus-5"], [{"type": "assistant", "message": {"model": "claude-opus-5", "content": []}}]),
            ("metrics_codex.py", ["gpt-5.6-sol-codex"], [{"type": "thread.started", "thread_id": "t"}]),
            ("metrics_kimi.py", ["kimi-k3-kimicode", "kimi-k3"], [{"role": "assistant", "content": ""}]),
        )
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            base = Path(raw)
            for index, (script, arguments, events) in enumerate(scripts):
                run_dir = base / f"metrics-{index}"
                run_dir.mkdir()
                (run_dir / "wall_seconds").write_text("1.25\n")
                (run_dir / "agent_exit").write_text("124\n")
                jsonl(run_dir / "transcript.jsonl", events)
                if script == "metrics_kimi.py":
                    jsonl(run_dir / "wire.jsonl", [])
                completed = subprocess.run(
                    [os.sys.executable, str(probe.ROOT / "bin" / script), str(run_dir), *arguments],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                metrics = json.loads(completed.stdout)
                self.assertIsNone(metrics["input_tokens"], script)
                self.assertIsNone(metrics["output_tokens"], script)
                self.assertIsNone(metrics["total_cost_usd"], script)

    def test_model_identity_requires_nonempty_and_all_observations_matching(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", phase="smoke")
            conditions = probe.condition_map(manifest)
            for slot in manifest["schedule"]:
                driver = conditions[slot["condition_id"]]["driver"]
                run_dir = temp / driver
                seed_run(run_dir, conditions[slot["condition_id"]])
                if driver == "claude":
                    events, _ = probe.iter_jsonl(run_dir / "transcript.jsonl")
                    events.insert(
                        2,
                        {
                            "type": "assistant",
                            "message": {"model": "unexpected-model", "content": [{"type": "text", "text": ""}]},
                            "_line": 99,
                        },
                    )
                    jsonl(run_dir / "transcript.jsonl", [{k: v for k, v in event.items() if k != "_line"} for event in events])
                elif driver == "kimi":
                    events, _ = probe.iter_jsonl(run_dir / "wire.jsonl")
                    for event in events:
                        if event.get("type") == "llm.response":
                            event["model"] = "unexpected-model"
                    jsonl(
                        run_dir / "wire.jsonl",
                        [{k: v for k, v in event.items() if k != "_line"} for event in events],
                    )
                else:
                    events, _ = probe.iter_jsonl(run_dir / "transcript.jsonl")
                    for event in events:
                        item = event.get("item")
                        if isinstance(item, dict) and item.get("type") == "agent_message":
                            item["model"] = "unexpected-model"
                    jsonl(
                        run_dir / "transcript.jsonl",
                        [{k: v for k, v in event.items() if k != "_line"} for event in events],
                    )
                record = probe.observe_run(manifest, slot, run_dir)
                self.assertTrue(
                    any("model mismatch" in issue for issue in record["validity"]["technical_issues"]),
                    (driver, record["validity"]["technical_issues"]),
                )

    def test_response_only_model_alias_and_provider_drift_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", phase="smoke")
            conditions = probe.condition_map(manifest)
            codex_slot = next(
                slot for slot in manifest["schedule"] if slot["condition_id"].startswith("codex--")
            )
            codex_run = temp / "codex-response-model"
            seed_run(codex_run, conditions[codex_slot["condition_id"]])
            session, _ = probe.iter_jsonl(codex_run / "session.jsonl")
            session.append(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "model": "unexpected-session-only-model",
                        "content": [],
                    },
                }
            )
            jsonl(
                codex_run / "session.jsonl",
                [{key: value for key, value in event.items() if key != "_line"} for event in session],
            )
            codex_record = probe.observe_run(manifest, codex_slot, codex_run)
            self.assertTrue(
                any("model mismatch" in issue for issue in codex_record["validity"]["technical_issues"])
            )

            kimi_slot = next(
                slot
                for slot in manifest["schedule"]
                if slot["condition_id"].startswith("kimi-code--")
            )
            for field, unexpected, expected_issue in (
                ("modelAlias", "arena/unexpected", "model alias mismatch"),
                ("provider", "unexpected-provider", "provider mismatch"),
            ):
                run_dir = temp / f"kimi-{field}"
                seed_run(run_dir, conditions[kimi_slot["condition_id"]])
                wire, _ = probe.iter_jsonl(run_dir / "wire.jsonl")
                for event in wire:
                    if event.get("type") == "llm.response":
                        event[field] = unexpected
                jsonl(
                    run_dir / "wire.jsonl",
                    [{key: value for key, value in event.items() if key != "_line"} for event in wire],
                )
                record = probe.observe_run(manifest, kimi_slot, run_dir)
                self.assertTrue(
                    any(expected_issue in issue for issue in record["validity"]["technical_issues"]),
                    (field, record["validity"]["technical_issues"]),
                )

    def test_transport_exclusion_requires_explicit_pre_request_evidence(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", repeats=10)
            slot = next(slot for slot in manifest["schedule"] if slot["condition_id"].startswith("codex--"))
            run_dir = temp / "run"
            seed_run(run_dir, probe.condition_map(manifest)[slot["condition_id"]], output="")
            metrics = json.loads((run_dir / "metrics.json").read_text())
            metrics["agent_exit"] = 1
            (run_dir / "metrics.json").write_text(json.dumps(metrics))
            record = probe.observe_run(manifest, slot, run_dir)
            self.assertTrue(record["validity"]["confirmatory_analysis_eligible"])
            self.assertEqual(record["validity"]["state"], "review_required")
            self.assertNotIn(
                "transport_or_service_failure_before_request_acceptance",
                probe.eligible_exclusion_reasons(record),
            )
            self.assertTrue(record["configuration"]["observed_identity"]["models"])

            record["completion"]["agent_exit"] = 143
            self.assertNotIn(
                "external_termination_before_attributable_target_completion",
                probe.eligible_exclusion_reasons(record),
            )
            record["completion"]["target_response_activity_observed"] = False
            self.assertIn(
                "external_termination_before_attributable_target_completion",
                probe.eligible_exclusion_reasons(record),
            )

            explicit = probe.completion_observation(
                "codex",
                [
                    {
                        "type": "error",
                        "request_accepted": False,
                        "failure_phase": "before_request",
                    }
                ],
                {"agent_exit": 1},
                "",
            )
            record["completion"] = explicit
            self.assertFalse(explicit["request_acceptance_observed"])
            self.assertTrue(explicit["pre_request_transport_failure_observed"])
            self.assertIn(
                "transport_or_service_failure_before_request_acceptance",
                probe.eligible_exclusion_reasons(record),
            )

            post_request = probe.completion_observation(
                "codex",
                [
                    {
                        "type": "turn.failed",
                        "request_accepted": True,
                        "failure_phase": "after_request",
                    }
                ],
                {"agent_exit": 1},
                "",
            )
            record["completion"] = post_request
            self.assertTrue(post_request["request_acceptance_observed"])
            self.assertFalse(post_request["pre_request_transport_failure_observed"])
            self.assertNotIn(
                "transport_or_service_failure_before_request_acceptance",
                probe.eligible_exclusion_reasons(record),
            )

    def test_model_identity_matching_is_exact_not_substring_based(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", phase="smoke")
            slot = next(slot for slot in manifest["schedule"] if slot["condition_id"].startswith("claude-code--"))
            condition = probe.condition_map(manifest)[slot["condition_id"]]
            run_dir = temp / "run"
            seed_run(run_dir, condition)
            events, _ = probe.iter_jsonl(run_dir / "transcript.jsonl")
            for event in events:
                if event.get("model"):
                    event["model"] = f"unexpected-{condition['requested_model']}-proxy"
                message = event.get("message")
                if isinstance(message, dict) and message.get("model"):
                    message["model"] = f"unexpected-{condition['requested_model']}-proxy"
            jsonl(
                run_dir / "transcript.jsonl",
                [{key: value for key, value in event.items() if key != "_line"} for event in events],
            )
            record = probe.observe_run(manifest, slot, run_dir)
            self.assertTrue(any("model mismatch" in issue for issue in record["validity"]["technical_issues"]))

    def test_smoke_outputs_cannot_be_blinded(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            path, _ = make_manifest(temp, phase="smoke")
            with self.assertRaisesRegex(ValueError, "Smoke|smoke"):
                probe.make_blind_packets(path, temp / "packets", "key")

    def test_kimi_policy_signature_ignores_only_dynamic_time_and_workspace(self):
        def context(timestamp, workspace):
            return {
                "config_updates": [
                    {
                        "type": "config.update",
                        "time": timestamp,
                        "systemPrompt": (
                            f"Policy text. The current date and time in ISO format is `{timestamp}`. "
                            f"The current working directory is `{workspace}`."
                        ),
                    }
                ],
                "active_tools": [{"names": ["Read", "Agent"]}],
                "tool_snapshots": [{"hash": "h", "tools": []}],
                "requests": [{"model": "kimi-k3", "thinkingEffort": "max"}],
            }

        first = probe.instruction_policy_signature("kimi", context("2026-01-01T00:00:00Z", "/tmp/arena-ws.one"))
        second = probe.instruction_policy_signature("kimi", context("2026-01-02T00:00:00Z", "/tmp/arena-ws.two"))
        self.assertEqual(first["sha256"], second["sha256"])

    def test_codex_policy_signature_normalizes_scratch_paths_but_not_policy(self):
        def context(workspace, auth_home, policy="keep this rule"):
            return {
                "base_instructions": f"{policy}; workspace={workspace}",
                "pre_response_messages": [
                    {"role": "developer", "content": f"auth={auth_home}; cwd={workspace}"}
                ],
                "turn_contexts": [
                    {
                        "approval_policy": "never",
                        "collaboration_mode": {"mode": "default"},
                        "model": "gpt-5.6-sol",
                        "multi_agent_mode": "default",
                        "permission_profile": {"type": "disabled"},
                        "personality": "codex",
                        "sandbox_policy": "danger-full-access",
                    }
                ],
            }

        first = probe.instruction_policy_signature(
            "codex",
            context("/tmp/arena-ws.ABC123", "/tmp/arena-codex-home.ZYX987"),
        )
        second = probe.instruction_policy_signature(
            "codex",
            context("/tmp/arena-ws.Different9", "/tmp/arena-codex-home.Other8"),
        )
        changed = probe.instruction_policy_signature(
            "codex",
            context("/tmp/arena-ws.Different9", "/tmp/arena-codex-home.Other8", "changed rule"),
        )
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertNotEqual(first["sha256"], changed["sha256"])

        staged = probe.instruction_policy_signature(
            "codex",
            context(
                "/tmp/arena-plan-attempt.Stage123/runtime/arena-ws.ABC123",
                "/tmp/arena-plan-attempt.Stage123/runtime/arena-codex-home.ZYX987",
            ),
        )
        self.assertEqual(first["sha256"], staged["sha256"])

    def test_driver_environment_is_minimal_and_driver_specific(self):
        source = {
            "HOME": "/home/operator",
            "PATH": "/bin",
            "TMPDIR": "relative-or-hostile",
            "LC_ALL": "C",
            "SSH_AUTH_SOCK": "/tmp/agent.sock",
            "OPENAI_API_KEY": "openai-secret",
            "KIMI_API_KEY": "kimi-secret",
            "ANTHROPIC_API_KEY": "anthropic-secret",
            "ARENA_CLAUDE_HOME": "/outside/claude",
            "ARENA_CODEX_HOME": "/outside/codex",
            "ARENA_KIMI_HOME": "/outside/kimi",
        }
        claude = probe.driver_environment("claude", source)
        codex = probe.driver_environment("codex", source)
        kimi = probe.driver_environment("kimi", source)
        self.assertEqual(claude["ANTHROPIC_API_KEY"], "anthropic-secret")
        self.assertNotIn("OPENAI_API_KEY", claude)
        self.assertNotIn("SSH_AUTH_SOCK", claude)
        self.assertNotIn("ARENA_CODEX_HOME", claude)
        self.assertNotIn("ARENA_KIMI_HOME", claude)
        self.assertNotIn("OPENAI_API_KEY", codex)
        self.assertNotIn("ARENA_CLAUDE_HOME", codex)
        self.assertNotIn("ARENA_KIMI_HOME", codex)
        self.assertNotIn("KIMI_API_KEY", kimi)
        self.assertEqual(kimi["ARENA_KIMI_HOME"], "/outside/kimi")
        self.assertNotIn("ARENA_CLAUDE_HOME", kimi)
        self.assertNotIn("ARENA_CODEX_HOME", kimi)
        for environment in (claude, codex, kimi):
            self.assertEqual(environment["TMPDIR"], "/tmp")

        with mock.patch.object(probe, "SAFE_TEMP_ROOT", probe.ROOT):
            with self.assertRaisesRegex(ValueError, "outside"):
                probe.driver_environment("codex", source)

    def test_live_driver_stage_contains_no_hidden_rubric_or_analysis_files(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            _, manifest = make_manifest(Path(raw) / "manifest", phase="smoke")
            source = {"HOME": str(Path.home()), "PATH": os.environ["PATH"]}
            for slot in manifest["schedule"]:
                driver = probe.condition_map(manifest)[slot["condition_id"]]["driver"]
                env = probe.driver_environment(driver, source)
                attempt_root, staged_run, command, staged_env = probe.prepare_staged_driver(
                    manifest, slot, env
                )
                try:
                    staged_names = {
                        str(path.relative_to(attempt_root)) for path in attempt_root.rglob("*")
                    }
                    self.assertFalse(any("SCORING" in name for name in staged_names))
                    self.assertFalse(any("analysis" in name.lower() for name in staged_names))
                    self.assertEqual(
                        (attempt_root / "harness" / probe.PROMPT_REL).read_bytes(),
                        (probe.ROOT / probe.PROMPT_REL).read_bytes(),
                    )
                    self.assertTrue(all(str(attempt_root) in argument for argument in (command[0], command[1], command[3])))
                    self.assertEqual(Path(staged_env["ARENA_PLAN_TMPDIR"]), attempt_root / "runtime")
                finally:
                    probe.recover_and_remove_staged_driver(attempt_root, staged_run, probe.ROOT / raw / "unused")


class CredentialGuardTests(unittest.TestCase):
    def test_exact_source_allowlist_and_actual_secret_scanning_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            home = temp / "auth-home"
            home.mkdir()
            secret = "test-secret-value-123456789"
            (home / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": secret, "auth_mode": "api_key"}))
            inventory, values = credential_guard.inspect_source("codex", home)
            self.assertEqual(inventory["secret_field_count"], 1)
            self.assertEqual(values, [secret.encode()])
            scan_root = temp / "artifacts"
            scan_root.mkdir()
            (scan_root / "safe.txt").write_text("safe")
            receipt = credential_guard.scan_artifacts("codex", home, [scan_root])
            self.assertTrue(receipt["pass"])
            self.assertNotIn(secret, json.dumps(receipt))
            (scan_root / "leak.txt").write_text(secret)
            receipt = credential_guard.scan_artifacts("codex", home, [scan_root])
            self.assertFalse(receipt["pass"])
            self.assertEqual(receipt["leak_match_count"], 1)
            (home / "config.toml").write_text("treatment = 'changed'")
            with self.assertRaisesRegex(credential_guard.CredentialGuardError, "allowlist"):
                credential_guard.inspect_source("codex", home)

    def test_zero_coverage_and_unsafe_entries_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            empty_home = temp / "empty-home"
            empty_home.mkdir()
            (empty_home / "auth.json").write_text(json.dumps({"auth_mode": "api_key"}))
            with self.assertRaisesRegex(credential_guard.CredentialGuardError, "zero recognized"):
                credential_guard.inspect_source("codex", empty_home)
            home = temp / "home"
            home.mkdir()
            (home / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": "test-secret-value"}))
            artifacts = temp / "artifacts"
            artifacts.mkdir()
            (artifacts / "escape").symlink_to(home / "auth.json")
            receipt = credential_guard.scan_artifacts("codex", home, [artifacts])
            self.assertFalse(receipt["pass"])
            self.assertEqual(receipt["escaping_symlink_count"], 1)

    def test_runtime_rotated_secret_and_receipt_validation_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            final_home = temp / "final-auth"
            final_home.mkdir()
            rotated = "rotated-runtime-secret-value-123456"
            (final_home / "auth.json").write_text(json.dumps({"accessToken": rotated}))
            artifacts = temp / "artifacts"
            artifacts.mkdir()
            (artifacts / "transcript.jsonl").write_text(rotated)
            receipt = credential_guard.scan_artifacts("codex", final_home, [artifacts])
            self.assertFalse(receipt["pass"])
            self.assertEqual(receipt["leak_match_count"], 1)
            receipt_path = temp / "credential_scan.runtime.json"
            receipt_path.write_text(json.dumps(receipt))
            issues = probe.credential_receipt_issues(receipt_path, "codex")
            self.assertTrue(any("unsafe content" in issue for issue in issues))
            self.assertTrue(any("did not pass" in issue for issue in issues))

    def test_runtime_credential_schema_drift_is_rejected_even_for_unrecognized_key(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            baseline_home = temp / "baseline"
            baseline_home.mkdir()
            (baseline_home / "auth.json").write_text(
                json.dumps({"accessToken": "baseline-secret-value-123456"})
            )
            artifacts = temp / "artifacts"
            artifacts.mkdir()
            baseline = credential_guard.scan_artifacts("codex", baseline_home, [artifacts])
            self.assertTrue(baseline["pass"])

            runtime_home = temp / "runtime"
            runtime_home.mkdir()
            unclassified_secret = "runtime-opaque-state-value-123456"
            (runtime_home / "auth.json").write_text(
                json.dumps(
                    {
                        "accessToken": "baseline-secret-value-123456",
                        "opaqueState": unclassified_secret,
                    }
                )
            )
            (artifacts / "transcript.jsonl").write_text(unclassified_secret)
            runtime = credential_guard.scan_artifacts("codex", runtime_home, [artifacts])
            self.assertTrue(runtime["pass"], "the structural gate must catch keys outside heuristics")
            receipt_path = temp / "credential_scan.runtime.json"
            receipt_path.write_text(json.dumps(runtime))
            issues = probe.credential_receipt_issues(
                receipt_path,
                "codex",
                expected_source_structure_sha256=baseline[
                    "source_redacted_credential_structure_sha256"
                ],
            )
            self.assertTrue(any("schema drift" in issue for issue in issues))

            (runtime_home / "auth.json").write_text(
                json.dumps(
                    {
                        "accessToken": "baseline-secret-value-123456",
                        "sessionCookie": unclassified_secret,
                    }
                )
            )
            cookie_receipt = credential_guard.scan_artifacts("codex", runtime_home, [artifacts])
            self.assertFalse(cookie_receipt["pass"])
            self.assertGreater(cookie_receipt["leak_match_count"], 0)

    def test_credential_guard_scans_artifact_path_names(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            home = temp / "home"
            home.mkdir()
            secret = "test-secret-value-in-path-123456"
            (home / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": secret}))
            artifacts = temp / "artifacts"
            artifacts.mkdir()
            (artifacts / secret).write_text("content contains no credential")
            receipt = credential_guard.scan_artifacts("codex", home, [artifacts])
            self.assertFalse(receipt["pass"])
            self.assertEqual(receipt["leak_match_count"], 1)
            self.assertGreater(receipt["scanned_path_bytes"], 0)

    def test_security_quarantine_uses_prevalidated_atomic_rename(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw, tempfile.TemporaryDirectory(
            prefix="arena-quarantine-test-"
        ) as quarantine:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", phase="smoke")
            manifest["bout_dir"] = str((temp / "bout").relative_to(probe.ROOT))
            manifest["freeze_id"] = probe.compute_freeze_id(manifest)
            slot = manifest["schedule"][0]
            run_dir = temp / "unsafe-run"
            run_dir.mkdir()
            (run_dir / "unsafe.txt").write_text("synthetic unsafe artifact")
            with mock.patch.dict(os.environ, {"ARENA_QUARANTINE_DIR": quarantine}):
                expected = probe.quarantine_destination(manifest, slot)
                result = probe.quarantine_run(manifest, slot, run_dir)
            self.assertTrue(result["succeeded"])
            self.assertFalse(run_dir.exists())
            self.assertEqual((expected / "unsafe.txt").read_text(), "synthetic unsafe artifact")
            receipt = probe.ROOT / result["receipt"]
            self.assertTrue(receipt.is_file())
            self.assertEqual(result["receipt_sha256"], probe.sha256_path(receipt))

    def test_quarantine_root_swap_falls_back_to_preopened_emergency_destination(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw, tempfile.TemporaryDirectory(
            prefix="arena-quarantine-container-"
        ) as container:
            temp = Path(raw)
            primary_path = Path(container) / "primary"
            primary_path.mkdir(mode=0o700)
            detached_path = Path(container) / "detached-primary"
            _, manifest = make_manifest(temp / "manifest", phase="smoke")
            manifest["bout_dir"] = str((temp / "bout").relative_to(probe.ROOT))
            manifest["freeze_id"] = probe.compute_freeze_id(manifest)
            slot = manifest["schedule"][0]
            source = temp / "unsafe-run"
            source.mkdir()
            (source / "unsafe.txt").write_text("synthetic unsafe artifact")
            with mock.patch.dict(
                os.environ, {"ARENA_QUARANTINE_DIR": str(primary_path)}
            ):
                primary = probe.prepare_quarantine(manifest, slot)
                fallback = probe.prepare_emergency_quarantine(manifest, slot)
                try:
                    primary_path.rename(detached_path)
                    primary_path.mkdir(mode=0o700)
                    result = probe.quarantine_with_fallback(
                        manifest,
                        slot,
                        source,
                        primary=primary,
                        fallback=fallback,
                    )
                    self.assertEqual(
                        result["primary_destination_error_type"], "ValueError"
                    )
                    receipt = json.loads((probe.ROOT / result["receipt"]).read_text())
                    self.assertTrue(receipt["fallback_destination"])
                    destination = Path(receipt["quarantine_destination"])
                    self.assertEqual(
                        (destination / "unsafe.txt").read_text(),
                        "synthetic unsafe artifact",
                    )
                    probe.close_quarantine(fallback)
                    shutil.rmtree(destination.parent.parent)
                finally:
                    probe.dispose_quarantine(fallback)
                    probe.close_quarantine(primary)

    def test_atomic_quarantine_destination_race_never_replaces_competitor(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw, tempfile.TemporaryDirectory(
            prefix="arena-quarantine-test-"
        ) as quarantine:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", phase="smoke")
            manifest["bout_dir"] = str((temp / "bout").relative_to(probe.ROOT))
            manifest["freeze_id"] = probe.compute_freeze_id(manifest)
            slot = manifest["schedule"][0]
            source = temp / "unsafe-run"
            source.mkdir()
            (source / "unsafe.txt").write_text("synthetic unsafe artifact")
            with mock.patch.dict(
                os.environ, {"ARENA_QUARANTINE_DIR": quarantine}
            ):
                primary = probe.prepare_quarantine(manifest, slot)
                fallback = probe.prepare_emergency_quarantine(manifest, slot)
                original_rename = probe._rename_noreplace
                raced = False

                def race_once(source_path, destination_fd, destination_name):
                    nonlocal raced
                    if not raced:
                        raced = True
                        os.mkdir(destination_name, dir_fd=destination_fd)
                        competitor_fd = os.open(
                            destination_name,
                            probe._directory_open_flags(),
                            dir_fd=destination_fd,
                        )
                        try:
                            marker_fd = os.open(
                                "competitor.txt",
                                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                                0o600,
                                dir_fd=competitor_fd,
                            )
                            try:
                                os.write(marker_fd, b"competitor")
                            finally:
                                os.close(marker_fd)
                        finally:
                            os.close(competitor_fd)
                    return original_rename(source_path, destination_fd, destination_name)

                try:
                    with mock.patch.object(
                        probe, "_rename_noreplace", side_effect=race_once
                    ):
                        result = probe.quarantine_with_fallback(
                            manifest,
                            slot,
                            source,
                            primary=primary,
                            fallback=fallback,
                        )
                    competitor = (
                        primary["base_path"]
                        / primary["experiment_id"]
                        / primary["slot_id"]
                        / "competitor.txt"
                    )
                    self.assertEqual(competitor.read_text(), "competitor")
                    receipt = json.loads((probe.ROOT / result["receipt"]).read_text())
                    self.assertTrue(receipt["fallback_destination"])
                    destination = Path(receipt["quarantine_destination"])
                    self.assertEqual(
                        (destination / "unsafe.txt").read_text(),
                        "synthetic unsafe artifact",
                    )
                    probe.close_quarantine(fallback)
                    shutil.rmtree(destination.parent.parent)
                finally:
                    probe.dispose_quarantine(fallback)
                    probe.close_quarantine(primary)

    def test_quarantine_rejects_symlinked_experiment_directory(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw, tempfile.TemporaryDirectory(
            prefix="arena-quarantine-test-"
        ) as quarantine, tempfile.TemporaryDirectory(prefix="arena-quarantine-redirect-") as redirect:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", phase="smoke")
            experiment_link = Path(quarantine) / manifest["experiment_id"]
            experiment_link.symlink_to(Path(redirect), target_is_directory=True)
            with mock.patch.dict(os.environ, {"ARENA_QUARANTINE_DIR": quarantine}):
                with self.assertRaisesRegex(ValueError, "experiment directory must be a real directory"):
                    probe.quarantine_destination(manifest, manifest["schedule"][0])

    def test_quarantine_rejects_symlink_ancestor_before_creating_through_it(self):
        with tempfile.TemporaryDirectory(
            prefix="arena-quarantine-container-"
        ) as container, tempfile.TemporaryDirectory(
            prefix="arena-quarantine-redirect-"
        ) as redirect, tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", phase="smoke")
            link = Path(container) / "redirect"
            link.symlink_to(redirect, target_is_directory=True)
            configured = link / "must-not-be-created"
            with mock.patch.dict(
                os.environ, {"ARENA_QUARANTINE_DIR": str(configured)}
            ):
                with self.assertRaisesRegex(ValueError, "symlink component"):
                    probe.prepare_quarantine(manifest, manifest["schedule"][0])
            self.assertFalse((Path(redirect) / "must-not-be-created").exists())

    def test_process_group_cleanup_kills_descendants_after_leader_exit(self):
        with tempfile.TemporaryDirectory(prefix="arena-process-group-test-") as raw:
            ready = Path(raw) / "child.pid"
            child_code = (
                "import os,signal,sys,time;"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
                "open(sys.argv[1], 'w').write(str(os.getpid()));"
                "time.sleep(30)"
            )
            leader_code = (
                "import subprocess,sys,time;"
                "subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[1]]);"
                "\nwhile True:\n"
                " try:\n"
                "  open(sys.argv[1]).read(); break\n"
                " except OSError: time.sleep(0.01)\n"
            )
            process = subprocess.Popen(
                [os.sys.executable, "-c", leader_code, str(ready), child_code],
                start_new_session=True,
            )
            try:
                self.assertEqual(process.wait(timeout=5), 0)
                self.assertTrue(ready.is_file())
                self.assertTrue(probe._process_group_exists(process.pid))
                probe.terminate_process_group(
                    process,
                    term_grace_seconds=0.1,
                    kill_grace_seconds=2.0,
                    poll_interval=0.01,
                )
                self.assertFalse(probe._process_group_exists(process.pid))
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_process_group_cleanup_escalates_after_active_leader_terminates(self):
        with tempfile.TemporaryDirectory(prefix="arena-process-group-test-") as raw:
            ready = Path(raw) / "child.pid"
            child_code = (
                "import os,signal,sys,time;"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
                "open(sys.argv[1], 'w').write(str(os.getpid()));"
                "time.sleep(30)"
            )
            leader_code = (
                "import subprocess,sys,time;"
                "subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[1]]);"
                "time.sleep(30)"
            )
            process = subprocess.Popen(
                [os.sys.executable, "-c", leader_code, str(ready), child_code],
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + 5
                while not ready.is_file() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(ready.is_file())
                probe.terminate_process_group(
                    process,
                    term_grace_seconds=0.1,
                    kill_grace_seconds=2.0,
                    poll_interval=0.01,
                )
                self.assertIsNotNone(process.returncode)
                self.assertFalse(probe._process_group_exists(process.pid))
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_process_scope_kills_descendant_that_detaches_into_a_new_session(self):
        try:
            probe.process_scope_capability()
        except (OSError, RuntimeError, ValueError) as exc:
            self.skipTest(f"cgroup-v2 process containment unavailable: {type(exc).__name__}")
        with tempfile.TemporaryDirectory(prefix="arena-process-scope-test-") as raw:
            ready = Path(raw) / "child.pid"
            slot = {"slot_id": f"synthetic-detached-{Path(raw).name}"}
            scope = probe.prepare_process_scope(slot)
            child_pid = None
            process = None
            child_code = (
                "import os,signal,sys,time;"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
                "open(sys.argv[1], 'w').write(str(os.getpid()));"
                "time.sleep(30)"
            )
            leader_code = (
                "import subprocess,sys,time;"
                "subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[1]], "
                "start_new_session=True);"
                "\nwhile True:\n"
                " try:\n"
                "  open(sys.argv[1]).read(); break\n"
                " except OSError: time.sleep(0.01)\n"
            )
            try:
                process = subprocess.Popen(
                    [os.sys.executable, "-c", leader_code, str(ready), child_code],
                    start_new_session=True,
                    pass_fds=(scope["attach_fd"],),
                    preexec_fn=lambda: probe.attach_process_scope(scope),
                )
                os.close(scope["attach_fd"])
                scope["attach_fd"] = None
                self.assertEqual(process.wait(timeout=5), 0)
                child_pid = int(ready.read_text())
                self.assertNotEqual(os.getpgid(child_pid), process.pid)
                self.assertTrue(probe._process_scope_populated(scope))
                probe.terminate_process_scope(
                    process,
                    scope,
                    term_grace_seconds=0.1,
                    kill_grace_seconds=2.0,
                    poll_interval=0.01,
                )
                self.assertTrue(scope["removed"])
            finally:
                if child_pid is not None:
                    try:
                        os.kill(child_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if not scope.get("removed"):
                    try:
                        probe.terminate_process_scope(
                            process,
                            scope,
                            term_grace_seconds=0.1,
                            kill_grace_seconds=2.0,
                            poll_interval=0.01,
                        )
                    except BaseException:
                        probe.close_process_scope(scope)

    def test_driver_discards_hostile_inherited_stdin_and_preserves_prompt_argument(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            capture_args = temp / "args.bin"
            capture_stdin = temp / "stdin.bin"
            capture_env = temp / "env.txt"
            fake = fake_bin / "claude"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"${1:-}\" == \"--version\" ]]; then echo '2.1.241 (Claude Code)'; exit 0; fi\n"
                "IFS= read -r incoming || true\n"
                "printf '%s' \"$incoming\" > \"$FAKE_STDIN\"\n"
                "printf '%s\\0' \"$@\" > \"$FAKE_ARGS\"\n"
                "printf '%s|%s|%s' \"${ARENA_CLAUDE_HOME-unset}\" \"${ARENA_HARNESS_COMMIT-unset}\" \"${ARENA_PLAN_TMPDIR-unset}\" > \"$FAKE_ENV\"\n"
                "printf '%s\\n' '{\"type\":\"system\",\"subtype\":\"init\",\"session_id\":\"fake-session\",\"model\":\"claude-opus-5\"}'\n"
                "printf '%s\\n' '{\"type\":\"assistant\",\"message\":{\"model\":\"claude-opus-5\",\"content\":[{\"type\":\"text\",\"text\":\"# Plan\"}]}}'\n"
                "printf '%s\\n' '{\"type\":\"result\",\"result\":\"# Plan\"}'\n"
            )
            fake.chmod(0o755)
            auth_home = temp / "claude-home"
            auth_home.mkdir()
            (auth_home / ".credentials.json").write_text(json.dumps({"accessToken": "fake-auth-value"}))
            bout = temp / "bout"
            environment = dict(os.environ)
            environment.update(
                {
                    "PATH": f"{fake_bin}:{environment['PATH']}",
                    "ARENA_PLAN_PROBE": "1",
                    "ARENA_CLAUDE_HOME": str(auth_home),
                    "ARENA_EFFORT": "native-default",
                    "ARENA_SETTING_SOURCES": "project",
                    "ARENA_SETTING_SOURCES_RECORD": "project (fresh auth-only per-run home)",
                    "ARENA_HARNESS_COMMIT": "offline-test-commit",
                    "ARENA_HARNESS_TRACKED_DIRTY": "false",
                    "FAKE_ARGS": str(capture_args),
                    "FAKE_ENV": str(capture_env),
                    "FAKE_STDIN": str(capture_stdin),
                }
            )
            completed = subprocess.run(
                [
                    str(probe.ROOT / "bin/run-task.sh"),
                    str(probe.ROOT / probe.TASK_REL),
                    "claude-opus-5",
                    str(bout),
                    "1",
                ],
                input=b"hostile appended input\n",
                env=environment,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
            self.assertEqual(capture_stdin.read_bytes(), b"")
            arguments = capture_args.read_bytes().split(b"\0")[:-1]
            self.assertEqual(arguments[0], b"-p")
            self.assertEqual(arguments[1], EXPECTED_PROMPT.encode())
            self.assertEqual(capture_env.read_text(), "unset|unset|unset")

    def test_every_target_driver_has_shell_level_stdin_isolation(self):
        for name in ("run-task.sh", "run-task-codex.sh", "run-task-kimi.sh"):
            source = (probe.ROOT / "bin" / name).read_text()
            self.assertIn("< /dev/null", source, name)
            self.assertIn("credential_scan.runtime.json", source, name)
            self.assertIn("exit 86", source, name)
        codex_source = (probe.ROOT / "bin/run-task-codex.sh").read_text()
        self.assertIn('HOME="$CODEX_HOME" CODEX_HOME="$CODEX_HOME"', codex_source)

    def test_staged_claude_wrapper_recovers_and_normalizes_offline(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            fake = fake_bin / "claude"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"${1:-}\" == \"--version\" ]]; then echo '2.1.241 (Claude Code)'; exit 0; fi\n"
                "printf '%s\\n' '{\"type\":\"system\",\"subtype\":\"init\",\"session_id\":\"stage-session\",\"model\":\"claude-opus-5\",\"tools\":[],\"agents\":[],\"skills\":[],\"plugins\":[],\"mcp_servers\":[]}'\n"
                "printf '%s\\n' '{\"type\":\"assistant\",\"message\":{\"id\":\"stage-message\",\"model\":\"claude-opus-5\",\"content\":[{\"type\":\"text\",\"text\":\"# Plan\"}]}}'\n"
                "printf '%s\\n' '{\"type\":\"result\",\"result\":\"# Plan\",\"total_cost_usd\":0,\"num_turns\":1,\"modelUsage\":{\"claude-opus-5\":{\"inputTokens\":1,\"outputTokens\":1}}}'\n"
            )
            fake.chmod(0o755)
            auth_home = temp / "auth"
            auth_home.mkdir()
            (auth_home / ".credentials.json").write_text(
                json.dumps({"accessToken": "offline-staged-auth-value-123456"})
            )
            _, manifest = make_manifest(temp / "manifest", phase="smoke")
            slot = next(
                slot
                for slot in manifest["schedule"]
                if slot["condition_id"].startswith("claude-code--")
            )
            env = probe.driver_environment(
                "claude",
                {
                    **os.environ,
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "ARENA_CLAUDE_HOME": str(auth_home),
                },
            )
            env["ARENA_HARNESS_COMMIT"] = "offline-stage-test"
            env["ARENA_HARNESS_TRACKED_DIRTY"] = "false"
            attempt_root, staged_run, command, staged_env = probe.prepare_staged_driver(
                manifest, slot, env
            )
            recovered = temp / "recovered"
            completed = subprocess.run(
                command,
                cwd=attempt_root,
                env=staged_env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=False,
            )
            probe.recover_and_remove_staged_driver(attempt_root, staged_run, recovered)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
            probe.scan_run_credentials("claude", staged_env, recovered, "credential_scan.raw.json")
            probe.scan_run_credentials("claude", staged_env, recovered, "credential_scan.json")
            synthetic_structure = json.loads(
                (recovered / "credential_scan.raw.json").read_text()
            )["source_redacted_credential_structure_sha256"]
            with mock.patch.object(
                probe,
                "_frozen_credential_structure_sha256",
                return_value=synthetic_structure,
            ):
                record = probe.observe_run(manifest, slot, recovered)
            self.assertEqual(record["validity"]["technical_issues"], [])
            self.assertTrue(record["embargo"]["pass"])


class ReviewAndAggregationTests(unittest.TestCase):
    def test_exact_evidence_offsets_and_hashes_are_required(self):
        text = "Use `[requirement]`."
        packet = {"blind_id": "P-1", "output_sha256": probe.sha256_bytes(text.encode()), "output": text}
        document = {
            "schema_version": 1,
            "reviewer_id": "r1",
            "independent_of": ["r2"],
            "reviews": [review_for("P-1", text, a_score=2)],
        }
        indexed, errors = analysis.validate_review_file(document, {"P-1": packet}, "reviewer")
        self.assertEqual(errors, [])
        self.assertEqual(indexed["P-1"]["A"]["score"], 2)
        bad = copy.deepcopy(document)
        bad["reviews"][0]["A"]["evidence"][0]["end"] -= 1
        _, errors = analysis.validate_review_file(bad, {"P-1": packet}, "reviewer")
        self.assertTrue(any("quote does not match" in error for error in errors))
        oversized = copy.deepcopy(document)
        oversized["reviews"][0]["A"]["evidence"][0]["end"] = 999
        _, errors = analysis.validate_review_file(oversized, {"P-1": packet}, "reviewer")
        self.assertTrue(any("invalid offsets" in error for error in errors))

    def test_blinding_self_identification_is_evidenced_and_reportable(self):
        text = "As Claude, I would use `[requirement]`."
        packet = {
            "blind_id": "P-1",
            "output_sha256": probe.sha256_bytes(text.encode()),
            "output": text,
        }
        review = review_for("P-1", text)
        review["blinding"]["self_identifies_model_or_condition"] = {
            "value": True,
            "rationale": "the output names a model condition",
            "evidence": [{"quote": "As Claude", "start": 0, "end": 9}],
        }
        document = {
            "schema_version": 1,
            "reviewer_id": "r1",
            "independent_of": ["r2"],
            "reviews": [review],
        }
        indexed, errors = analysis.validate_review_file(
            document, {"P-1": packet}, "reviewer"
        )
        self.assertEqual(errors, [])
        values = {
            field: analysis.get_value(indexed["P-1"], field)
            for field in analysis.ALL_FIELDS
        }
        run_record = {
            "output": {"present": True, "sha256": packet["output_sha256"]},
            "embargo": {
                "pass": True,
                "target_originated_tool_or_function_call": False,
                "spawned_agent": False,
                "repository_or_file_inspection": False,
                "research_or_network_action": False,
                "implementation_or_mutation_attempt": False,
                "unclassified_tool_action": False,
                "trace_integrity_failure": False,
            },
            "metrics": {},
            "completion": {},
        }
        row = analysis.derive_row(
            "P-1",
            values,
            {"slot_id": "s1", "condition_id": "c1"},
            run_record,
        )
        self.assertTrue(row["blinding_compromised"])

    def test_two_reviewers_and_every_disagreement_require_distinct_adjudication(self):
        text = "Use `[requirement]`."
        packet = {"blind_id": "P-1", "output_sha256": probe.sha256_bytes(text.encode()), "output": text}
        first_doc = {
            "schema_version": 1,
            "reviewer_id": "r1",
            "independent_of": ["r2"],
            "reviews": [review_for("P-1", text, a_score=1)],
        }
        second_doc = {
            "schema_version": 1,
            "reviewer_id": "r2",
            "independent_of": ["r1"],
            "reviews": [review_for("P-1", text, a_score=2)],
        }
        first, errors_a = analysis.validate_review_file(first_doc, {"P-1": packet}, "a")
        second, errors_b = analysis.validate_review_file(second_doc, {"P-1": packet}, "b")
        self.assertEqual(errors_a + errors_b, [])
        expected = analysis.disagreements(first, second)
        self.assertEqual(expected, [("P-1", "A")])
        empty = {"schema_version": 1, "adjudicator_id": "r3", "resolutions": []}
        _, errors = analysis.validate_adjudications(empty, expected, {"P-1": packet}, {"r1", "r2"})
        self.assertTrue(any("unresolved" in error for error in errors))
        resolved = {
            "schema_version": 1,
            "adjudicator_id": "r3",
            "resolutions": [
                {
                    "blind_id": "P-1",
                    "field": "A",
                    "value": 2,
                    "output_sha256": probe.sha256_bytes(text.encode()),
                    "rationale": "anchor met",
                    "evidence": evidence(text),
                }
            ],
        }
        _, errors = analysis.validate_adjudications(resolved, expected, {"P-1": packet}, {"r1", "r2"})
        self.assertEqual(errors, [])

    def test_wilson_intervals_do_not_turn_clean_sweeps_into_universal_claims(self):
        ten = analysis.wilson(10, 10)
        twenty = analysis.wilson(20, 20)
        self.assertLess(ten["lower"], 0.75)
        self.assertGreater(twenty["lower"], 0.83)
        self.assertLess(twenty["lower"], 1.0)
        self.assertEqual(twenty["upper"], 1.0)

    def test_agreement_handles_ordinal_binary_and_constant_edge_cases(self):
        ordinal = [(0, 0), (1, 2), (3, 3)]
        self.assertAlmostEqual(analysis.agreement_rate(ordinal), 2 / 3)
        self.assertIsNotNone(analysis.cohen_kappa(ordinal, weighted=True))
        self.assertIsNone(analysis.cohen_kappa([(True, True), (True, True)], weighted=False))

    def test_instruction_exposure_requires_two_reviewers_and_exact_policy_quote(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            artifact = Path(raw) / "instruction_context.json"
            artifact.write_text("system policy encourages review")
            rel = str(artifact.relative_to(probe.ROOT))
            quote = "encourages review"
            start = artifact.read_text().index(quote)
            finding = {
                "status": "optional_or_encouraged",
                "rationale": "The policy encourages the behavior.",
                "evidence": [
                    {
                        "artifact_path": rel,
                        "artifact_sha256": probe.sha256_path(artifact),
                        "precedence": "system",
                        "quote": quote,
                        "start": start,
                        "end": start + len(quote),
                    }
                ],
            }
            document = {
                "schema_version": 1,
                "coded_before_semantic_outputs_unblinded": True,
                "coding_reviewers": ["c1", "c2"],
                "conditions": [
                    {
                        "condition_id": "only",
                        "coverage": "complete",
                        "orchestration": finding,
                        "independent_qa": finding,
                        "artifacts": [{"path": rel, "sha256": probe.sha256_path(artifact)}],
                        "limitations": [],
                    }
                ],
            }
            _, errors = analysis.validate_instruction_exposure(document, {"only"})
            self.assertEqual(errors, [])
            altered = copy.deepcopy(document)
            altered["conditions"][0]["unexpected"] = True
            _, errors = analysis.validate_instruction_exposure(altered, {"only"})
            self.assertTrue(any("condition fields differ" in error for error in errors))
            document["coding_reviewers"] = ["same", "same"]
            _, errors = analysis.validate_instruction_exposure(document, {"only"})
            self.assertTrue(any("two distinct" in error for error in errors))

    def test_derived_full_compliance_keeps_embargo_failures_in_the_row(self):
        values = {field: 0 for field in analysis.ORDINAL_FIELDS}
        values.update({f"E.{field}": False for field in analysis.E_FIELDS})
        values.update({f"F.{field}": False for field in analysis.F_FIELDS})
        values.update({f"blinding.{field}": False for field in analysis.BLINDING_FIELDS})
        values["F.uses_explicit_placeholders"] = True
        values["F.separates_assumptions_from_facts"] = True
        run_record = {
            "output": {"present": True, "sha256": "0" * 64},
            "embargo": {
                "pass": False,
                "target_originated_tool_or_function_call": True,
                "spawned_agent": True,
                "repository_or_file_inspection": False,
                "research_or_network_action": False,
                "implementation_or_mutation_attempt": False,
                "unclassified_tool_action": False,
                "trace_integrity_failure": False,
            },
            "metrics": {},
            "completion": {},
        }
        row = analysis.derive_row("P-1", values, {"slot_id": "s1", "condition_id": "c1"}, run_record)
        self.assertFalse(row["embargo_pass"])
        self.assertFalse(row["full_compliance"])
        self.assertEqual(row["F_trace"]["spawned_agent"], True)

    def test_aggregate_binds_packets_to_frozen_ledger_and_artifacts(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            paths = seed_confirmatory_matrix(Path(raw))
            result, errors = analysis.aggregate(
                manifest_path=paths["manifest"],
                packets_path=paths["packets"],
                blind_map_path=paths["mapping"],
                reviewer_a_path=paths["reviewer_a"],
                reviewer_b_path=paths["reviewer_b"],
                adjudications_path=paths["adjudications"],
                instruction_exposure_path=paths["exposure"],
            )
            self.assertEqual(errors, [])
            self.assertTrue(result["complete"])
            self.assertEqual(len(result["per_run"]), 30)
            self.assertEqual(result["reviewers"]["blinding_compromised_runs"], 0)
            self.assertIn("blinding", analysis.render_report(result).lower())
            tampered = json.loads(paths["packets"].read_text())
            tampered["packets"][0]["output"] += "tampered"
            paths["packets"].write_text(json.dumps(tampered))
            _, errors = analysis.aggregate(
                manifest_path=paths["manifest"],
                packets_path=paths["packets"],
                blind_map_path=paths["mapping"],
                reviewer_a_path=paths["reviewer_a"],
                reviewer_b_path=paths["reviewer_b"],
                adjudications_path=paths["adjudications"],
                instruction_exposure_path=paths["exposure"],
            )
            self.assertTrue(any("packet text/hash" in error for error in errors))

    def test_analysis_outputs_are_no_clobber_and_content_addressed_as_a_bundle(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            paths = seed_confirmatory_matrix(temp)
            output_json = temp / "analysis.json"
            output_report = temp / "REPORT.md"
            output_manifest = temp / "ANALYSIS_MANIFEST.json"
            command = [
                "python3",
                str(ANALYZE_PATH),
                "--manifest",
                str(paths["manifest"]),
                "--packets",
                str(paths["packets"]),
                "--blind-map",
                str(paths["mapping"]),
                "--reviewer-a",
                str(paths["reviewer_a"]),
                "--reviewer-b",
                str(paths["reviewer_b"]),
                "--adjudications",
                str(paths["adjudications"]),
                "--instruction-exposure",
                str(paths["exposure"]),
                "--output-json",
                str(output_json),
                "--output-report",
                str(output_report),
                "--output-manifest",
                str(output_manifest),
            ]
            first = subprocess.run(command, cwd=probe.ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            bundle = json.loads(output_manifest.read_text())
            self.assertEqual({item["role"] for item in bundle["outputs"]}, {
                "machine_readable_analysis",
                "human_readable_report",
            })
            input_roles = [item["role"] for item in bundle["inputs"]]
            self.assertEqual(input_roles.count("execution_ledger"), 1)
            self.assertEqual(sum(role.startswith("effective_run_record:") for role in input_roles), 30)
            self.assertEqual(sum(role.startswith("effective_artifact_manifest:") for role in input_roles), 30)
            analysis_doc = json.loads(output_json.read_text())
            self.assertIn("semantic_review_provenance", analysis_doc["per_run"][0])
            second = subprocess.run(command, cwd=probe.ROOT, capture_output=True, text=True, check=False)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("refusing to overwrite", second.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
