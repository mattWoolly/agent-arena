from lrucache import LRUCache


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def advance(self, dt):
        self.now += dt

    def __call__(self):
        return self.now


def test_basic_put_get():
    c = LRUCache(2)
    c.put("a", 1)
    assert c.get("a") == 1
    assert c.get("missing") is None
    assert c.get("missing", 42) == 42


def test_get_refreshes_recency():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1  # "a" is now most recently used
    c.put("c", 3)  # must evict "b", the least recently used
    assert c.get("a") == 1
    assert c.get("b") is None
    assert c.get("c") == 3


def test_updating_existing_key_does_not_evict_others():
    c = LRUCache(2)
    c.put("x", 1)
    c.put("y", 2)
    c.put("y", 3)  # update in place; "x" must survive
    assert c.get("x") == 1
    assert c.get("y") == 3


def test_eviction_order():
    c = LRUCache(3)
    for k in ("a", "b", "c"):
        c.put(k, k.upper())
    c.put("d", "D")  # evicts "a"
    assert c.get("a") is None
    assert c.get("b") == "B"


def test_ttl_expiry():
    clock = FakeClock()
    c = LRUCache(2, ttl=10, clock=clock)
    c.put("a", 1)
    clock.advance(11)
    assert c.get("a") is None
    assert len(c) == 0


def test_contains():
    c = LRUCache(1)
    c.put("k", None)  # storing None is legal
    assert "k" in c
    assert "other" not in c
