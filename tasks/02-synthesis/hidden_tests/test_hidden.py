import time

import pytest

from problems import flatten, luhn_valid, parse_duration, rolling_max, top_k_frequent


def test_parse_duration():
    assert parse_duration("1h30m15s") == 5415
    assert parse_duration("90m") == 5400
    assert parse_duration("2h") == 7200
    assert parse_duration("45s") == 45
    assert parse_duration("1h5s") == 3605
    assert parse_duration("120m") == 7200
    assert parse_duration("0s") == 0
    for bad in ["", "h", "30m1h", "1h2h", "-5m", "1h ", " 1h", "1h!", "1d", "1.5h"]:
        with pytest.raises(ValueError):
            parse_duration(bad)


def test_luhn_valid():
    assert luhn_valid("4539148803436467") is True
    assert luhn_valid("4539 1488 0343 6467") is True
    assert luhn_valid("4539-1488-0343-6467") is True
    assert luhn_valid("4539148803436468") is False
    assert luhn_valid("79927398713") is True
    assert luhn_valid("79927398714") is False
    assert luhn_valid("0") is True
    assert luhn_valid("1") is False
    assert luhn_valid("") is False
    assert luhn_valid("   ") is False
    assert luhn_valid("4539x488") is False


def test_flatten():
    assert flatten({"a": {"b": 1, "c": {"d": 2}}, "e": 3}) == {
        "a.b": 1,
        "a.c.d": 2,
        "e": 3,
    }
    assert flatten({"a": {}}) == {}
    assert flatten({}) == {}
    assert flatten({"a": {"b": 2}}, sep="/") == {"a/b": 2}
    assert flatten({"a": [1, {"x": 2}]}) == {"a": [1, {"x": 2}]}
    original = {"a": {"b": 1}}
    flatten(original)
    assert original == {"a": {"b": 1}}


def test_top_k_frequent():
    assert top_k_frequent(["b", "a", "b", "c", "a"], 2) == ["a", "b"]
    assert top_k_frequent(["z", "z", "a"], 2) == ["z", "a"]
    assert top_k_frequent(["x"], 5) == ["x"]
    assert top_k_frequent([], 3) == []
    assert top_k_frequent(["a", "b"], 0) == []
    assert top_k_frequent(["a", "b"], -1) == []
    assert top_k_frequent(["B", "b", "B"], 2) == ["B", "b"]


def test_rolling_max():
    assert rolling_max([1, 3, 2, 5, 4], 3) == [3, 5, 5]
    assert rolling_max([2, 1], 1) == [2, 1]
    assert rolling_max([1, 2], 5) == []
    assert rolling_max([], 1) == []
    assert rolling_max([5, 4, 3, 2, 1], 2) == [5, 4, 3, 2]
    with pytest.raises(ValueError):
        rolling_max([1], 0)
    with pytest.raises(ValueError):
        rolling_max([1], -2)


def test_rolling_max_is_linear():
    n = 200_000
    nums = [(i * 2654435761) % 1_000_003 for i in range(n)]
    start = time.perf_counter()
    out = rolling_max(nums, 5000)
    elapsed = time.perf_counter() - start
    assert len(out) == n - 5000 + 1
    assert elapsed < 3.0, f"too slow ({elapsed:.1f}s) — not O(n)"
