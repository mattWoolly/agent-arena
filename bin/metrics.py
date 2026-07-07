#!/usr/bin/env python3
"""Extract run metrics from a run output dir: transcript.jsonl + result.json."""
import json
import sys
from collections import Counter
from pathlib import Path


def main(out_dir: str, model: str) -> None:
    out = Path(out_dir)
    metrics = {"model": model}

    try:
        metrics["wall_seconds"] = float((out / "wall_seconds").read_text().strip())
    except (OSError, ValueError):
        metrics["wall_seconds"] = None
    try:
        metrics["agent_exit"] = int((out / "agent_exit").read_text().strip())
    except (OSError, ValueError):
        metrics["agent_exit"] = None

    tool_calls = Counter()
    assistant_msgs = 0
    tpath = out / "transcript.jsonl"
    if tpath.exists():
        for line in tpath.read_text().splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "assistant":
                assistant_msgs += 1
                for block in ev.get("message", {}).get("content", []):
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_calls[block.get("name", "?")] += 1
    metrics["assistant_messages"] = assistant_msgs
    metrics["tool_calls"] = dict(tool_calls)
    metrics["tool_calls_total"] = sum(tool_calls.values())

    rpath = out / "result.json"
    if rpath.exists() and rpath.read_text().strip():
        r = json.loads(rpath.read_text())
        metrics["total_cost_usd"] = r.get("total_cost_usd")
        metrics["num_turns"] = r.get("num_turns")
        metrics["duration_ms"] = r.get("duration_ms")
        metrics["duration_api_ms"] = r.get("duration_api_ms")
        metrics["is_error"] = r.get("is_error")
        metrics["permission_denials"] = len(r.get("permission_denials") or [])
        mu = (r.get("modelUsage") or {}).get(model) or {}
        metrics["input_tokens"] = mu.get("inputTokens")
        metrics["output_tokens"] = mu.get("outputTokens")
        metrics["cache_read_tokens"] = mu.get("cacheReadInputTokens")
        metrics["final_message"] = (r.get("result") or "")[:4000]

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
