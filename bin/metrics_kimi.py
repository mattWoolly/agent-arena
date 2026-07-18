#!/usr/bin/env python3
"""Extract run metrics from a Kimi Code run dir.

Two sources: transcript.jsonl (the CLI's stream-json: role-level messages,
used for turns and tool-call composition) and wire.jsonl (the session
journal copied by run-task-kimi.sh, whose usage.record events carry per-turn
inputOther / inputCacheRead / inputCacheCreation / output). Emits the same
metric keys as metrics.py so summarize.py merges drivers into one table.
Cost comes from env/prices.json under the "kimi-k3" key; cache-creation
tokens are billed at the full input rate (conservative: Moonshot's platform
reported zero cache-creation tokens in probing).
"""
import json
import sys
from collections import Counter
from pathlib import Path


def main(out_dir: str, label: str) -> None:
    out = Path(out_dir)
    metrics = {"model": label}

    for key, fname, conv in (("wall_seconds", "wall_seconds", float), ("agent_exit", "agent_exit", int)):
        try:
            metrics[key] = conv((out / fname).read_text().strip())
        except (OSError, ValueError):
            metrics[key] = None

    turns = 0
    tool_calls = Counter()
    tpath = out / "transcript.jsonl"
    if tpath.exists():
        for line in tpath.read_text().splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("role") == "assistant":
                turns += 1
                for tc in ev.get("tool_calls") or []:
                    tool_calls[(tc.get("function") or {}).get("name", "?")] += 1
                if ev.get("content") and not ev.get("tool_calls"):
                    metrics["final_message"] = str(ev["content"])[:4000]
    metrics["num_turns"] = turns
    metrics["assistant_messages"] = turns
    metrics["tool_calls"] = dict(tool_calls)
    metrics["tool_calls_total"] = sum(tool_calls.values())

    usage_records = []
    wpath = out / "wire.jsonl"
    if wpath.exists():
        for line in wpath.read_text().splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "usage.record" and ev.get("usageScope") == "turn":
                usage_records.append(ev.get("usage") or {})

    uncached = sum(u.get("inputOther") or 0 for u in usage_records)
    cached = sum(u.get("inputCacheRead") or 0 for u in usage_records)
    cwrite = sum(u.get("inputCacheCreation") or 0 for u in usage_records)
    outp = sum(u.get("output") or 0 for u in usage_records)
    metrics["input_tokens"] = uncached + cached + cwrite
    metrics["cache_read_tokens"] = cached
    metrics["output_tokens"] = outp

    ppath = Path(__file__).resolve().parent.parent / "env" / "prices.json"
    if ppath.exists() and usage_records:
        prices = json.loads(ppath.read_text()).get("kimi-k3")
        if prices:
            total = (
                (uncached + cwrite) * prices["input"]
                + cached * prices.get("cache_read", prices["input"])
                + outp * prices["output"]
            ) / 1e6
            metrics["total_cost_usd"] = round(total, 5)
            metrics["cost_source"] = f"computed:env/prices.json (wire.jsonl usage, {len(usage_records)} turn records)"

    epath = out / "run_env.json"
    if epath.exists():
        try:
            metrics["run_env"] = json.loads(epath.read_text())
        except json.JSONDecodeError:
            pass

    pk = out / "peek_check"
    if pk.exists():
        metrics["peek_check"] = pk.read_text().strip()

    ds = out / "workspace.diffstat"
    if ds.exists():
        lines = ds.read_text().strip().splitlines()
        metrics["diffstat"] = lines[-1].strip() if lines else ""

    ge = out / "grade_exit"
    metrics["grade_pass"] = ge.exists() and ge.read_text().strip() == "0"
    gt = out / "grade.txt"
    if gt.exists():
        for line in gt.read_text().splitlines():
            if line.startswith("SCORE:"):
                metrics["score"] = line.split("SCORE:", 1)[1].strip()

    json.dump(metrics, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
