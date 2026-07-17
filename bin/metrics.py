#!/usr/bin/env python3
"""Extract run metrics from a run output dir: transcript.jsonl + result.json."""
import json
import sys
from collections import Counter
from pathlib import Path


def computed_cost(out: Path, model: str) -> tuple[float, str] | None:
    """Recompute cost from per-request transcript usage and env/prices.json.

    The CLI prices unknown model IDs from its own (Claude) table, so proxied
    models get fiction. For models listed in env/prices.json we walk the
    transcript's assistant messages (deduped by message id, so retries and
    multi-block messages count once) and price each API request, including
    cache tiers and long-context multipliers where the sheet defines them.
    """
    ppath = Path(__file__).resolve().parent.parent / "env" / "prices.json"
    tpath = out / "transcript.jsonl"
    if not (ppath.exists() and tpath.exists()):
        return None
    prices = json.loads(ppath.read_text()).get(model)
    if not prices:
        return None
    usage_by_id: dict = {}
    for i, line in enumerate(tpath.read_text().splitlines()):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") != "assistant":
            continue
        msg = ev.get("message", {})
        if msg.get("usage"):
            usage_by_id[msg.get("id") or f"line-{i}"] = msg["usage"]
    def price_one(u: dict, per_request: bool) -> float:
        inp = u.get("input_tokens") or 0
        cread = u.get("cache_read_input_tokens") or 0
        cwrite = u.get("cache_creation_input_tokens") or 0
        outp = u.get("output_tokens") or 0
        in_mult = out_mult = 1.0
        threshold = prices.get("long_context_threshold")
        # The long-context surcharge is per request; it cannot be judged from
        # an aggregate, so it only applies when we have per-request usage.
        if per_request and threshold and (inp + cread + cwrite) > threshold:
            in_mult = prices.get("long_context_input_multiplier", 1.0)
            out_mult = prices.get("long_context_output_multiplier", 1.0)
        return (
            inp * prices["input"] * in_mult
            + cread * prices.get("cache_read", prices["input"])
            + cwrite * prices["input"] * prices.get("cache_write_multiplier", 1.0)
            + outp * prices["output"] * out_mult
        ) / 1e6

    total = sum(price_one(u, per_request=True) for u in usage_by_id.values())
    if total > 0:
        return round(total, 5), "computed:env/prices.json (per-request)"
    # Some proxies zero out per-message usage; fall back to the envelope's
    # aggregate usage (no long-context surcharge judgeable at this precision).
    rpath = out / "result.json"
    if rpath.exists() and rpath.read_text().strip():
        agg = json.loads(rpath.read_text()).get("usage") or {}
        total = price_one(agg, per_request=False)
        if total > 0:
            return round(total, 5), "computed:env/prices.json (aggregate)"
    return None


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
        cc = computed_cost(out, model)
        if cc is not None:
            metrics["total_cost_usd_cli"] = metrics.get("total_cost_usd")
            metrics["total_cost_usd"], metrics["cost_source"] = cc

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
