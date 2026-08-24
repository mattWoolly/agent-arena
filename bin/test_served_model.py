#!/usr/bin/env python3
"""Tests for served_model.py. Run: python3 bin/test_served_model.py

Synthetic transcripts only -- no network, no real runs. Also cross-checks
against a real archived transcript when one is present.
"""
import json
import os
import tempfile

from served_model import served_models, summarize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def write(lines):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for obj in lines:
            fh.write(json.dumps(obj) + "\n")
    return path


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def test_claude_code_single():
    p = write([
        {"type": "system"},
        {"type": "assistant", "message": {"model": "claude-opus-5", "content": []}},
        {"type": "assistant", "message": {"model": "claude-opus-5", "content": []}},
        {"type": "result"},
    ])
    s = summarize(p)
    assert s["served_model"] == "claude-opus-5", s
    assert s["served_models"] == ["claude-opus-5"], s
    assert s["served_model_leak"] is False, s
    os.unlink(p)


@case
def test_kimi_code_format():
    p = write([
        {"role": "user", "content": "hi"},
        {"role": "assistant", "model": "kimi-k3", "content": "", "tool_calls": []},
    ])
    assert served_models(p) == ["kimi-k3"], served_models(p)
    os.unlink(p)


@case
def test_codex_format():
    p = write([
        {"type": "thread.started", "thread_id": "t"},
        {"type": "item.completed", "item": {"model": "gpt-5.6-sol", "text": "x"}},
    ])
    assert served_models(p) == ["gpt-5.6-sol"], served_models(p)
    os.unlink(p)


@case
def test_silent_substitution_is_visible():
    # The GLM case: requested glm-5.2, endpoint served glm-5.3. The extractor
    # reports what was SERVED, so a caller comparing against the request catches
    # it.
    p = write([
        {"type": "assistant", "message": {"model": "glm-5.3", "content": []}},
    ])
    assert summarize(p)["served_model"] == "glm-5.3"
    os.unlink(p)


@case
def test_side_channel_leak_flagged():
    # Two distinct served models in one run = a subagent/summarizer used a
    # different model than the arm pinned.
    p = write([
        {"type": "assistant", "message": {"model": "claude-opus-5", "content": []}},
        {"type": "assistant", "message": {"model": "claude-haiku-4-5", "content": []}},
        {"type": "assistant", "message": {"model": "claude-opus-5", "content": []}},
    ])
    s = summarize(p)
    assert s["served_model_leak"] is True, s
    assert s["served_model"] == "claude-opus-5", s  # modal wins
    assert set(s["served_models"]) == {"claude-opus-5", "claude-haiku-4-5"}, s
    os.unlink(p)


@case
def test_request_echo_is_not_counted():
    # A user turn or params echo that mentions a model must NOT count as served.
    p = write([
        {"type": "user", "message": {"model": "should-be-ignored", "content": "hi"}},
        {"role": "user", "model": "also-ignored", "content": "hi"},
        {"type": "assistant", "message": {"model": "claude-opus-5", "content": []}},
    ])
    assert served_models(p) == ["claude-opus-5"], served_models(p)
    os.unlink(p)


@case
def test_empty_and_malformed():
    p = write([])
    assert summarize(p) == {"served_models": [], "served_model": None,
                            "served_model_leak": False}
    os.unlink(p)
    # a file with a non-JSON line and one good line
    fd, p2 = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write("not json\n")
        fh.write(json.dumps({"type": "assistant",
                             "message": {"model": "glm-5.3"}}) + "\n")
    assert served_models(p2) == ["glm-5.3"]
    os.unlink(p2)


@case
def test_missing_file():
    assert served_models("/nonexistent/path.jsonl") == []


@case
def test_real_archived_transcript():
    # Cross-check against a real archived run if the corpus is present.
    if os.environ.get("ARENA_SYNTHETIC_ONLY") == "1":
        print("  (skip test_real_archived_transcript: ARENA_SYNTHETIC_ONLY=1)")
        return
    import glob
    hits = glob.glob(os.path.join(ROOT, "bouts", "*glm*", "*", "*",
                                  "transcript.jsonl"))
    hits += glob.glob(os.path.join(ROOT, "bouts", "*glm*", "*", "*", "*",
                                   "transcript.jsonl"))
    if not hits:
        print("  (skip test_real_archived_transcript: no glm bouts present)")
        return
    ms = served_models(hits[0])
    assert ms, f"expected a served model in {hits[0]}, got {ms}"
    assert all(isinstance(m, str) and m for m in ms), ms


def main():
    failed = 0
    for fn in CASES:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERR  {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
