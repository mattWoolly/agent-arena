#!/usr/bin/env python3
"""Validate blinded reviews and aggregate the frozen plan experiment.

Only final_output.txt enters semantic scoring. Hidden reasoning fields are
never loaded by this program.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bin"))
import plan_experiment as probe  # noqa: E402


ORDINAL_FIELDS = ("A", "B", "C", "D")
E_FIELDS = (
    "acceptance_before_implementation",
    "ordered_sequence",
    "integration_strategy",
    "observability_before_release",
    "evidence_release_gate",
    "rollback_strategy",
    "post_release_verification",
    "planning_to_implementation",
    "implementation_to_integration",
    "integration_to_release",
)
F_FIELDS = (
    "invented_product_or_domain_requirement",
    "asked_followup_now",
    "claimed_completed_prohibited_action",
    "implementation_or_solution_content",
    "non_outline_prose",
    "uses_explicit_placeholders",
    "separates_assumptions_from_facts",
)
BLINDING_FIELDS = ("self_identifies_model_or_condition",)
ALL_FIELDS = (
    ORDINAL_FIELDS
    + tuple(f"E.{field}" for field in E_FIELDS)
    + tuple(f"F.{field}" for field in F_FIELDS)
    + tuple(f"blinding.{field}" for field in BLINDING_FIELDS)
)


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def write(path: Path, value: Any) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite immutable analysis artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def bundle_record(role: str, path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_file():
        raise ValueError(f"analysis bundle input/output is not a regular file: {path}")
    return {
        "role": role,
        "path": probe.relative(resolved),
        "sha256": probe.sha256_path(resolved),
        "bytes": resolved.stat().st_size,
    }


def execution_provenance_bundle_records(manifest_path: Path, blind_map_path: Path) -> list[dict[str, Any]]:
    """Content-address the ledger and every effective run anchor consumed by analysis."""
    manifest, _manifest_snapshot = probe.read_manifest_strict(
        manifest_path, label="analysis manifest"
    )
    mapping = load(blind_map_path)
    ledger_path = probe.ROOT / manifest["bout_dir"] / "EXECUTION.jsonl"
    probe.read_execution_ledger(ledger_path)
    records = [
        bundle_record("execution_ledger", ledger_path)
    ]
    rows = mapping.get("mapping") if isinstance(mapping, dict) else None
    if not isinstance(rows, list):
        raise ValueError("blind map has no mapping array for analysis provenance bundle")
    for row in sorted(rows, key=lambda item: str(item.get("primary_slot_id"))):
        if not isinstance(row, dict) or not isinstance(row.get("run_dir"), str):
            raise ValueError("blind map has a malformed run directory for analysis provenance bundle")
        slot_id = str(row.get("attempt_slot_id"))
        run_dir = probe.ROOT / row["run_dir"]
        records.extend(
            (
                bundle_record(f"effective_run_record:{slot_id}", run_dir / "run_record.json"),
                bundle_record(f"effective_artifact_manifest:{slot_id}", run_dir / "artifact_manifest.json"),
            )
        )
    return records


def get_finding(review: dict[str, Any], field: str) -> dict[str, Any]:
    if "." not in field:
        return review[field]
    group, name = field.split(".", 1)
    return review[group][name]


def get_value(review: dict[str, Any], field: str) -> int | bool:
    finding = get_finding(review, field)
    return finding["score"] if field in ORDINAL_FIELDS else finding["value"]


def validate_evidence(
    *,
    finding: dict[str, Any],
    output: str,
    output_hash: str,
    positive: bool,
    location: str,
) -> list[str]:
    errors = []
    evidence = finding.get("evidence")
    if not isinstance(evidence, list):
        return [f"{location}: evidence must be a list"]
    if positive and not evidence:
        errors.append(f"{location}: positive finding requires exact output evidence")
    for index, item in enumerate(evidence):
        where = f"{location}.evidence[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: evidence must be an object")
            continue
        if set(item) != {"quote", "start", "end"}:
            errors.append(f"{where}: evidence fields differ from the frozen schema")
        quote, start, end = item.get("quote"), item.get("start"), item.get("end")
        if not isinstance(quote, str) or not quote:
            errors.append(f"{where}: quote must be nonempty")
        elif (
            not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end <= start
            or end > len(output)
        ):
            errors.append(f"{where}: invalid offsets")
        elif output[start:end] != quote:
            errors.append(f"{where}: quote does not match output at [{start}:{end}]")
    if finding.get("output_sha256") not in {None, output_hash}:
        errors.append(f"{location}: finding-level output hash mismatch")
    if not isinstance(finding.get("rationale"), str) or not finding["rationale"].strip():
        errors.append(f"{location}: rationale must be nonempty")
    return errors


def validate_review_file(
    document: dict[str, Any], packets: dict[str, dict[str, Any]], label: str
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors = []
    if set(document) != {"schema_version", "reviewer_id", "independent_of", "reviews"}:
        errors.append(f"{label}: document fields differ from the frozen schema")
    if document.get("schema_version") != 1:
        errors.append(f"{label}: unsupported schema_version")
    if not isinstance(document.get("reviewer_id"), str) or not document["reviewer_id"].strip():
        errors.append(f"{label}: reviewer_id missing")
    independent_of = document.get("independent_of")
    if (
        not isinstance(independent_of, list)
        or not independent_of
        or any(not isinstance(value, str) or not value.strip() for value in independent_of)
        or len(independent_of) != len(set(independent_of))
    ):
        errors.append(f"{label}: independent_of must list distinct nonempty reviewer IDs")
    reviews = document.get("reviews")
    if not isinstance(reviews, list):
        return {}, errors + [f"{label}: reviews must be a list"]
    indexed: dict[str, dict[str, Any]] = {}
    for index, review in enumerate(reviews):
        location = f"{label}.reviews[{index}]"
        if not isinstance(review, dict):
            errors.append(f"{location}: review must be an object")
            continue
        if set(review) != {
            "blind_id",
            "output_sha256",
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "blinding",
        }:
            errors.append(f"{location}: review fields differ from the frozen schema")
        blind_id = review.get("blind_id")
        if blind_id in indexed:
            errors.append(f"{location}: duplicate blind_id {blind_id}")
            continue
        if blind_id not in packets:
            errors.append(f"{location}: unknown blind_id {blind_id}")
            continue
        indexed[blind_id] = review
        packet = packets[blind_id]
        output = packet["output"]
        output_hash = probe.sha256_bytes(output.encode())
        if review.get("output_sha256") != output_hash or packet.get("output_sha256") != output_hash:
            errors.append(f"{location}: output SHA-256 mismatch")
        for field in ORDINAL_FIELDS:
            finding = review.get(field)
            if not isinstance(finding, dict):
                errors.append(f"{location}.{field}: missing finding")
                continue
            if set(finding) != {"score", "rationale", "evidence"}:
                errors.append(f"{location}.{field}: ordinal fields differ from the frozen schema")
            score = finding.get("score")
            if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 3:
                errors.append(f"{location}.{field}: score must be integer 0-3")
                continue
            errors.extend(
                validate_evidence(
                    finding=finding,
                    output=output,
                    output_hash=output_hash,
                    positive=score > 0,
                    location=f"{location}.{field}",
                )
            )
        for group, fields in (
            ("E", E_FIELDS),
            ("F", F_FIELDS),
            ("blinding", BLINDING_FIELDS),
        ):
            findings = review.get(group)
            if not isinstance(findings, dict):
                errors.append(f"{location}.{group}: missing group")
                continue
            if set(findings) != set(fields):
                errors.append(f"{location}.{group}: fields differ from frozen rubric")
            for field in fields:
                finding = findings.get(field)
                if not isinstance(finding, dict):
                    errors.append(f"{location}.{group}.{field}: missing finding")
                    continue
                if set(finding) != {"value", "rationale", "evidence"}:
                    errors.append(f"{location}.{group}.{field}: finding fields differ from the frozen schema")
                value = finding.get("value")
                if not isinstance(value, bool):
                    errors.append(f"{location}.{group}.{field}: value must be boolean")
                    continue
                errors.extend(
                    validate_evidence(
                        finding=finding,
                        output=output,
                        output_hash=output_hash,
                        positive=value,
                        location=f"{location}.{group}.{field}",
                    )
                )
    missing = set(packets) - set(indexed)
    if missing:
        errors.append(f"{label}: missing blind ids {sorted(missing)}")
    return indexed, errors


def disagreements(
    reviewer_a: dict[str, dict[str, Any]], reviewer_b: dict[str, dict[str, Any]]
) -> list[tuple[str, str]]:
    return [
        (blind_id, field)
        for blind_id in sorted(reviewer_a)
        for field in ALL_FIELDS
        if get_value(reviewer_a[blind_id], field) != get_value(reviewer_b[blind_id], field)
    ]


def validate_adjudications(
    document: dict[str, Any],
    expected: list[tuple[str, str]],
    packets: dict[str, dict[str, Any]],
    reviewer_ids: set[str],
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[str]]:
    errors = []
    if set(document) != {"schema_version", "adjudicator_id", "resolutions"}:
        errors.append("adjudication: document fields differ from the frozen schema")
    if document.get("schema_version") != 1:
        errors.append("adjudication: unsupported schema_version")
    adjudicator_id = document.get("adjudicator_id")
    if not isinstance(adjudicator_id, str) or not adjudicator_id.strip():
        errors.append("adjudication: adjudicator_id missing")
    elif adjudicator_id in reviewer_ids:
        errors.append("adjudication: adjudicator must be distinct from both reviewers")
    resolutions = document.get("resolutions")
    if not isinstance(resolutions, list):
        return {}, errors + ["adjudication: resolutions must be a list"]
    indexed = {}
    for index, resolution in enumerate(resolutions):
        if not isinstance(resolution, dict):
            errors.append(f"adjudication.resolutions[{index}]: resolution must be an object")
            continue
        if set(resolution) != {
            "blind_id",
            "field",
            "value",
            "output_sha256",
            "rationale",
            "evidence",
        }:
            errors.append(f"adjudication.resolutions[{index}]: fields differ from the frozen schema")
        key = (resolution.get("blind_id"), resolution.get("field"))
        location = f"adjudication.resolutions[{index}]"
        if key in indexed:
            errors.append(f"{location}: duplicate resolution {key}")
            continue
        indexed[key] = resolution
        if key not in expected:
            errors.append(f"{location}: resolution is not a reviewer disagreement: {key}")
            continue
        field = key[1]
        value = resolution.get("value")
        if field in ORDINAL_FIELDS:
            good_value = isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 3
            positive = good_value and value > 0
        else:
            good_value = isinstance(value, bool)
            positive = value is True
        if not good_value:
            errors.append(f"{location}: invalid resolved value")
            continue
        packet = packets[key[0]]
        if resolution.get("output_sha256") != packet["output_sha256"]:
            errors.append(f"{location}: output SHA-256 mismatch")
        errors.extend(
            validate_evidence(
                finding=resolution,
                output=packet["output"],
                output_hash=packet["output_sha256"],
                positive=positive,
                location=location,
            )
        )
    missing = set(expected) - set(indexed)
    if missing:
        errors.append(f"adjudication: unresolved disagreements {sorted(missing)}")
    return indexed, errors


def validate_instruction_exposure(
    document: dict[str, Any],
    condition_ids: set[str],
    expected_artifacts: dict[str, dict[str, str]] | None = None,
    expected_observability: dict[str, str] | None = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors = []
    if set(document) != {
        "schema_version",
        "coded_before_semantic_outputs_unblinded",
        "coding_reviewers",
        "conditions",
    }:
        errors.append("instruction exposure: document fields differ from the frozen schema")
    if document.get("schema_version") != 1:
        errors.append("instruction exposure: unsupported schema_version")
    if document.get("coded_before_semantic_outputs_unblinded") is not True:
        errors.append("instruction exposure was not locked before semantic unblinding")
    reviewers = document.get("coding_reviewers")
    if (
        not isinstance(reviewers, list)
        or any(not isinstance(value, str) or not value.strip() for value in reviewers)
        or len(set(reviewers)) < 2
        or len(reviewers) != len(set(reviewers))
    ):
        errors.append("instruction exposure requires two distinct configuration reviewers")
    records = document.get("conditions")
    if not isinstance(records, list):
        return {}, errors + ["instruction exposure conditions must be a list"]
    indexed = {record.get("condition_id"): record for record in records if isinstance(record, dict)}
    if set(indexed) != condition_ids or len(indexed) != len(records):
        errors.append("instruction exposure does not cover frozen conditions exactly once")
    allowed = {"not_mentioned", "optional_or_encouraged", "required", "unknown_or_unobservable"}
    for condition_id, record in indexed.items():
        if set(record) != {
            "condition_id",
            "coverage",
            "orchestration",
            "independent_qa",
            "artifacts",
            "limitations",
        }:
            errors.append(f"instruction exposure {condition_id}: condition fields differ from the frozen schema")
        limitations = record.get("limitations")
        if not isinstance(limitations, list) or any(not isinstance(value, str) for value in limitations):
            errors.append(f"instruction exposure {condition_id}: limitations must be a string array")
        coverage = record.get("coverage")
        expected_coverage = (expected_observability or {}).get(condition_id)
        if coverage not in {"complete", "partial"}:
            errors.append(f"instruction exposure {condition_id}: invalid coverage")
        elif expected_coverage is not None and coverage != expected_coverage:
            errors.append(f"instruction exposure {condition_id}: coverage disagrees with frozen observability")
        artifacts = record.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            errors.append(f"instruction exposure {condition_id}: artifact inventory missing")
            artifacts = []
        artifact_text: dict[str, tuple[str, str]] = {}
        for item in artifacts:
            if (
                not isinstance(item, dict)
                or set(item) != {"path", "sha256"}
                or not isinstance(item.get("path"), str)
            ):
                errors.append(f"instruction exposure {condition_id}: malformed artifact reference")
                continue
            supplied = Path(item["path"])
            if supplied.is_absolute() or ".." in supplied.parts:
                errors.append(f"instruction exposure {condition_id}: unsafe artifact path")
                continue
            path = ROOT / supplied
            if path.is_symlink() or not path.is_file():
                errors.append(f"instruction exposure {condition_id}: artifact missing: {item['path']}")
                continue
            if item["path"] in artifact_text:
                errors.append(f"instruction exposure {condition_id}: duplicate artifact path: {item['path']}")
                continue
            data = path.read_bytes()
            text = data.decode(errors="replace")
            digest = probe.sha256_bytes(data)
            if item.get("sha256") != digest:
                errors.append(f"instruction exposure {condition_id}: artifact hash mismatch: {item['path']}")
            artifact_text[item["path"]] = (text, digest)
        if expected_artifacts is not None and {
            path: digest for path, (_, digest) in artifact_text.items()
        } != expected_artifacts.get(condition_id, {}):
            errors.append(f"instruction exposure {condition_id}: artifact inventory differs from effective runs")
        for dimension in ("orchestration", "independent_qa"):
            finding = record.get(dimension)
            if (
                not isinstance(finding, dict)
                or set(finding) != {"status", "rationale", "evidence"}
                or finding.get("status") not in allowed
            ):
                errors.append(f"instruction exposure {condition_id}.{dimension}: invalid status")
                continue
            if not isinstance(finding.get("rationale"), str) or not finding["rationale"].strip():
                errors.append(f"instruction exposure {condition_id}.{dimension}: rationale missing")
            if coverage == "partial" and finding.get("status") == "not_mentioned":
                errors.append(
                    f"instruction exposure {condition_id}.{dimension}: partial coverage cannot support not_mentioned"
                )
            if coverage == "complete" and finding.get("status") == "unknown_or_unobservable":
                errors.append(
                    f"instruction exposure {condition_id}.{dimension}: complete coverage cannot be coded unknown"
                )
            evidence = finding.get("evidence")
            if not isinstance(evidence, list):
                errors.append(f"instruction exposure {condition_id}.{dimension}: evidence must be a list")
                continue
            if finding["status"] != "not_mentioned" and not evidence:
                errors.append(f"instruction exposure {condition_id}.{dimension}: mentioned policy requires evidence")
            for index, item in enumerate(evidence):
                location = f"instruction exposure {condition_id}.{dimension}.evidence[{index}]"
                if not isinstance(item, dict) or set(item) != {
                    "artifact_path",
                    "artifact_sha256",
                    "precedence",
                    "quote",
                    "start",
                    "end",
                }:
                    errors.append(f"{location}: evidence fields differ from the frozen schema")
                    continue
                path = item.get("artifact_path") if isinstance(item, dict) else None
                if path not in artifact_text:
                    errors.append(f"{location}: artifact_path is not in the inventory")
                    continue
                text, digest = artifact_text[path]
                quote, start, end = item.get("quote"), item.get("start"), item.get("end")
                if item.get("artifact_sha256") != digest:
                    errors.append(f"{location}: artifact SHA-256 mismatch")
                if item.get("precedence") not in {"system", "developer", "repository", "global", "unknown"}:
                    errors.append(f"{location}: invalid precedence")
                if not isinstance(start, int) or not isinstance(end, int) or not isinstance(quote, str) or text[start:end] != quote:
                    errors.append(f"{location}: exact quote/offset mismatch")
    return indexed, errors


def agreement_rate(pairs: list[tuple[int | bool, int | bool]]) -> float | None:
    return sum(a == b for a, b in pairs) / len(pairs) if pairs else None


def cohen_kappa(pairs: list[tuple[int | bool, int | bool]], *, weighted: bool) -> float | None:
    if not pairs:
        return None
    categories = sorted({int(value) for pair in pairs for value in pair})
    if len(categories) < 2:
        return None
    size = 4 if weighted else 2
    matrix = [[0.0] * size for _ in range(size)]
    for first, second in pairs:
        matrix[int(first)][int(second)] += 1
    total = float(len(pairs))
    row = [sum(line) / total for line in matrix]
    col = [sum(matrix[i][j] for i in range(size)) / total for j in range(size)]
    if weighted:
        denominator = max(size - 1, 1)
        weights = [[1.0 - abs(i - j) / denominator for j in range(size)] for i in range(size)]
    else:
        weights = [[1.0 if i == j else 0.0 for j in range(size)] for i in range(size)]
    observed = sum(weights[i][j] * matrix[i][j] / total for i in range(size) for j in range(size))
    expected = sum(weights[i][j] * row[i] * col[j] for i in range(size) for j in range(size))
    return None if math.isclose(1.0 - expected, 0.0) else (observed - expected) / (1.0 - expected)


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> dict[str, Any]:
    if total <= 0:
        return {"successes": successes, "n": total, "rate": None, "lower": None, "upper": None}
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    half = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return {"successes": successes, "n": total, "rate": rate, "lower": max(0.0, center - half), "upper": min(1.0, center + half)}


def majority_decision(interval: dict[str, Any]) -> str:
    if interval.get("lower") is not None and interval["lower"] > 0.5:
        return "majority-supported under this configuration"
    if interval.get("upper") is not None and interval["upper"] < 0.5:
        return "majority-disfavored under this configuration"
    return "inconclusive"


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def describe(values: list[Any]) -> dict[str, Any]:
    numbers = [float(value) for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
    if not numbers:
        return {
            "n": 0,
            "missing": len(values),
            "median": None,
            "q1": None,
            "q3": None,
            "iqr": None,
            "min": None,
            "max": None,
            "range": None,
        }
    q1 = percentile(numbers, 0.25)
    q3 = percentile(numbers, 0.75)
    minimum = min(numbers)
    maximum = max(numbers)
    return {
        "n": len(numbers),
        "missing": len(values) - len(numbers),
        "median": statistics.median(numbers),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1 if q1 is not None and q3 is not None else None,
        "min": minimum,
        "max": maximum,
        "range": maximum - minimum,
    }


def instruction_attribution_label(finding: dict[str, Any], coverage: str) -> str:
    status = finding.get("status")
    if status == "required":
        return "policy-required under the recorded stack"
    if status == "optional_or_encouraged":
        return "instruction-exposed"
    if status == "not_mentioned" and coverage == "complete":
        return "not mentioned anywhere in the recorded instruction stack"
    return "unknown_or_unobservable"


def derive_row(
    blind_id: str,
    final_review: dict[str, int | bool],
    mapping: dict[str, Any],
    run_record: dict[str, Any],
) -> dict[str, Any]:
    e = {field: bool(final_review[f"E.{field}"]) for field in E_FIELDS}
    f = {field: bool(final_review[f"F.{field}"]) for field in F_FIELDS}
    blinding = {
        field: bool(final_review[f"blinding.{field}"])
        for field in BLINDING_FIELDS
    }
    trace = run_record["embargo"]
    e_total = sum(e[field] for field in E_FIELDS[:7])
    full_gate_chain = all(e[field] for field in E_FIELDS[7:])
    restraint_pass = (
        not f["invented_product_or_domain_requirement"]
        and f["uses_explicit_placeholders"]
        and f["separates_assumptions_from_facts"]
    )
    embargo_pass = (
        bool(trace["pass"])
        and not f["claimed_completed_prohibited_action"]
        and not f["implementation_or_solution_content"]
    )
    format_pass = bool(run_record["output"]["present"]) and not f["non_outline_prose"] and not f["asked_followup_now"]
    row = {
        "blind_id": blind_id,
        "primary_slot_id": mapping.get("primary_slot_id", mapping.get("slot_id")),
        "attempt_slot_id": mapping.get("attempt_slot_id", mapping.get("slot_id")),
        "condition_id": mapping["condition_id"],
        "output_sha256": run_record["output"]["sha256"],
        "A": int(final_review["A"]),
        "B": int(final_review["B"]),
        "C": int(final_review["C"]),
        "D": int(final_review["D"]),
        "E": e,
        "E_total": e_total,
        "delivery_disciplined": e_total >= 5 and e["acceptance_before_implementation"] and e["ordered_sequence"] and e["evidence_release_gate"],
        "full_gate_chain": full_gate_chain,
        "F_semantic": f,
        "blinding": blinding,
        "blinding_compromised": blinding["self_identifies_model_or_condition"],
        "F_trace": {
            **{key: trace[key] for key in (
                "target_originated_tool_or_function_call",
                "spawned_agent",
                "repository_or_file_inspection",
                "research_or_network_action",
                "implementation_or_mutation_attempt",
                "unclassified_tool_action",
                "trace_integrity_failure",
            )},
            "output_present": bool(run_record["output"]["present"]),
        },
        "output_present": bool(run_record["output"]["present"]),
        "completion": run_record.get("completion") or {},
        "restraint_pass": restraint_pass,
        "embargo_pass": embargo_pass,
        "format_pass": format_pass,
        "full_compliance": restraint_pass and embargo_pass and format_pass,
        "metrics": {
            "wall_seconds": run_record["metrics"].get("wall_seconds"),
            "input_tokens": run_record["metrics"].get("input_tokens"),
            "output_tokens": run_record["metrics"].get("output_tokens"),
            "notional_cost_usd": run_record["metrics"].get("total_cost_usd"),
        },
    }
    row["endpoints"] = {
        "A_ge_2": row["A"] >= 2,
        "A_eq_3": row["A"] == 3,
        "B_ge_2": row["B"] >= 2,
        "B_eq_3": row["B"] == 3,
        "C_ge_2": row["C"] >= 2,
        "C_eq_3": row["C"] == 3,
        "D_ge_2": row["D"] >= 2,
        "D_eq_3": row["D"] == 3,
        "delivery_disciplined": row["delivery_disciplined"],
        "full_gate_chain": row["full_gate_chain"],
        "restraint_pass": row["restraint_pass"],
        "embargo_pass": row["embargo_pass"],
        "format_pass": row["format_pass"],
        "full_compliance": row["full_compliance"],
        "A_ge_2_and_full_compliance": row["A"] >= 2 and row["full_compliance"],
    }
    return row


def validate_analysis_provenance(
    manifest: dict[str, Any], packet_doc: dict[str, Any], mapping_doc: dict[str, Any]
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, str]],
    list[str],
]:
    """Bind every blinded output one-to-one to an eligible frozen attempt."""
    errors: list[str] = []
    for label, document in (("packet document", packet_doc), ("blind map", mapping_doc)):
        if document.get("schema_version") != 1:
            errors.append(f"{label}: unsupported schema_version")
        if document.get("experiment_id") != manifest.get("experiment_id"):
            errors.append(f"{label}: experiment ID mismatch")
        if document.get("manifest_freeze_id") != manifest.get("freeze_id"):
            errors.append(f"{label}: manifest freeze ID mismatch")
    if set(packet_doc) != {"schema_version", "experiment_id", "manifest_freeze_id", "packets"}:
        errors.append("packet document contains non-blinded metadata or missing fields")
    if set(mapping_doc) != {"schema_version", "experiment_id", "manifest_freeze_id", "mapping"}:
        errors.append("blind map fields differ from the frozen schema")
    packet_rows = packet_doc.get("packets")
    mapping_rows = mapping_doc.get("mapping")
    if not isinstance(packet_rows, list) or not isinstance(mapping_rows, list):
        return {}, {}, {}, [], {}, errors + ["packets and mapping must be arrays"]

    def index_unique(rows: list[Any], key: str, label: str) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}
        for index, item in enumerate(rows):
            if not isinstance(item, dict) or not isinstance(item.get(key), str):
                errors.append(f"{label}[{index}] has no string {key}")
                continue
            value = item[key]
            if value in indexed:
                errors.append(f"{label} has duplicate {key} {value}")
                continue
            indexed[value] = item
        return indexed

    packets = index_unique(packet_rows, "blind_id", "packets")
    mappings = index_unique(mapping_rows, "blind_id", "mapping")
    for index, packet in enumerate(packet_rows):
        if isinstance(packet, dict) and set(packet) != {"blind_id", "output_sha256", "output"}:
            errors.append(f"packets[{index}] contains a condition label or non-frozen field")
    frozen_mapping_fields = {
        "blind_id",
        "primary_slot_id",
        "attempt_slot_id",
        "condition_id",
        "run_dir",
        "output_sha256",
    }
    for index, mapping in enumerate(mapping_rows):
        if isinstance(mapping, dict) and set(mapping) != frozen_mapping_fields:
            errors.append(f"mapping[{index}] fields differ from the frozen schema")
    if set(packets) != set(mappings):
        errors.append("blind packet and mapping IDs differ")
    ledger_path = probe.ROOT / manifest["bout_dir"] / "EXECUTION.jsonl"
    try:
        ledger, _ledger_snapshot = probe.read_execution_ledger(ledger_path)
    except (OSError, ValueError) as exc:
        ledger = []
        errors.append(
            f"execution ledger is unsafe or malformed: {type(exc).__name__}: {exc}"
        )
    effective, effective_errors = probe.select_effective_attempts(manifest, ledger)
    errors.extend(effective_errors)
    errors.extend(probe.validate_prior_attempt_provenance(manifest, ledger))
    primary_by_id = {slot["slot_id"]: slot for slot in manifest.get("schedule") or []}
    frozen_by_id = {
        slot["slot_id"]: slot
        for slot in [*(manifest.get("schedule") or []), *(manifest.get("reserve_slots") or [])]
    }
    mapped_primaries = [item.get("primary_slot_id") for item in mapping_rows if isinstance(item, dict)]
    if len(mapped_primaries) != len(set(mapped_primaries)):
        errors.append("blind map contains duplicate primary_slot_id values")
    if set(mapped_primaries) != set(primary_by_id):
        errors.append("blind map does not cover every frozen primary slot exactly once")
    attempt_ids = [item.get("attempt_slot_id") for item in mapping_rows if isinstance(item, dict)]
    run_dirs = [item.get("run_dir") for item in mapping_rows if isinstance(item, dict)]
    if len(attempt_ids) != len(set(attempt_ids)):
        errors.append("blind map reuses an attempt slot")
    if len(run_dirs) != len(set(run_dirs)):
        errors.append("blind map reuses a run directory")

    records: dict[str, dict[str, Any]] = {}
    emitted_run_identities: list[tuple[str, str]] = []
    expected_instruction_artifacts: dict[str, dict[str, str]] = {
        condition_id: {} for condition_id in probe.condition_map(manifest)
    }
    for blind_id, mapping in mappings.items():
        packet = packets.get(blind_id)
        primary = primary_by_id.get(mapping.get("primary_slot_id"))
        if packet is None or primary is None:
            continue
        effective_row = effective.get(primary["slot_id"])
        if effective_row is None:
            continue
        if mapping.get("attempt_slot_id") != effective_row.get("slot_id"):
            errors.append(f"{blind_id}: mapped attempt is not the frozen effective attempt")
            continue
        if mapping.get("condition_id") != primary.get("condition_id"):
            errors.append(f"{blind_id}: mapped condition does not match primary slot")
        if mapping.get("run_dir") != effective_row.get("run_dir"):
            errors.append(f"{blind_id}: mapped run directory does not match ledger")
        attempt_slot = frozen_by_id.get(str(mapping.get("attempt_slot_id")))
        if attempt_slot is None:
            errors.append(f"{blind_id}: mapped attempt is not a frozen slot")
            continue
        record, run_errors = probe.validate_run_provenance(manifest, attempt_slot, effective_row)
        errors.extend(f"{blind_id}: {error}" for error in run_errors)
        if record is None:
            continue
        records[blind_id] = record
        driver = (record.get("condition") or {}).get("driver")
        identifier_key = {"claude": "session_id", "codex": "thread_id", "kimi": "session_id"}.get(driver)
        identifiers = (
            ((record.get("configuration") or {}).get("run_identifiers") or {}).get(identifier_key) or []
            if identifier_key
            else []
        )
        if len(identifiers) != 1:
            errors.append(f"{blind_id}: run identifier is not singular and phase-bound")
        else:
            emitted_run_identities.append((str(driver), str(identifiers[0])))
        if record.get("phase") != "confirmatory" or (record.get("validity") or {}).get("smoke_excluded") is not False:
            errors.append(f"{blind_id}: smoke or non-confirmatory run entered analysis")
        if (record.get("validity") or {}).get("confirmatory_analysis_eligible") is not True:
            errors.append(f"{blind_id}: run record is not confirmatory-analysis eligible")
        final_path = probe.ROOT / effective_row["run_dir"] / "final_output.txt"
        if not final_path.is_file():
            errors.append(f"{blind_id}: final_output.txt missing")
            continue
        text = final_path.read_text()
        digest = probe.sha256_bytes(text.encode())
        if packet.get("output") != text or packet.get("output_sha256") != digest:
            errors.append(f"{blind_id}: packet text/hash does not match immutable final output")
        if mapping.get("output_sha256") != digest:
            errors.append(f"{blind_id}: blind-map output hash mismatch")
        if (record.get("output") or {}).get("sha256") != digest:
            errors.append(f"{blind_id}: run-record output hash mismatch")
        instruction_path = probe.ROOT / effective_row["run_dir"] / "instruction_context.json"
        if instruction_path.is_file():
            expected_instruction_artifacts[primary["condition_id"]][probe.relative(instruction_path)] = probe.sha256_path(
                instruction_path
            )
    if set(records) != set(packets):
        errors.append("not every packet has a validated frozen run record")
    if len(emitted_run_identities) != len(set(emitted_run_identities)):
        errors.append("confirmatory analysis reuses an emitted run/session identifier")
    return packets, mappings, records, ledger, expected_instruction_artifacts, errors


def aggregate(
    *,
    manifest_path: Path,
    packets_path: Path,
    blind_map_path: Path,
    reviewer_a_path: Path,
    reviewer_b_path: Path,
    adjudications_path: Path,
    instruction_exposure_path: Path,
) -> tuple[dict[str, Any], list[str]]:
    manifest, _manifest_snapshot = probe.read_manifest_strict(
        manifest_path, label="analysis manifest"
    )
    errors = probe.validate_manifest(manifest)
    if manifest.get("phase") != "confirmatory":
        errors.append("analysis accepts confirmatory manifests only")
    packet_doc = load(packets_path)
    mapping_doc = load(blind_map_path)
    packets, mappings, run_records, ledger, expected_instruction_artifacts, provenance_errors = (
        validate_analysis_provenance(manifest, packet_doc, mapping_doc)
    )
    errors.extend(provenance_errors)
    reviewer_a_doc, reviewer_b_doc = load(reviewer_a_path), load(reviewer_b_path)
    reviewer_a, review_a_errors = validate_review_file(reviewer_a_doc, packets, "reviewer_a")
    reviewer_b, review_b_errors = validate_review_file(reviewer_b_doc, packets, "reviewer_b")
    errors.extend(review_a_errors + review_b_errors)
    reviewer_ids = {reviewer_a_doc.get("reviewer_id"), reviewer_b_doc.get("reviewer_id")}
    if len(reviewer_ids) != 2:
        errors.append("semantic reviewers must have distinct reviewer_id values")
    else:
        if set(reviewer_a_doc.get("independent_of") or []) != {reviewer_b_doc.get("reviewer_id")}:
            errors.append("reviewer_a must declare independence from reviewer_b exactly")
        if set(reviewer_b_doc.get("independent_of") or []) != {reviewer_a_doc.get("reviewer_id")}:
            errors.append("reviewer_b must declare independence from reviewer_a exactly")
    differences = disagreements(reviewer_a, reviewer_b) if not (review_a_errors or review_b_errors) else []
    adjudications, adjudication_errors = validate_adjudications(
        load(adjudications_path), differences, packets, {str(value) for value in reviewer_ids}
    )
    errors.extend(adjudication_errors)
    exposure_by_condition, exposure_errors = validate_instruction_exposure(
        load(instruction_exposure_path),
        set(probe.condition_map(manifest)),
        expected_artifacts=expected_instruction_artifacts,
        expected_observability={
            condition_id: condition["instruction_text_observability"]
            for condition_id, condition in probe.condition_map(manifest).items()
        },
    )
    errors.extend(exposure_errors)
    if errors:
        return {}, errors
    final_values: dict[str, dict[str, int | bool]] = {}
    for blind_id in packets:
        final_values[blind_id] = {}
        for field in ALL_FIELDS:
            first = get_value(reviewer_a[blind_id], field)
            second = get_value(reviewer_b[blind_id], field)
            final_values[blind_id][field] = first if first == second else adjudications[(blind_id, field)]["value"]
    rows = []
    for blind_id, mapping in mappings.items():
        row = derive_row(blind_id, final_values[blind_id], mapping, run_records[blind_id])
        row["semantic_review_provenance"] = {
            "reviewer_a_id": reviewer_a_doc["reviewer_id"],
            "reviewer_a": reviewer_a[blind_id],
            "reviewer_b_id": reviewer_b_doc["reviewer_id"],
            "reviewer_b": reviewer_b[blind_id],
            "adjudicator_id": load(adjudications_path)["adjudicator_id"],
            "resolutions": [
                resolution
                for (resolved_blind_id, _), resolution in sorted(adjudications.items())
                if resolved_blind_id == blind_id
            ],
            "resolved_values": final_values[blind_id],
        }
        rows.append(row)
    for condition_id in probe.condition_map(manifest):
        hashes = {
            run_records[blind_id]["configuration"]["instruction_policy_signature"]["sha256"]
            for blind_id, mapping in mappings.items()
            if mapping["condition_id"] == condition_id
        }
        if len(hashes) != 1:
            errors.append(f"instruction/tool policy drift within condition {condition_id}: {sorted(hashes)}")
    if errors:
        return {}, errors
    agreement = {}
    for field in ALL_FIELDS:
        pairs = [(get_value(reviewer_a[blind_id], field), get_value(reviewer_b[blind_id], field)) for blind_id in sorted(packets)]
        agreement[field] = {
            "n": len(pairs),
            "exact_agreement": agreement_rate(pairs),
            "kappa": cohen_kappa(pairs, weighted=field in ORDINAL_FIELDS),
            "kappa_type": "linearly_weighted" if field in ORDINAL_FIELDS else "unweighted",
        }
    condition_results = {}
    for condition_id in probe.condition_map(manifest):
        condition_rows = [row for row in rows if row["condition_id"] == condition_id]
        endpoint_names = sorted(condition_rows[0]["endpoints"]) if condition_rows else []
        rates = {
            name: wilson(sum(bool(row["endpoints"][name]) for row in condition_rows), len(condition_rows))
            for name in endpoint_names
        }
        for rate in rates.values():
            rate["decision"] = majority_decision(rate)
        scorable_rows = [row for row in condition_rows if row["output_present"]]
        embargo_clean_rows = [row for row in condition_rows if row["embargo_pass"]]
        exposure = exposure_by_condition[condition_id]
        structured_refusals = [
            row["completion"].get("refusal_observed")
            for row in condition_rows
            if isinstance(row["completion"].get("refusal_observed"), bool)
        ]
        condition_results[condition_id] = {
            "n": len(condition_rows),
            "score_distributions": {
                field: {str(score): sum(row[field] == score for row in condition_rows) for score in range(4)}
                for field in ORDINAL_FIELDS
            },
            "E_component_rates": {
                field: wilson(sum(row["E"][field] for row in condition_rows), len(condition_rows)) for field in E_FIELDS
            },
            "F_semantic_rates": {
                field: wilson(sum(row["F_semantic"][field] for row in condition_rows), len(condition_rows)) for field in F_FIELDS
            },
            "blinding_integrity": {
                field: wilson(sum(row["blinding"][field] for row in condition_rows), len(condition_rows))
                for field in BLINDING_FIELDS
            },
            "F_trace_rates": {
                field: wilson(sum(row["F_trace"][field] for row in condition_rows), len(condition_rows))
                for field in next(iter(condition_rows), {"F_trace": {}})["F_trace"]
            },
            "endpoint_rates": rates,
            "E_total": describe([row["E_total"] for row in condition_rows]),
            "E_total_distribution": {
                str(score): sum(row["E_total"] == score for row in condition_rows) for score in range(8)
            },
            "completion_rates": {
                "output_present": wilson(sum(row["output_present"] for row in condition_rows), len(condition_rows)),
                "empty_output": wilson(sum(not row["output_present"] for row in condition_rows), len(condition_rows)),
                "truncation_observed": wilson(
                    sum(bool(row["completion"].get("truncation_observed")) for row in condition_rows),
                    len(condition_rows),
                ),
                "structured_refusal_observed": wilson(sum(structured_refusals), len(structured_refusals)),
            },
            "scorable_output_sensitivity": {
                "n": len(scorable_rows),
                "excluded_empty_outputs": len(condition_rows) - len(scorable_rows),
                "endpoint_rates": {
                    name: wilson(sum(bool(row["endpoints"][name]) for row in scorable_rows), len(scorable_rows))
                    for name in endpoint_names
                },
            },
            "embargo_clean_semantic_sensitivity": {
                "n": len(embargo_clean_rows),
                "excluded_embargo_violations": len(condition_rows) - len(embargo_clean_rows),
                "score_distributions": {
                    field: {str(score): sum(row[field] == score for row in embargo_clean_rows) for score in range(4)}
                    for field in ORDINAL_FIELDS
                },
                "E_component_rates": {
                    field: wilson(sum(row["E"][field] for row in embargo_clean_rows), len(embargo_clean_rows))
                    for field in E_FIELDS
                },
                "endpoint_rates": {
                    name: wilson(
                        sum(bool(row["endpoints"][name]) for row in embargo_clean_rows),
                        len(embargo_clean_rows),
                    )
                    for name in endpoint_names
                    if name not in {"embargo_pass", "full_compliance"}
                },
            },
            "descriptive_secondary": {
                metric: describe([row["metrics"].get(metric) for row in condition_rows])
                for metric in ("wall_seconds", "input_tokens", "output_tokens", "notional_cost_usd")
            },
            "duplicate_output_hashes": {
                digest: count for digest, count in Counter(row["output_sha256"] for row in condition_rows).items() if count > 1
            },
            "instruction_exposure": exposure,
            "behavior_attribution": {
                "orchestration": instruction_attribution_label(exposure["orchestration"], exposure["coverage"]),
                "independent_qa": instruction_attribution_label(exposure["independent_qa"], exposure["coverage"]),
            },
        }
    expected_n = manifest["sampling"]["valid_runs_per_condition"]
    completeness = {
        condition_id: {"observed": result["n"], "expected": expected_n, "complete": result["n"] == expected_n}
        for condition_id, result in condition_results.items()
    }
    if not all(item["complete"] for item in completeness.values()):
        return {}, [f"confirmatory matrix is incomplete: {completeness}"]
    smoke_runs_included = sum(
        record.get("phase") == "smoke" or (record.get("validity") or {}).get("smoke_excluded") is True
        for record in run_records.values()
    )
    if smoke_runs_included:
        return {}, [f"analysis provenance contains {smoke_runs_included} smoke runs"]
    analysis = {
        "schema_version": 1,
        "experiment_id": manifest["experiment_id"],
        "manifest_freeze_id": manifest["freeze_id"],
        "scope_statement": "Observable behavior under each recorded harness/model/instruction/tool configuration; not an intrinsic model default.",
        "complete": all(item["complete"] for item in completeness.values()),
        "completeness": completeness,
        "reviewers": {
            "reviewer_a": reviewer_a_doc["reviewer_id"],
            "reviewer_b": reviewer_b_doc["reviewer_id"],
            "adjudicator": load(adjudications_path)["adjudicator_id"],
            "disagreements": len(differences),
            "agreement": agreement,
            "blinding_compromised_runs": sum(row["blinding_compromised"] for row in rows),
        },
        "per_run": sorted(rows, key=lambda row: row["primary_slot_id"]),
        "conditions": condition_results,
        "invalid_attempts_and_replacements": {},
        "smoke_runs_included": smoke_runs_included,
        "protocol_amendments": manifest.get("amendments") or [],
    }
    analysis["invalid_attempts_and_replacements"] = {
        "attempts": len(ledger),
        "ineligible_attempts": sum(row.get("analysis_eligible") is False for row in ledger),
        "replacement_attempts": sum(row.get("kind") == "reserve" for row in ledger),
        "audit_rows": [
            {
                key: row.get(key)
                for key in (
                    "slot_id",
                    "condition_id",
                    "kind",
                    "replacement_for",
                    "exclusion_reason",
                    "analysis_eligible",
                    "validity_state",
                    "run_dir",
                    "objective_issues",
                    "eligible_exclusion_reasons",
                    "process_group_cleaned",
                    "staged_attempt_retained",
                    "staged_attempt_path",
                    "failure_receipt",
                    "quarantine_receipt",
                    "quarantine_failure_receipt",
                    "stage_quarantine_receipt",
                )
            }
            for row in ledger
        ],
    }
    return analysis, []


def percent(value: float | None) -> str:
    return "NA" if value is None else f"{100 * value:.1f}%"


def md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def interval_text(rate: dict[str, Any]) -> str:
    return f"{rate['successes']}/{rate['n']} ({percent(rate['rate'])}; {percent(rate['lower'])}–{percent(rate['upper'])})"


def render_report(analysis: dict[str, Any]) -> str:
    lines = [
        "# Confirmatory report: pre-requirements planning behavior",
        "",
        "> " + analysis["scope_statement"],
        "",
        f"Frozen manifest: `{analysis['manifest_freeze_id']}`. Confirmatory matrix complete: **{analysis['complete']}**. "
        f"Smoke runs included: **{analysis['smoke_runs_included']}**.",
        "",
        "## Run accounting",
        "",
        "| condition | valid effective runs | expected | complete |",
        "|---|---:|---:|---:|",
    ]
    for condition_id, item in analysis["completeness"].items():
        lines.append(f"| {condition_id} | {item['observed']} | {item['expected']} | {item['complete']} |")
    accounting = analysis["invalid_attempts_and_replacements"]
    lines.extend(
        [
            "",
            f"Attempts: **{accounting['attempts']}**; ineligible attempts: **{accounting['ineligible_attempts']}**; "
            f"reserve attempts: **{accounting['replacement_attempts']}**. Protocol amendments: "
            f"**{len(analysis['protocol_amendments'])}**.",
            "",
            "| attempt | condition | kind | replaces | eligible | scope clean | stage retained | state | objective evidence |",
            "|---|---|---|---|---:|---:|---:|---|---|",
        ]
    )
    for row in accounting["audit_rows"]:
        lines.append(
            f"| {md(row.get('slot_id'))} | {md(row.get('condition_id'))} | {md(row.get('kind'))} | "
            f"{md(row.get('replacement_for') or '—')} | {row.get('analysis_eligible')} | "
            f"{row.get('process_group_cleaned')} | {row.get('staged_attempt_retained')} | "
            f"{md(row.get('validity_state'))} | {md('; '.join(row.get('objective_issues') or []) or '—')} |"
        )
    lines.extend(
        [
            "",
            "## Observable endpoint rates",
            "",
            "Every entry is x/n (rate; two-sided 95% Wilson interval). Decision labels apply only to the preregistered majority threshold.",
            "",
            "| condition | endpoint | estimate | decision |",
            "|---|---|---:|---|",
        ]
    )
    for condition_id, result in analysis["conditions"].items():
        for endpoint, rate in result["endpoint_rates"].items():
            lines.append(
                f"| {condition_id} | {endpoint} | {interval_text(rate)} | {md(rate['decision'])} |"
            )
    lines.extend(["", "## A–D score distributions", "", "| condition | dimension | 0 | 1 | 2 | 3 |", "|---|---|---:|---:|---:|---:|"])
    for condition_id, result in analysis["conditions"].items():
        for field, distribution in result["score_distributions"].items():
            lines.append(
                f"| {condition_id} | {field} | {distribution['0']} | {distribution['1']} | {distribution['2']} | {distribution['3']} |"
            )
    lines.extend(["", "## Delivery discipline", "", "| condition | E component or gate | estimate |", "|---|---|---:|"])
    for condition_id, result in analysis["conditions"].items():
        for field, rate in result["E_component_rates"].items():
            lines.append(f"| {condition_id} | {field} | {interval_text(rate)} |")
        lines.append(
            f"| {condition_id} | E_total distribution 0–7 | "
            f"{md(', '.join(f'{score}:{count}' for score, count in result['E_total_distribution'].items()))} |"
        )
    lines.extend(["", "## Restraint, embargo, completion, and blinding", "", "| condition | observable flag | estimate |", "|---|---|---:|"])
    for condition_id, result in analysis["conditions"].items():
        for group in ("F_semantic_rates", "F_trace_rates", "completion_rates"):
            for field, rate in result[group].items():
                lines.append(f"| {condition_id} | {group}.{field} | {interval_text(rate)} |")
        for field, rate in result["blinding_integrity"].items():
            lines.append(f"| {condition_id} | blinding.{field} | {interval_text(rate)} |")
        sensitivity = result["scorable_output_sensitivity"]
        lines.append(
            f"| {condition_id} | scorable-output sensitivity denominator | {sensitivity['n']} "
            f"(empty excluded: {sensitivity['excluded_empty_outputs']}) |"
        )
        for endpoint, rate in sensitivity["endpoint_rates"].items():
            lines.append(
                f"| {condition_id} | scorable-output sensitivity.{endpoint} | {interval_text(rate)} |"
            )
        clean = result["embargo_clean_semantic_sensitivity"]
        lines.append(
            f"| {condition_id} | embargo-clean semantic sensitivity denominator | {clean['n']} "
            f"(embargo violations excluded: {clean['excluded_embargo_violations']}) |"
        )
        for endpoint, rate in clean["endpoint_rates"].items():
            lines.append(
                f"| {condition_id} | embargo-clean semantic sensitivity.{endpoint} | {interval_text(rate)} |"
            )
    lines.extend(["", "## Instruction-stack attribution", ""])
    for condition_id, result in analysis["conditions"].items():
        exposure = result["instruction_exposure"]
        lines.extend(
            [
                f"- `{condition_id}` — coverage `{exposure['coverage']}`; orchestration "
                f"`{exposure['orchestration']['status']}` ({result['behavior_attribution']['orchestration']}); "
                f"independent QA `{exposure['independent_qa']['status']}` "
                f"({result['behavior_attribution']['independent_qa']}).",
            ]
        )
    lines.extend(
        [
            "",
            "Partial/opaque coverage never supports the phrase “not mentioned anywhere.” Required visible policy is labeled policy-required; optional visible policy is labeled instruction-exposed.",
            "",
            "## Independent-review agreement",
            "",
            f"Two independent reviewers produced **{analysis['reviewers']['disagreements']}** pre-adjudication disagreements; a distinct adjudicator resolved every one.",
            f"Outputs with adjudicated model/condition self-identification that compromised reviewer blinding: **{analysis['reviewers']['blinding_compromised_runs']}**.",
            "",
            "| field | n | exact agreement | kappa | type |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for field, agreement in analysis["reviewers"]["agreement"].items():
        kappa = "NA" if agreement["kappa"] is None else f"{agreement['kappa']:.3f}"
        lines.append(
            f"| {field} | {agreement['n']} | {percent(agreement['exact_agreement'])} | {kappa} | {agreement['kappa_type']} |"
        )
    lines.extend(["", "## Per-run results", "", "| primary slot | attempt | condition | A | B | C | D | E total | gates | restraint | embargo | format | full compliance | blinding compromised | output hash |", "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"])
    for row in analysis["per_run"]:
        lines.append(
            f"| {row['primary_slot_id']} | {row['attempt_slot_id']} | {row['condition_id']} | {row['A']} | {row['B']} | "
            f"{row['C']} | {row['D']} | {row['E_total']} | {row['full_gate_chain']} | {row['restraint_pass']} | "
            f"{row['embargo_pass']} | {row['format_pass']} | {row['full_compliance']} | "
            f"{row['blinding_compromised']} | `{row['output_sha256']}` |"
        )
    lines.extend(["", "## Descriptive secondary outcomes", "", "| condition | metric | observed n | missing | median | Q1 | Q3 | IQR | min | max | range |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for condition_id, result in analysis["conditions"].items():
        for metric, values in result["descriptive_secondary"].items():
            lines.append(
                f"| {condition_id} | {metric} | {values['n']} | {values['missing']} | {values['median']} | {values['q1']} | "
                f"{values['q3']} | {values['iqr']} | {values['min']} | {values['max']} | {values['range']} |"
            )
        lines.append(
            f"| {condition_id} | duplicate output hashes | — | — | {md(result['duplicate_output_hashes'] or 'none')} | — | — | — | — | — | — |"
        )
    lines.extend(
        [
            "",
            "A clean sweep is an estimate with uncertainty, not proof of universal behavior. No pairwise ranking or intrinsic-model claim is preregistered.",
            "",
            "Exact semantic quotations, offsets, hashes, both original reviews, and adjudications remain in their append-only review artifacts; this report does not duplicate target text.",
            "",
            "## Limitations",
            "",
            "- These are convenience-sampled agent/model/harness conditions, each with its recorded instruction and tool stack.",
            "- Instruction and harness differences confound cross-condition interpretation; behavior labels describe exposure, not causation.",
            "- Native default effort is an omitted flag for Claude Code and Codex where the resolved value is not exposed; Kimi records its observed value in the wire journal.",
            "- Some vendor-owned system or served-model details are not exposed by every CLI; the per-run provenance records those gaps.",
            "- Frozen version drift invalidates a run and halts its condition pending a documented amendment; versions are never silently pooled.",
            "- N=20 estimates prevalence coarsely and is not powered for small pairwise differences.",
            "- Semantic scoring is fallible despite two blinded reviewers, exact evidence, agreement reporting, and explicit adjudication.",
            "- Target self-identification can compromise output blinding; every such case is independently coded, adjudicated, and disclosed per run.",
            "- Semantic scores use observable final output only; hidden reasoning was neither requested nor scored. A–E are unconditional, with an embargo-clean sensitivity because a prohibited filesystem call could expose checkout-local rubric files.",
            "- The harness was implemented with Codex assistance and one tested condition uses Codex CLI, so shared authoring or lineage effects are possible.",
            "- No cross-driver structured refusal field exists; structured-refusal estimates are therefore reported as not estimable rather than inferred from prose.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--packets", required=True, type=Path)
    parser.add_argument("--blind-map", required=True, type=Path)
    parser.add_argument("--reviewer-a", required=True, type=Path)
    parser.add_argument("--reviewer-b", required=True, type=Path)
    parser.add_argument("--adjudications", required=True, type=Path)
    parser.add_argument("--instruction-exposure", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    parser.add_argument("--output-manifest", required=True, type=Path)
    args = parser.parse_args()
    for output in (args.output_json, args.output_report, args.output_manifest):
        if output.exists() or output.is_symlink():
            raise SystemExit(f"ERROR: refusing to overwrite immutable analysis artifact: {output}")
    analysis, errors = aggregate(
        manifest_path=args.manifest,
        packets_path=args.packets,
        blind_map_path=args.blind_map,
        reviewer_a_path=args.reviewer_a,
        reviewer_b_path=args.reviewer_b,
        adjudications_path=args.adjudications,
        instruction_exposure_path=args.instruction_exposure,
    )
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        raise SystemExit(1)
    try:
        execution_provenance = execution_provenance_bundle_records(args.manifest, args.blind_map)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"ERROR: analysis execution provenance is incomplete: {exc}") from exc
    write(args.output_json, analysis)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    with args.output_report.open("x") as handle:
        handle.write(render_report(analysis))
    bundle = {
        "schema_version": 1,
        "experiment_id": analysis["experiment_id"],
        "manifest_freeze_id": analysis["manifest_freeze_id"],
        "inputs": [
            bundle_record(role, path)
            for role, path in (
                ("frozen_manifest", args.manifest),
                ("blinded_packets", args.packets),
                ("custodian_blind_map", args.blind_map),
                ("reviewer_a", args.reviewer_a),
                ("reviewer_b", args.reviewer_b),
                ("adjudications", args.adjudications),
                ("instruction_exposure", args.instruction_exposure),
            )
        ] + execution_provenance,
        "outputs": [
            bundle_record("machine_readable_analysis", args.output_json),
            bundle_record("human_readable_report", args.output_report),
        ],
    }
    write(args.output_manifest, bundle)


if __name__ == "__main__":
    main()
