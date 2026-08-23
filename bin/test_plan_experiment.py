#!/usr/bin/env python3
"""Offline tests for the pre-requirements planning experiment.

No model, network, or paid run is invoked.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import tempfile
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
        "credential_pattern_count": 1,
        "scanned_entry_count": 1,
        "scanned_regular_and_symlink_bytes": 1,
        "leak_match_count": 0,
        "unsafe_special_entry_count": 0,
        "escaping_symlink_count": 0,
        "pass": True,
    }
    (run_dir / "credential_scan.raw.json").write_text(json.dumps(scan_receipt))
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
                {"type": "item.completed", "item": {"id": "msg-1", "type": "agent_message", "text": output}},
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
                {"role": "assistant", "content": output},
            ],
        )
        jsonl(
            run_dir / "wire.jsonl",
            [
                {"type": "config.update", "systemPrompt": "base"},
                {"type": "tools.set_active_tools", "names": ["Read"]},
                {"type": "llm.tools_snapshot", "hash": "tools", "tools": []},
                {"type": "llm.request", "model": condition["requested_model"], "thinkingEffort": "max"},
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
            (run_dir / "artifact_manifest.json").write_text('{"schema_version":1,"artifacts":[]}\n')
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
                    "analysis_eligible": False,
                    "smoke_excluded": True,
                    "preflight": preflight,
                }

            errors = probe.validate_execution_ledger(
                manifest,
                [row(manifest["schedule"][1]), row(manifest["schedule"][0])],
            )
            self.assertTrue(any("prefix of frozen sequence" in error for error in errors))

    def test_pre_directory_driver_failure_is_preserved_in_ledger(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            path, manifest = make_manifest(temp / "manifest", phase="smoke")
            manifest["bout_dir"] = str((temp / "bout").relative_to(probe.ROOT))
            manifest["freeze_id"] = probe.compute_freeze_id(manifest)
            path.write_text(json.dumps(manifest))
            slot = manifest["schedule"][0]
            preflight = {"condition_id": slot["condition_id"]}
            preflight["sha256"] = probe.sha256_bytes(probe.canonical_json(preflight))
            snapshot = {slot["condition_id"]: preflight}
            with mock.patch.object(probe, "preflight_manifest", return_value=snapshot), mock.patch.object(
                probe.subprocess, "Popen", side_effect=OSError("driver unavailable")
            ):
                with self.assertRaisesRegex(RuntimeError, "ledger row was preserved"):
                    probe.run_slots(path, approval=None, requested_slots={slot["slot_id"]}, dry_run=False)
            ledger, malformed = probe.iter_jsonl(probe.ROOT / manifest["bout_dir"] / "EXECUTION.jsonl")
            self.assertEqual(malformed, [])
            self.assertEqual(len(ledger), 1)
            self.assertFalse(ledger[0]["analysis_eligible"])
            self.assertEqual(ledger[0]["eligible_exclusion_reasons"], ["harness_crash_before_target_execution"])
            self.assertTrue((probe.ROOT / ledger[0]["failure_receipt"]).is_file())

    def test_target_chosen_empty_output_remains_confirmatory_eligible_for_every_driver(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", repeats=10)
            conditions = probe.condition_map(manifest)
            for index, slot in enumerate(manifest["schedule"][:3]):
                run_dir = temp / f"run-{index}"
                seed_run(run_dir, conditions[slot["condition_id"]], output="")
                record = probe.observe_run(manifest, slot, run_dir)
                self.assertEqual(record["validity"]["technical_issues"], [], slot["condition_id"])
                self.assertTrue(record["validity"]["confirmatory_analysis_eligible"])
                self.assertFalse(record["output"]["present"])

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
                    wire, _ = probe.iter_jsonl(run_dir / "wire.jsonl")
                    wire.append({"type": "llm.request", "model": "unexpected-model", "thinkingEffort": "max", "_line": 99})
                    jsonl(run_dir / "wire.jsonl", [{k: v for k, v in event.items() if k != "_line"} for event in wire])
                else:
                    session, _ = probe.iter_jsonl(run_dir / "session.jsonl")
                    session = [event for event in session if event.get("type") != "turn_context"]
                    jsonl(run_dir / "session.jsonl", [{k: v for k, v in event.items() if k != "_line"} for event in session])
                record = probe.observe_run(manifest, slot, run_dir)
                expected = "observable model identity missing" if driver == "codex" else "model mismatch"
                self.assertTrue(
                    any(expected in issue for issue in record["validity"]["technical_issues"]),
                    (driver, record["validity"]["technical_issues"]),
                )

    def test_pre_attributable_transport_failure_is_ineligible_and_replaceable(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            _, manifest = make_manifest(temp / "manifest", repeats=10)
            slot = next(slot for slot in manifest["schedule"] if slot["condition_id"].startswith("codex--"))
            run_dir = temp / "run"
            seed_run(run_dir, probe.condition_map(manifest)[slot["condition_id"]], output="")
            session, _ = probe.iter_jsonl(run_dir / "session.jsonl")
            session = [event for event in session if event.get("type") != "turn_context"]
            jsonl(run_dir / "session.jsonl", [{k: v for k, v in event.items() if k != "_line"} for event in session])
            metrics = json.loads((run_dir / "metrics.json").read_text())
            metrics["agent_exit"] = 1
            (run_dir / "metrics.json").write_text(json.dumps(metrics))
            record = probe.observe_run(manifest, slot, run_dir)
            self.assertFalse(record["validity"]["confirmatory_analysis_eligible"])
            self.assertEqual(record["validity"]["state"], "invalid_exogenous_pre_attribution")
            self.assertIn(
                "transport_or_service_failure_before_request_acceptance",
                probe.eligible_exclusion_reasons(record),
            )

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

    def test_driver_environment_is_minimal_and_driver_specific(self):
        source = {
            "HOME": "/home/operator",
            "PATH": "/bin",
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
        self.assertNotIn("OPENAI_API_KEY", codex)
        self.assertNotIn("KIMI_API_KEY", kimi)
        self.assertEqual(kimi["ARENA_KIMI_HOME"], "/outside/kimi")


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

    def test_driver_discards_hostile_inherited_stdin_and_preserves_prompt_argument(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT) as raw:
            temp = Path(raw)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            capture_args = temp / "args.bin"
            capture_stdin = temp / "stdin.bin"
            fake = fake_bin / "claude"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"${1:-}\" == \"--version\" ]]; then echo '2.1.241 (Claude Code)'; exit 0; fi\n"
                "IFS= read -r incoming || true\n"
                "printf '%s' \"$incoming\" > \"$FAKE_STDIN\"\n"
                "printf '%s\\0' \"$@\" > \"$FAKE_ARGS\"\n"
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
                    "FAKE_ARGS": str(capture_args),
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

    def test_every_target_driver_has_shell_level_stdin_isolation(self):
        for name in ("run-task.sh", "run-task-codex.sh", "run-task-kimi.sh"):
            source = (probe.ROOT / "bin" / name).read_text()
            self.assertIn("< /dev/null", source, name)


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
            analysis_doc = json.loads(output_json.read_text())
            self.assertIn("semantic_review_provenance", analysis_doc["per_run"][0])
            second = subprocess.run(command, cwd=probe.ROOT, capture_output=True, text=True, check=False)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("refusing to overwrite", second.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
