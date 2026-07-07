import time
from collections import OrderedDict


class LRUCache:
    """Reference solution: recency refreshed on get and on update."""

    def __init__(self, capacity, ttl=None, clock=time.monotonic):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self.ttl = ttl
        self._clock = clock
        self._data = OrderedDict()

    def get(self, key, default=None):
        if key not in self._data:
            return default
        value, ts = self._data[key]
        if self.ttl is not None and self._clock() - ts > self.ttl:
            del self._data[key]
            return default
        self._data.move_to_end(key)
        return value

    def put(self, key, value):
        if key in self._data:
            self._data[key] = (value, self._clock())
            self._data.move_to_end(key)
            return
        if len(self._data) >= self.capacity:
            self._data.popitem(last=False)
        self._data[key] = (value, self._clock())

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return self.get(key, default=_MISSING) is not _MISSING


_MISSING = object()
