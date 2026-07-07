"""Reference solutions."""
import re
from collections import Counter, deque

_DURATION_RE = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")


def parse_duration(s):
    if not isinstance(s, str):
        raise ValueError(f"not a string: {s!r}")
    m = _DURATION_RE.fullmatch(s)
    if not m or not s or all(g is None for g in m.groups()):
        raise ValueError(f"invalid duration: {s!r}")
    h, mi, se = (int(g) if g else 0 for g in m.groups())
    return h * 3600 + mi * 60 + se


def luhn_valid(number):
    if not isinstance(number, str):
        return False
    digits = number.replace(" ", "").replace("-", "")
    if not digits or not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def flatten(d, sep="."):
    out = {}

    def walk(prefix, obj):
        for k, v in obj.items():
            key = f"{prefix}{sep}{k}" if prefix else k
            if isinstance(v, dict):
                walk(key, v)
            else:
                out[key] = v

    walk("", d)
    return out


def top_k_frequent(words, k):
    if k <= 0:
        return []
    counts = Counter(words)
    return sorted(counts, key=lambda w: (-counts[w], w))[:k]


def rolling_max(nums, window):
    if window <= 0:
        raise ValueError("window must be positive")
    if window > len(nums):
        return []
    dq = deque()
    out = []
    for i, x in enumerate(nums):
        while dq and nums[dq[-1]] <= x:
            dq.pop()
        dq.append(i)
        if dq[0] <= i - window:
            dq.popleft()
        if i >= window - 1:
            out.append(nums[dq[0]])
    return out
