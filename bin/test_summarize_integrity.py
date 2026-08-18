#!/usr/bin/env python3
"""Tests for summarize.py's served-model integrity gate.
Run: python3 bin/test_summarize_integrity.py

Builds synthetic bout directories (no runs, no network) and asserts the gate
catches a silent version substitution and a side-channel model leak, and does
not false-positive on a clean bout.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def cell(bout, task, model, served, *, leak=False, extra=None, grade_pass=True):
    d = os.path.join(bout, task, model, "run-1")
    os.makedirs(d)
    sms = [served] + ([extra] if extra else [])
    json.dump({
        "model": model, "served_model": served, "served_models": sms,
        "served_model_leak": leak, "grade_pass": grade_pass,
        "wall_seconds": 10, "total_cost_usd": 0.5, "num_turns": 8,
        "output_tokens": 1000, "cache_read_tokens": 5000,
    }, open(os.path.join(d, "metrics.json"), "w"))


def summarize(bout):
    r = subprocess.run([sys.executable, os.path.join(HERE, "summarize.py"), bout],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return open(os.path.join(bout, "results.md")).read()


def test_catches_substitution_and_leak():
    b = tempfile.mkdtemp(prefix="bout-bad-")
    try:
        json.dump({"glm-5.3": "glm-5.3", "claude-opus-5": "claude-opus-5"},
                  open(os.path.join(b, "EXPECTED.json"), "w"))
        cell(b, "01-bugfix", "glm-5.3", "glm-5.2")  # served an OLDER model than asked
        cell(b, "01-bugfix", "claude-opus-5", "claude-opus-5")
        cell(b, "02-synthesis", "claude-opus-5", "claude-opus-5",
             leak=True, extra="claude-haiku-4-5")
        md = summarize(b)
        assert "SERVED-MODEL INTEGRITY FAILURES" in md, md
        assert "SUBSTITUTION" in md and "glm-5.2" in md, md
        assert "LEAK" in md, md
    finally:
        shutil.rmtree(b)


def test_clean_bout_passes():
    b = tempfile.mkdtemp(prefix="bout-ok-")
    try:
        json.dump({"glm-5.3": "glm-5.3", "claude-opus-5": "claude-opus-5"},
                  open(os.path.join(b, "EXPECTED.json"), "w"))
        cell(b, "01-bugfix", "glm-5.3", "glm-5.3")
        cell(b, "01-bugfix", "claude-opus-5", "claude-opus-5")
        md = summarize(b)
        assert "INTEGRITY FAILURES" not in md, md
        assert "served-model check: OK" in md, md
    finally:
        shutil.rmtree(b)


def test_missing_served_tag_flagged():
    b = tempfile.mkdtemp(prefix="bout-missing-")
    try:
        json.dump({"glm-5.3": "glm-5.3"}, open(os.path.join(b, "EXPECTED.json"), "w"))
        d = os.path.join(b, "01-bugfix", "glm-5.3", "run-1")
        os.makedirs(d)
        json.dump({"model": "glm-5.3", "served_model": None, "served_models": [],
                   "served_model_leak": False, "grade_pass": True},
                  open(os.path.join(d, "metrics.json"), "w"))
        md = summarize(b)
        assert "MISSING" in md, md
    finally:
        shutil.rmtree(b)


def main():
    tests = [test_catches_substitution_and_leak, test_clean_bout_passes,
             test_missing_served_tag_flagged]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ok   {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {str(e)[:200]}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
