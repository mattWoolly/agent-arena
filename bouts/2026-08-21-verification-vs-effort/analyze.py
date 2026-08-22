#!/usr/bin/env python3
"""Analyze the pre-registered source-audit prompt-by-effort bout."""
from collections import defaultdict
import json
import math
from pathlib import Path
import re
from statistics import mean

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL = "claude-sonnet-5"
CLI_VERSION = "2.1.239 (Claude Code)"
ITEM_IDS = (
    "q3_revenue",
    "q3_spend",
    "operating_surplus",
    "support_close_rate",
    "launch_date",
    "security_resolution_rate",
)
SMOKE_ITEM_IDS = (
    "q_revenue",
    "q_costs",
    "q_net",
    "margin",
    "net_adds",
    "close_rate",
    "mom_jun",
    "mom_jul",
)
BASIS_SOURCES = ("finance", "support", "delivery")
AUTH_EXPECTED = {
    "loggedIn": True,
    "authMethod": "claude.ai",
    "apiProvider": "firstParty",
    "apiKeySource": None,
    "subscriptionType": "max",
}
EFFORT_DIRS = {
    "low": ROOT / "bouts" / "2026-08-21-verification-vs-effort-low",
    "xhigh": ROOT / "bouts" / "2026-08-21-verification-vs-effort-xhigh",
}
TASKS = {
    "base": "16-source-audit",
    "verify": "16-source-audit-verify",
}
SMOKE_CASES = [
    ("base", "low", "15-rollup", "2026-08-21-verification-vs-effort-smoke-low"),
    ("verify", "low", "15-rollup-verify", "2026-08-21-verification-vs-effort-smoke-low"),
    ("base", "xhigh", "15-rollup", "2026-08-21-verification-vs-effort-smoke-xhigh"),
    ("verify", "xhigh", "15-rollup-verify", "2026-08-21-verification-vs-effort-smoke-xhigh"),
]


def wilson(successes, total, z=1.959963984540054):
    if total == 0:
        return [None, None]
    p = successes / total
    den = 1 + z * z / total
    center = (p + z * z / (2 * total)) / den
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / den
    return [center - half, center + half]


def parse_grade(path, kind):
    items = []
    bases = []
    controls = []
    flags = []
    scores = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if line.startswith("ITEM ") and len(parts) >= 3:
            items.append({"id": parts[1], "status": parts[2]})
        elif line.startswith("BASIS ") and len(parts) == 3:
            bases.append((parts[1], parts[2]))
        elif line.startswith("CONTROL ") and len(parts) == 3:
            controls.append((parts[1], parts[2]))
        elif line.startswith("FLAG ") and len(parts) == 3:
            flags.append((parts[1], parts[2]))
        elif line.startswith("SCORE:") and len(parts) == 2:
            scores.append(parts[1])

    expected_ids = ITEM_IDS if kind == "confirmation" else SMOKE_ITEM_IDS
    if len(items) != len(expected_ids) or sorted(i["id"] for i in items) != sorted(expected_ids):
        raise SystemExit(f"invalid ITEM set in {path}")
    if any(i["status"] not in {"OK", "WRONG", "MISSING"} for i in items):
        raise SystemExit(f"invalid ITEM status in {path}")
    if len(scores) != 1 or not re.fullmatch(r"\d+/\d+", scores[0]):
        raise SystemExit(f"invalid SCORE set in {path}")

    if kind == "confirmation":
        if (len(bases) != 3 or sorted(source for source, _ in bases) != sorted(BASIS_SOURCES)
                or any(value not in {"detail", "stated", "other"} for _, value in bases)):
            raise SystemExit(f"invalid BASIS set in {path}")
        if controls != [("security", "correct")] and controls != [("security", "wrong")]:
            raise SystemExit(f"invalid CONTROL set in {path}")
        if flags:
            raise SystemExit(f"unexpected FLAG in {path}")
    else:
        if bases or controls or flags not in [[("discrepancy", "yes")], [("discrepancy", "no")]]:
            raise SystemExit(f"invalid smoke grade annotations in {path}")

    return {
        "items": items,
        "bases": dict(bases),
        "controls": dict(controls),
        "flags": dict(flags),
        "score": scores[0],
    }


def is_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def read_grade_exit(path):
    value = path.read_text().strip()
    if not re.fullmatch(r"\d{1,3}", value) or int(value) > 255:
        raise SystemExit(f"invalid grade_exit in {path.parent}")
    return int(value)


def read_artifacts(run_dir, expected_effort, kind):
    required = [
        "auth_status.json",
        "grade.txt",
        "grade_exit",
        "metrics.json",
        "peek_check",
        "run_env.json",
    ]
    missing = [name for name in required if not (run_dir / name).is_file()]
    if missing:
        raise SystemExit(f"missing {missing} in {run_dir}")

    grade = parse_grade(run_dir / "grade.txt", kind)
    grade_exit = read_grade_exit(run_dir / "grade_exit")
    metrics = json.loads((run_dir / "metrics.json").read_text())
    run_env = json.loads((run_dir / "run_env.json").read_text())
    auth = json.loads((run_dir / "auth_status.json").read_text())
    telemetry_fields = ("total_cost_usd", "output_tokens", "num_turns", "wall_seconds")
    invalid = [field for field in telemetry_fields if not is_number(metrics.get(field))]
    if invalid:
        raise SystemExit(f"invalid telemetry {invalid} in {run_dir}")

    grade_pass = grade_exit == 0
    clean = (run_dir / "peek_check").read_text().strip() == "clean"
    served_ok = (metrics.get("served_model") == MODEL
                 and metrics.get("served_model_leak") is False)
    effort_ok = run_env.get("effort") == expected_effort
    auth_ok = auth == AUTH_EXPECTED
    runtime_ok = (
        metrics.get("agent_exit") == 0
        and metrics.get("is_error") is False
        and run_env.get("base_url") == "https://api.anthropic.com"
        and run_env.get("proxy_upstream") == "none"
        and run_env.get("model_env") == "none"
        and run_env.get("setting_sources") == "project"
        and run_env.get("max_turns") == 60
        and run_env.get("timeout_s") == 1500
        and run_env.get("cli_version") == CLI_VERSION
    )
    return {
        "grade_pass": grade_pass,
        "score": grade["score"],
        "items": grade["items"],
        "bases": grade["bases"],
        "controls": grade["controls"],
        "flags": grade["flags"],
        "served_ok": served_ok,
        "effort_ok": effort_ok,
        "auth_ok": auth_ok,
        "runtime_ok": runtime_ok,
        "peek_clean": clean,
        "integrity_ok": served_ok and effort_ok and auth_ok and runtime_ok and clean,
        "cost_usd": metrics["total_cost_usd"],
        "cost_source": metrics.get("cost_source", "cli-reported"),
        "output_tokens": metrics["output_tokens"],
        "turns": metrics["num_turns"],
        "execution_seconds": metrics["wall_seconds"],
    }


def load_runs():
    runs = []
    for effort, bout in EFFORT_DIRS.items():
        for prompt, task in TASKS.items():
            model_dir = bout / task / MODEL
            for repeat in range(1, 11):
                run_dir = model_dir / f"run-{repeat}"
                rec = read_artifacts(run_dir, effort, "confirmation")
                all_items = all(item["status"] == "OK" for item in rec["items"])
                all_detail = all(rec["bases"].get(name) == "detail" for name in BASIS_SOURCES)
                security_correct = rec["controls"].get("security") == "correct"
                rec.update({
                    "effort": effort,
                    "prompt": prompt,
                    "task": task,
                    "model": MODEL,
                    "repeat": repeat,
                    "all_items_correct": all_items,
                    "all_detail": all_detail,
                    "security_correct": security_correct,
                    "audit_success": (rec["grade_pass"] and all_items and all_detail
                                      and security_correct),
                })
                rec.pop("items")
                rec.pop("flags")
                runs.append(rec)
    return runs


def load_smokes():
    smokes = []
    for prompt, effort, task, bout_name in SMOKE_CASES:
        run_dir = ROOT / "bouts" / bout_name / task / MODEL / "run-1"
        rec = read_artifacts(run_dir, effort, "smoke")
        rec.update({"prompt": prompt, "effort": effort, "task": task,
                    "model": MODEL, "run": "smoke"})
        rec.pop("items")
        rec.pop("bases")
        rec.pop("controls")
        smokes.append(rec)
    return smokes


def safe_mean(values):
    values = [v for v in values if is_number(v)]
    return mean(values) if values else None


def summarize(runs):
    cells = {}
    grouped = defaultdict(list)
    for run in runs:
        grouped[(run["prompt"], run["effort"])].append(run)
    for (prompt, effort), rows in sorted(grouped.items()):
        successes = sum(row["audit_success"] for row in rows)
        detail_total = len(rows) * len(BASIS_SOURCES)
        detail_hits = sum(
            row["bases"].get(name) == "detail"
            for row in rows for name in BASIS_SOURCES
        )
        cells[f"{prompt}-{effort}"] = {
            "runs": len(rows),
            "audit_successes": successes,
            "audit_success_rate": successes / len(rows),
            "audit_success_wilson_95": wilson(successes, len(rows)),
            "detail_choices": detail_hits,
            "detail_opportunities": detail_total,
            "per_source_detail": {
                name: sum(row["bases"].get(name) == "detail" for row in rows)
                for name in BASIS_SOURCES
            },
            "security_correct_runs": sum(row["security_correct"] for row in rows),
            "all_items_correct_runs": sum(row["all_items_correct"] for row in rows),
            "task_passes": sum(row["grade_pass"] for row in rows),
            "mean_cost_usd": safe_mean(row["cost_usd"] for row in rows),
            "mean_output_tokens": safe_mean(row["output_tokens"] for row in rows),
            "mean_turns": safe_mean(row["turns"] for row in rows),
            "mean_execution_seconds": safe_mean(row["execution_seconds"] for row in rows),
            "integrity_failures": sum(not row["integrity_ok"] for row in rows),
        }
    return cells


def pct(value):
    return f"{100 * value:.0f}%"


def money(value):
    return "n/a" if value is None else f"${value:.3f}"


def render(cells, smokes):
    vl = cells["verify-low"]
    bx = cells["base-xhigh"]
    bl = cells["base-low"]
    vx = cells["verify-xhigh"]
    h1 = (vl["audit_success_rate"] >= bx["audit_success_rate"]
          and vl["mean_cost_usd"] is not None and bx["mean_cost_usd"] is not None
          and vl["mean_cost_usd"] <= bx["mean_cost_usd"])
    prompt_gain = vl["audit_success_rate"] - bl["audit_success_rate"]
    effort_gain = bx["audit_success_rate"] - bl["audit_success_rate"]
    interaction = ((vx["audit_success_rate"] - bx["audit_success_rate"])
                   - (vl["audit_success_rate"] - bl["audit_success_rate"]))
    confirmation_integrity = sum(cell["integrity_failures"] for cell in cells.values())
    smoke_integrity = sum(not smoke["integrity_ok"] for smoke in smokes)
    integrity = confirmation_integrity + smoke_integrity
    smoke_acceptance = all(smoke["grade_pass"] for smoke in smokes)

    hypotheses = [
        ("H1 verification-low matches or beats base-xhigh at no higher cost", h1,
         f"{vl['audit_successes']}/10 at {money(vl['mean_cost_usd'])} mean vs {bx['audit_successes']}/10 at {money(bx['mean_cost_usd'])}"),
        ("H2 low-effort prompt gain is at least 40 points", prompt_gain >= .4,
         f"{prompt_gain * 100:+.0f} points"),
        ("H3 prompt gain exceeds effort gain", prompt_gain > effort_gain,
         f"prompt {prompt_gain * 100:+.0f} points; effort {effort_gain * 100:+.0f} points"),
        ("H4 verification clean-control accuracy is at least 9/10 per arm",
         vl["security_correct_runs"] >= 9 and vx["security_correct_runs"] >= 9,
         f"low {vl['security_correct_runs']}/10; xhigh {vx['security_correct_runs']}/10"),
        ("H5 all-run integrity", integrity == 0,
         f"{integrity}/44 integrity failures; smoke task acceptance {'4/4' if smoke_acceptance else 'below 4/4'}"),
    ]

    lines = [
        "# Analysis: verification prompt versus inference effort",
        "",
        "## Hypothesis scorecard",
        "",
        "| Hypothesis | Verdict | Evidence |",
        "|---|---|---|",
    ]
    for label, hit, evidence in sorted(hypotheses, key=lambda row: (row[1], row[0])):
        lines.append(f"| {label} | {'HIT' if hit else 'MISS'} | {evidence} |")
    lines.extend([
        "",
        "## Cell results",
        "",
        "| Prompt | Effort | Audit success | Detail choices | Security correct | Key figures correct | Mean cost | Mean output tokens | Mean turns | Mean execution time |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for key in ("base-low", "verify-low", "base-xhigh", "verify-xhigh"):
        cell = cells[key]
        prompt, effort = key.split("-", 1)
        lines.append(
            f"| {prompt} | {effort} | {cell['audit_successes']}/{cell['runs']} ({pct(cell['audit_success_rate'])}) | "
            f"{cell['detail_choices']}/{cell['detail_opportunities']} | {cell['security_correct_runs']}/{cell['runs']} | "
            f"{cell['all_items_correct_runs']}/{cell['runs']} | {money(cell['mean_cost_usd'])} | "
            f"{cell['mean_output_tokens']:.0f} | {cell['mean_turns']:.1f} | {cell['mean_execution_seconds']:.1f}s |"
        )
    lines.extend([
        "",
        "## Pre-registered contrasts",
        "",
        f"- Verification-low minus base-xhigh: {(vl['audit_success_rate'] - bx['audit_success_rate']) * 100:+.0f} percentage points.",
        f"- Verification-low minus base-low: {prompt_gain * 100:+.0f} percentage points.",
        f"- Base-xhigh minus base-low: {effort_gain * 100:+.0f} percentage points.",
        f"- Prompt-by-effort interaction: {interaction * 100:+.0f} percentage points.",
        "",
        "Wilson intervals, per-run records, per-source basis counts, and cost-source fields are in `analysis.json`.",
        "The 10 repeats in each cell estimate sampling variance on this fixed task, not broad task transfer.",
        "",
    ])
    return "\n".join(lines)


def main():
    runs = load_runs()
    smokes = load_smokes()
    cells = summarize(runs)
    payload = {"model": MODEL, "smokes": smokes, "runs": runs, "cells": cells}
    (HERE / "analysis.json").write_text(json.dumps(payload, indent=2) + "\n")
    (HERE / "ANALYSIS.md").write_text(render(cells, smokes))
    print(render(cells, smokes))


if __name__ == "__main__":
    main()
