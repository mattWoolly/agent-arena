#!/usr/bin/env python3
"""Analyze the pre-registered source-audit prompt-by-effort bout."""
from collections import defaultdict
import json
import math
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL = "claude-sonnet-5"
EFFORT_DIRS = {
    "low": ROOT / "bouts" / "2026-08-21-verification-vs-effort-low",
    "xhigh": ROOT / "bouts" / "2026-08-21-verification-vs-effort-xhigh",
}
TASKS = {
    "base": "16-source-audit",
    "verify": "16-source-audit-verify",
}


def wilson(successes, total, z=1.959963984540054):
    if total == 0:
        return [None, None]
    p = successes / total
    den = 1 + z * z / total
    center = (p + z * z / (2 * total)) / den
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / den
    return [center - half, center + half]


def parse_grade(path):
    items = []
    flags = {}
    false_flags = {}
    score = None
    for line in path.read_text().splitlines():
        parts = line.split()
        if line.startswith("ITEM ") and len(parts) >= 3:
            items.append({"id": parts[1], "status": parts[2]})
        elif line.startswith("FLAG ") and len(parts) == 3:
            flags[parts[1]] = parts[2]
        elif line.startswith("FALSE_FLAG ") and len(parts) == 3:
            false_flags[parts[1]] = parts[2]
        elif line.startswith("SCORE:"):
            score = parts[1]
    return items, flags, false_flags, score


def load_runs():
    runs = []
    for effort, bout in EFFORT_DIRS.items():
        for prompt, task in TASKS.items():
            model_dir = bout / task / MODEL
            for repeat in range(1, 11):
                run_dir = model_dir / f"run-{repeat}"
                required = ["grade.txt", "grade_exit", "metrics.json", "peek_check", "run_env.json"]
                missing = [name for name in required if not (run_dir / name).exists()]
                if missing:
                    raise SystemExit(f"missing {missing} in {run_dir}")
                items, flags, false_flags, score = parse_grade(run_dir / "grade.txt")
                metrics = json.loads((run_dir / "metrics.json").read_text())
                run_env = json.loads((run_dir / "run_env.json").read_text())
                grade_pass = (run_dir / "grade_exit").read_text().strip() == "0"
                clean = (run_dir / "peek_check").read_text().strip() == "clean"
                all_items = len(items) == 6 and all(item["status"] == "OK" for item in items)
                all_conflicts = all(flags.get(name) == "yes" for name in
                                    ("finance", "support", "delivery"))
                false_alarm = false_flags.get("security") == "yes"
                served_ok = (metrics.get("served_model") == MODEL
                             and not metrics.get("served_model_leak"))
                effort_ok = run_env.get("effort") == effort
                audit_success = (grade_pass and all_items and all_conflicts
                                 and not false_alarm)
                runs.append({
                    "effort": effort,
                    "prompt": prompt,
                    "task": task,
                    "model": MODEL,
                    "repeat": repeat,
                    "grade_pass": grade_pass,
                    "score": score,
                    "all_items_correct": all_items,
                    "flags": flags,
                    "false_flags": false_flags,
                    "audit_success": audit_success,
                    "served_ok": served_ok,
                    "effort_ok": effort_ok,
                    "peek_clean": clean,
                    "cost_usd": metrics.get("total_cost_usd"),
                    "cost_source": metrics.get("cost_source", "cli-reported"),
                    "output_tokens": metrics.get("output_tokens"),
                    "turns": metrics.get("num_turns"),
                    "execution_seconds": metrics.get("wall_seconds"),
                })
    return runs


def safe_mean(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return mean(values) if values else None


def summarize(runs):
    cells = {}
    grouped = defaultdict(list)
    for run in runs:
        grouped[(run["prompt"], run["effort"])].append(run)
    for (prompt, effort), rows in sorted(grouped.items()):
        successes = sum(row["audit_success"] for row in rows)
        conflict_total = len(rows) * 3
        conflict_hits = sum(
            row["flags"].get(name) == "yes"
            for row in rows for name in ("finance", "support", "delivery")
        )
        cells[f"{prompt}-{effort}"] = {
            "runs": len(rows),
            "audit_successes": successes,
            "audit_success_rate": successes / len(rows),
            "audit_success_wilson_95": wilson(successes, len(rows)),
            "conflict_flags": conflict_hits,
            "conflict_opportunities": conflict_total,
            "per_source_flags": {
                name: sum(row["flags"].get(name) == "yes" for row in rows)
                for name in ("finance", "support", "delivery")
            },
            "security_false_flags": sum(
                row["false_flags"].get("security") == "yes" for row in rows),
            "all_items_correct_runs": sum(row["all_items_correct"] for row in rows),
            "task_passes": sum(row["grade_pass"] for row in rows),
            "mean_cost_usd": safe_mean(row["cost_usd"] for row in rows),
            "mean_output_tokens": safe_mean(row["output_tokens"] for row in rows),
            "mean_turns": safe_mean(row["turns"] for row in rows),
            "mean_execution_seconds": safe_mean(row["execution_seconds"] for row in rows),
            "integrity_failures": sum(
                not (row["served_ok"] and row["effort_ok"] and row["peek_clean"])
                for row in rows),
        }
    return cells


def pct(value):
    return f"{100 * value:.0f}%"


def money(value):
    return "n/a" if value is None else f"${value:.3f}"


def render(cells):
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
    integrity = sum(cell["integrity_failures"] for cell in cells.values())

    lines = [
        "# Analysis: verification prompt versus inference effort",
        "",
        "## Hypothesis scorecard",
        "",
        "| Hypothesis | Verdict | Evidence |",
        "|---|---|---|",
        f"| H1 verification-low matches or beats base-xhigh at no higher cost | {'HIT' if h1 else 'MISS'} | {vl['audit_successes']}/10 at {money(vl['mean_cost_usd'])} mean vs {bx['audit_successes']}/10 at {money(bx['mean_cost_usd'])} |",
        f"| H2 low-effort prompt gain is at least 40 points | {'HIT' if prompt_gain >= .4 else 'MISS'} | {prompt_gain * 100:+.0f} points |",
        f"| H3 prompt gain exceeds effort gain | {'HIT' if prompt_gain > effort_gain else 'MISS'} | prompt {prompt_gain * 100:+.0f} points; effort {effort_gain * 100:+.0f} points |",
        f"| H4 verification false alarms at most 1/10 per arm | {'HIT' if vl['security_false_flags'] <= 1 and vx['security_false_flags'] <= 1 else 'MISS'} | low {vl['security_false_flags']}/10; xhigh {vx['security_false_flags']}/10 |",
        f"| H5 confirmation integrity | {'HIT' if integrity == 0 else 'MISS'} | {integrity}/40 integrity failures; smoke integrity reported separately |",
        "",
        "## Cell results",
        "",
        "| Prompt | Effort | Audit success | Conflict flags | False flags | Key figures correct | Mean cost | Mean output tokens | Mean turns | Mean execution time |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in ("base-low", "verify-low", "base-xhigh", "verify-xhigh"):
        cell = cells[key]
        prompt, effort = key.split("-", 1)
        lines.append(
            f"| {prompt} | {effort} | {cell['audit_successes']}/{cell['runs']} ({pct(cell['audit_success_rate'])}) | "
            f"{cell['conflict_flags']}/{cell['conflict_opportunities']} | {cell['security_false_flags']}/{cell['runs']} | "
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
        "Wilson intervals, per-run records, per-source counts, and cost-source fields are in `analysis.json`.",
        "The 10 repeats in each cell estimate sampling variance on this fixed task, not broad task transfer.",
        "",
    ])
    return "\n".join(lines)


def main():
    runs = load_runs()
    cells = summarize(runs)
    payload = {"model": MODEL, "runs": runs, "cells": cells}
    (HERE / "analysis.json").write_text(json.dumps(payload, indent=2) + "\n")
    (HERE / "ANALYSIS.md").write_text(render(cells))
    print(render(cells))


if __name__ == "__main__":
    main()
