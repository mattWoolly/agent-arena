"""Hidden tests: extra edge coverage of the same intended behavior."""
from lrucache import LRUCache


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def advance(self, dt):
        self.now += dt

    def __call__(self):
        return self.now


def test_capacity_one():
    c = LRUCache(1)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") is None
    assert c.get("b") == 2


def test_update_makes_key_most_recent():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 9)  # updating "a" makes it most recently used
    c.put("c", 3)  # evicts "b"
    assert c.get("a") == 9
    assert c.get("b") is None
    assert c.get("c") == 3


def test_no_ttl_never_expires():
    clock = FakeClock()
    c = LRUCache(2, ttl=None, clock=clock)
    c.put("a", 1)
    clock.advance(1e9)
    assert c.get("a") == 1


def test_expired_entry_is_removed():
    clock = FakeClock()
    c = LRUCache(2, ttl=5, clock=clock)
    c.put("a", 1)
    clock.advance(6)
    assert c.get("a") is None
    assert len(c) == 0


def test_get_returns_default_not_none():
    c = LRUCache(1)
    sentinel = object()
    assert c.get("nope", sentinel) is sentinel


def test_capacity_validation():
    try:
        LRUCache(0)
    except ValueError:
        pass
    else:
        raise AssertionError("capacity 0 must raise ValueError")
