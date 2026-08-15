#!/usr/bin/env python3
"""Extract the model(s) a transcript was actually served by.

Motivation (2026-08-15): Z.ai's Anthropic-compatible endpoint silently serves
GLM-5.3 when GLM-5.2 is requested, with no error and no warning -- the only
signal is the `model` field on each response. A version-pinned comparison run
through such an endpoint is invalid unless every run's *served* model is
recorded and checked against what was requested. Nothing in the harness did
this before. This module is that check.

Supports all three transcript formats the arena records:
  - Claude Code   : {"type":"assistant","message":{"model": "...", ...}}
  - Codex CLI     : {"type":"item.completed","item":{... "model": "..." ...}}
  - Kimi Code     : {"role":"assistant","model":"...", ...}

Usage:
  served_model.py <transcript.jsonl>   -> prints JSON {served_models, leak}
  from served_model import served_models
"""
from __future__ import annotations

import json
import sys
from collections import Counter


def _models_in_obj(obj):
    """Yield every plausible served-model string in one parsed JSON event.

    We look only at assistant/response-side model tags, never at request
    echoes, so a requested-model field elsewhere can't masquerade as served.
    """
    if not isinstance(obj, dict):
        return
    t = obj.get("type")
    # Claude Code assistant event.
    if t == "assistant":
        m = (obj.get("message") or {})
        if isinstance(m, dict) and isinstance(m.get("model"), str):
            yield m["model"]
        return
    # Kimi Code: bare assistant message with a top-level model tag.
    if obj.get("role") == "assistant" and isinstance(obj.get("model"), str):
        yield obj["model"]
        return
    # Codex CLI: completed items may carry a model tag on the item.
    item = obj.get("item")
    if isinstance(item, dict) and isinstance(item.get("model"), str):
        yield item["model"]


def served_models(transcript_path) -> list[str]:
    """Distinct served-model strings, ordered by frequency (most common first)."""
    counts: Counter[str] = Counter()
    try:
        with open(transcript_path, errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for m in _models_in_obj(ev):
                    counts[m] += 1
    except OSError:
        return []
    return [m for m, _ in counts.most_common()]


def summarize(transcript_path) -> dict:
    ms = served_models(transcript_path)
    return {
        "served_models": ms,
        "served_model": ms[0] if ms else None,
        # >1 distinct served model in one run means a side channel (a subagent
        # or background summarizer) used a different model/vendor than the arm
        # pinned. Always a red flag for a controlled comparison.
        "served_model_leak": len(ms) > 1,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: served_model.py <transcript.jsonl>", file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(summarize(sys.argv[1]), indent=2))
