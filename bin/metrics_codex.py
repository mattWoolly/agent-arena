#!/usr/bin/env python3
"""Extract run metrics from a codex-exec run dir (codex --json event stream).

Emits the same metric keys as metrics.py so summarize.py aggregates both
drivers into one table. Cost is computed from per-turn usage in
turn.completed events (codex reports cached_input_tokens natively; the
cached count is a subset of input_tokens, per OpenAI usage semantics)
against env/prices.json. The model key in prices.json is the label minus
the "-codex" suffix.
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
    usage_records = []
    tpath = out / "transcript.jsonl"
    if tpath.exists():
        for line in tpath.read_text().splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            et = ev.get("type")
            if et == "turn.completed":
                turns += 1
                if ev.get("usage"):
                    usage_records.append(ev["usage"])
            elif et == "item.completed":
                item = ev.get("item") or {}
                itype = item.get("item_type") or item.get("type") or "?"
                if itype not in ("agent_message", "reasoning"):
                    tool_calls[itype] += 1
    metrics["num_turns"] = turns
    metrics["assistant_messages"] = turns
    metrics["tool_calls"] = dict(tool_calls)
    metrics["tool_calls_total"] = sum(tool_calls.values())

    inp = sum(u.get("input_tokens") or 0 for u in usage_records)
    cached = sum(u.get("cached_input_tokens") or 0 for u in usage_records)
    outp = sum(u.get("output_tokens") or 0 for u in usage_records)
    metrics["input_tokens"] = inp
    metrics["cache_read_tokens"] = cached
    metrics["output_tokens"] = outp

    model_key = label.removesuffix("-codex")
    ppath = Path(__file__).resolve().parent.parent / "env" / "prices.json"
    if ppath.exists():
        prices = json.loads(ppath.read_text()).get(model_key)
        if prices:
            total = 0.0
            for u in usage_records:
                ui = u.get("input_tokens") or 0
                uc = u.get("cached_input_tokens") or 0
                uo = u.get("output_tokens") or 0
                in_mult = out_mult = 1.0
                threshold = prices.get("long_context_threshold")
                if threshold and ui > threshold:
                    in_mult = prices.get("long_context_input_multiplier", 1.0)
                    out_mult = prices.get("long_context_output_multiplier", 1.0)
                total += (
                    (ui - uc) * prices["input"] * in_mult
                    + uc * prices.get("cache_read", prices["input"])
                    + uo * prices["output"] * out_mult
                ) / 1e6
            metrics["total_cost_usd"] = round(total, 5)
            metrics["cost_source"] = f"computed:env/prices.json (codex per-turn usage, {len(usage_records)} turns)"

    lpath = out / "last_message.txt"
    if lpath.exists():
        metrics["final_message"] = lpath.read_text()[:4000]

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
